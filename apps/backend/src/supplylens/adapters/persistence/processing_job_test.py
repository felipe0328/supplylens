from collections.abc import Iterator
from datetime import datetime
from unittest.mock import Mock
from uuid import UUID

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from supplylens.adapters.persistence.documents import DocumentPersistenceAdapter
from supplylens.adapters.persistence.processing_job import (
    ProcessingJobPersistenceAdapter,
)
from supplylens.database.database import Base
from supplylens.domain.documents import DocumentUploadStatus
from supplylens.domain.processing_job import ProcessingJobState
from supplylens.models.document import Document
from supplylens.models.processing_job import ProcessingJob as ModelProcessingJob
from supplylens.port.persistence.processing_job import ProcessingJob

DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000001")
OTHER_DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000002")


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(engine)
        with Session(engine, autoflush=False) as database_session:
            database_session.add(
                Document(id=DOCUMENT_ID, filename="synthetic.pdf", size_bytes=128)
            )
            database_session.commit()
            yield database_session
    finally:
        engine.dispose()


def test_enqueue_creates_pending_job_and_leaves_commit_to_caller(
    session: Session,
) -> None:
    adapter = ProcessingJobPersistenceAdapter(session)

    job_id = adapter.enqueue_new_job(DOCUMENT_ID)
    job = adapter.get_job_by_id(job_id)

    assert job_id > 0
    assert isinstance(job, ProcessingJob)
    assert job.document_uuid == DOCUMENT_ID
    assert job.status is ProcessingJobState.PENDING
    assert job.attempts == 1
    assert isinstance(job.created_at, datetime)
    assert job.lease_owner is None
    assert job.lease_expires_at is None
    assert job.error_code is None
    assert job.error_message is None
    assert job.started_at is None
    assert job.finished_at is None

    session.rollback()

    assert adapter.get_job_by_id(job_id) is None
    assert adapter.get_job_by_document_uuid(DOCUMENT_ID) is None


def test_enqueue_commits_when_caller_commits(session: Session) -> None:
    adapter = ProcessingJobPersistenceAdapter(session)
    job_id = adapter.enqueue_new_job(DOCUMENT_ID)

    session.commit()

    with Session(session.get_bind()) as verification_session:
        job = ProcessingJobPersistenceAdapter(verification_session).get_job_by_id(
            job_id
        )
        assert job is not None
        assert job.document_uuid == DOCUMENT_ID


@pytest.mark.parametrize("commit_between_calls", [False, True])
def test_repeated_enqueue_reuses_job(
    session: Session, commit_between_calls: bool
) -> None:
    adapter = ProcessingJobPersistenceAdapter(session)
    first_id = adapter.enqueue_new_job(DOCUMENT_ID)
    original = adapter.get_job_by_id(first_id)
    if commit_between_calls:
        session.commit()

    second_id = adapter.enqueue_new_job(DOCUMENT_ID)

    assert second_id == first_id
    assert adapter.get_job_by_id(second_id) == original
    assert session.scalar(select(func.count()).select_from(ModelProcessingJob)) == 1


@pytest.mark.parametrize("status", list(ProcessingJobState))
def test_enqueue_preserves_existing_job_state(
    session: Session, status: ProcessingJobState
) -> None:
    existing = ModelProcessingJob(
        document_id=DOCUMENT_ID,
        status=status,
        attempts=3,
        error_code=17,
        error_message="Synthetic previous failure",
    )
    session.add(existing)
    session.commit()
    adapter = ProcessingJobPersistenceAdapter(session)
    original = adapter.get_job_by_id(existing.id)

    assert adapter.enqueue_new_job(DOCUMENT_ID) == existing.id
    assert adapter.get_job_by_id(existing.id) == original
    assert session.scalar(select(func.count()).select_from(ModelProcessingJob)) == 1


def test_lookups_return_only_requested_job(session: Session) -> None:
    session.add(
        Document(id=OTHER_DOCUMENT_ID, filename="other-synthetic.pdf", size_bytes=256)
    )
    session.flush()
    adapter = ProcessingJobPersistenceAdapter(session)
    first_id = adapter.enqueue_new_job(DOCUMENT_ID)
    second_id = adapter.enqueue_new_job(OTHER_DOCUMENT_ID)

    first = adapter.get_job_by_document_uuid(DOCUMENT_ID)
    second = adapter.get_job_by_document_uuid(OTHER_DOCUMENT_ID)

    assert first is not None
    assert second is not None
    assert first.id == first_id
    assert second.id == second_id
    assert first_id != second_id
    assert first.document_uuid == DOCUMENT_ID
    assert second.document_uuid == OTHER_DOCUMENT_ID
    assert adapter.get_job_by_id(first_id) == first
    assert adapter.get_job_by_id(second_id) == second


def test_lookups_return_none_for_missing_job(session: Session) -> None:
    adapter = ProcessingJobPersistenceAdapter(session)

    assert adapter.get_job_by_id(999) is None
    assert adapter.get_job_by_document_uuid(DOCUMENT_ID) is None


def test_enqueue_rejects_missing_document_without_creating_job(
    session: Session,
) -> None:
    adapter = ProcessingJobPersistenceAdapter(session)

    with pytest.raises(ValueError, match=f"Document {OTHER_DOCUMENT_ID} not found"):
        adapter.enqueue_new_job(OTHER_DOCUMENT_ID)

    assert session.scalar(select(func.count()).select_from(ModelProcessingJob)) == 0


@pytest.mark.parametrize("has_job", [False, True])
def test_enqueue_rejects_deleted_document(session: Session, has_job: bool) -> None:
    adapter = ProcessingJobPersistenceAdapter(session)
    if has_job:
        adapter.enqueue_new_job(DOCUMENT_ID)
    DocumentPersistenceAdapter(session).delete_document(DOCUMENT_ID)
    session.commit()

    with pytest.raises(ValueError, match=f"Document {DOCUMENT_ID} not found"):
        adapter.enqueue_new_job(DOCUMENT_ID)

    assert session.scalar(select(func.count()).select_from(ModelProcessingJob)) == int(
        has_job
    )


def test_enqueue_requests_document_lock_before_job_lookup() -> None:
    # SQLite does not implement FOR UPDATE: inspect PostgreSQL SQL, not concurrency.
    session = Mock(spec=Session)
    session.scalar.side_effect = [DOCUMENT_ID, None]
    session.add.side_effect = lambda job: setattr(job, "id", 42)

    assert ProcessingJobPersistenceAdapter(session).enqueue_new_job(DOCUMENT_ID) == 42

    lock_statement, lookup_statement = [
        invocation.args[0] for invocation in session.scalar.call_args_list
    ]
    lock_sql = str(lock_statement.compile(dialect=postgresql.dialect()))
    lookup_sql = str(lookup_statement.compile(dialect=postgresql.dialect()))
    assert "SELECT documents.id" in lock_sql
    assert "documents.deleted_at IS NULL" in lock_sql
    assert lock_sql.endswith("FOR UPDATE")
    assert lock_statement.compile().params["id_1"] == DOCUMENT_ID
    assert "processing_jobs.document_id =" in lookup_sql
    assert lookup_statement.compile().params["document_id_1"] == DOCUMENT_ID
    assert [invocation[0] for invocation in session.mock_calls] == [
        "scalar",
        "scalar",
        "add",
        "flush",
    ]
    new_job = session.add.call_args.args[0]
    assert isinstance(new_job, ModelProcessingJob)
    assert new_job.document_id == DOCUMENT_ID
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_enqueue_propagates_flush_failure_without_owning_transaction() -> None:
    session = Mock(spec=Session)
    session.scalar.side_effect = [DOCUMENT_ID, None]
    error = RuntimeError("synthetic insert failure")
    session.flush.side_effect = error

    with pytest.raises(RuntimeError) as raised:
        ProcessingJobPersistenceAdapter(session).enqueue_new_job(DOCUMENT_ID)

    assert raised.value is error
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_document_status_and_job_roll_back_together(session: Session) -> None:
    with pytest.raises(RuntimeError, match="processing failed"):
        with session.begin():
            DocumentPersistenceAdapter(session).update_document_upload_status(
                DOCUMENT_ID, DocumentUploadStatus.UPLOADED
            )
            ProcessingJobPersistenceAdapter(session).enqueue_new_job(DOCUMENT_ID)
            raise RuntimeError("processing failed")

    document = session.get(Document, DOCUMENT_ID)
    assert document is not None
    assert document.upload_status is DocumentUploadStatus.PENDING
    assert document.uploaded_at is None
    assert session.scalar(select(func.count()).select_from(ModelProcessingJob)) == 0
