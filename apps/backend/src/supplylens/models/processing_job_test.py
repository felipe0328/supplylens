from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from supplylens.database.database import Base
from supplylens.domain.processing_job import ProcessingJobState
from supplylens.models.document import Document
from supplylens.models.processing_job import ProcessingJob


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(engine)

        with Session(engine) as database_session:
            yield database_session
    finally:
        engine.dispose()


@pytest.fixture
def document_id(session: Session) -> UUID:
    document = Document(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        filename="synthetic.pdf",
        size_bytes=128,
    )
    session.add(document)
    session.flush()
    return document.id


def test_processing_job_defaults_and_nullable_fields(
    session: Session, document_id: UUID
) -> None:
    job = ProcessingJob(document_id=document_id)
    session.add(job)
    session.flush()

    assert isinstance(job.id, int)
    assert job.document_id == document_id
    assert job.attempts == 1
    assert job.status is ProcessingJobState.PENDING
    assert job.created_at is not None
    assert job.lease_owner is None
    assert job.lease_expires_at is None
    assert job.error_code is None
    assert job.error_message is None
    assert job.started_at is None
    assert job.finished_at is None


def test_processing_job_defaults_apply_when_defaulted_fields_are_none(
    session: Session, document_id: UUID
) -> None:
    job = ProcessingJob(
        document_id=document_id, attempts=None, status=None, created_at=None
    )
    session.add(job)
    session.flush()

    assert job.attempts == 1
    assert job.status is ProcessingJobState.PENDING
    assert job.created_at is not None


@pytest.mark.parametrize("status", list(ProcessingJobState))
def test_processing_job_persists_statuses(
    session: Session, document_id: UUID, status: ProcessingJobState
) -> None:
    job = ProcessingJob(document_id=document_id, status=status)
    session.add(job)
    session.flush()
    job_id = job.id
    session.commit()
    session.expunge_all()

    persisted_job = session.get(ProcessingJob, job_id)

    assert persisted_job is not None
    assert persisted_job.status is status


def test_processing_job_persists_optional_values(
    session: Session, document_id: UUID
) -> None:
    started_at = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
    finished_at = datetime(2026, 10, 6, 12, 1, tzinfo=UTC)
    lease_expires_at = datetime(2026, 10, 6, 12, 5, tzinfo=UTC)
    job = ProcessingJob(
        document_id=document_id,
        attempts=2,
        lease_owner="worker-1",
        lease_expires_at=lease_expires_at,
        error_code=1001,
        error_message="Synthetic processing failure.",
        started_at=started_at,
        finished_at=finished_at,
    )
    session.add(job)
    session.flush()
    job_id = job.id
    session.commit()
    session.expunge_all()

    persisted_job = session.get(ProcessingJob, job_id)

    assert persisted_job is not None
    assert persisted_job.document_id == document_id
    assert persisted_job.attempts == 2
    assert persisted_job.lease_owner == "worker-1"
    assert persisted_job.error_code == 1001
    assert persisted_job.error_message == "Synthetic processing failure."
    # SQLite does not preserve timezone information; PostgreSQL needs separate coverage.
    assert persisted_job.lease_expires_at == lease_expires_at.replace(tzinfo=None)
    assert persisted_job.started_at == started_at.replace(tzinfo=None)
    assert persisted_job.finished_at == finished_at.replace(tzinfo=None)


def test_processing_job_accepts_zero_attempts(
    session: Session, document_id: UUID
) -> None:
    job = ProcessingJob(document_id=document_id, attempts=0)
    session.add(job)
    session.flush()

    assert job.attempts == 0


def test_processing_job_rejects_negative_attempts(
    session: Session, document_id: UUID
) -> None:
    session.add(ProcessingJob(document_id=document_id, attempts=-1))

    with pytest.raises(IntegrityError, match="ck_attempts_positive"):
        session.flush()


@pytest.mark.parametrize(
    "document_id",
    [None, UUID("00000000-0000-0000-0000-000000000002")],
)
def test_processing_job_rejects_missing_or_unknown_document(
    session: Session, document_id: UUID | None
) -> None:
    session.add(ProcessingJob(document_id=document_id))

    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize(
    ("lease_owner", "lease_expires_at"),
    [
        ("worker-1", None),
        (None, datetime(2026, 10, 6, 12, 5, tzinfo=UTC)),
    ],
)
def test_processing_job_rejects_unpaired_lease_on_insert(
    session: Session,
    document_id: UUID,
    lease_owner: str | None,
    lease_expires_at: datetime | None,
) -> None:
    session.add(
        ProcessingJob(
            document_id=document_id,
            lease_owner=lease_owner,
            lease_expires_at=lease_expires_at,
        )
    )

    with pytest.raises(IntegrityError, match="ck_processing_job_lease_fields_paired"):
        session.flush()


@pytest.mark.parametrize("field_name", ["lease_owner", "lease_expires_at"])
def test_processing_job_rejects_unpaired_lease_on_update(
    session: Session, document_id: UUID, field_name: str
) -> None:
    job = ProcessingJob(
        document_id=document_id,
        lease_owner="worker-1",
        lease_expires_at=datetime(2026, 10, 6, 12, 5, tzinfo=UTC),
    )
    session.add(job)
    session.flush()
    setattr(job, field_name, None)

    with pytest.raises(IntegrityError, match="ck_processing_job_lease_fields_paired"):
        session.flush()


def test_processing_job_can_claim_and_clear_lease(
    session: Session, document_id: UUID
) -> None:
    job = ProcessingJob(document_id=document_id)
    session.add(job)
    session.flush()

    job.lease_owner = "worker-1"
    job.lease_expires_at = datetime(2026, 10, 6, 12, 5, tzinfo=UTC)
    session.flush()

    job.lease_owner = None
    job.lease_expires_at = None
    session.flush()
    session.refresh(job)

    assert job.lease_owner is None
    assert job.lease_expires_at is None


def test_processing_job_has_nonunique_document_id_index(session: Session) -> None:
    indexes = inspect(session.get_bind()).get_indexes("processing_jobs")

    assert any(
        index["column_names"] == ["document_id"] and not index["unique"]
        for index in indexes
    )
