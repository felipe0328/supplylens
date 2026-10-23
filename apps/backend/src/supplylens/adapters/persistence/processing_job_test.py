from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
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
NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
LEASE_OWNER = "synthetic-worker-1"
LEASE_EXPIRES_AT = NOW + timedelta(minutes=5)
MAX_ATTEMPTS = 3


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


def test_claim_next_job_claims_oldest_pending_job(session: Session) -> None:
    session.add(
        Document(id=OTHER_DOCUMENT_ID, filename="other-synthetic.pdf", size_bytes=256)
    )
    session.flush()
    adapter = ProcessingJobPersistenceAdapter(session)
    first_id = adapter.enqueue_new_job(DOCUMENT_ID)
    second_id = adapter.enqueue_new_job(OTHER_DOCUMENT_ID)
    session.flush()

    claimed = adapter.claim_next_job(
        LEASE_OWNER,
        LEASE_EXPIRES_AT,
        max_attempts=MAX_ATTEMPTS,
        now=NOW,
    )

    assert claimed is not None
    assert claimed.id == first_id
    assert claimed.id != second_id
    assert claimed.status is ProcessingJobState.PROCESSING
    assert claimed.lease_owner == LEASE_OWNER
    assert claimed.lease_expires_at == LEASE_EXPIRES_AT
    assert claimed.attempts == 1
    assert claimed.started_at == NOW
    assert claimed.finished_at is None
    assert claimed.error_code is None
    assert claimed.error_message is None


def test_claim_next_job_returns_none_when_queue_empty(session: Session) -> None:
    adapter = ProcessingJobPersistenceAdapter(session)

    assert (
        adapter.claim_next_job(
            LEASE_OWNER,
            LEASE_EXPIRES_AT,
            max_attempts=MAX_ATTEMPTS,
            now=NOW,
        )
        is None
    )


def test_claim_next_job_skips_active_lease_and_terminal_states(
    session: Session,
) -> None:
    session.add(
        Document(id=OTHER_DOCUMENT_ID, filename="other-synthetic.pdf", size_bytes=256)
    )
    session.flush()
    active = ModelProcessingJob(
        document_id=DOCUMENT_ID,
        status=ProcessingJobState.PROCESSING,
        lease_owner="other-worker",
        lease_expires_at=NOW + timedelta(minutes=1),
        attempts=1,
        started_at=NOW - timedelta(minutes=1),
    )
    succeeded = ModelProcessingJob(
        document_id=OTHER_DOCUMENT_ID,
        status=ProcessingJobState.SUCCEEDED,
        attempts=1,
        started_at=NOW - timedelta(minutes=2),
        finished_at=NOW - timedelta(minutes=1),
    )
    session.add_all([active, succeeded])
    session.commit()
    adapter = ProcessingJobPersistenceAdapter(session)

    assert (
        adapter.claim_next_job(
            LEASE_OWNER,
            LEASE_EXPIRES_AT,
            max_attempts=MAX_ATTEMPTS,
            now=NOW,
        )
        is None
    )


def test_claim_next_job_reclaims_expired_lease_and_increments_attempts(
    session: Session,
) -> None:
    existing = ModelProcessingJob(
        document_id=DOCUMENT_ID,
        status=ProcessingJobState.PROCESSING,
        lease_owner="other-worker",
        lease_expires_at=NOW - timedelta(seconds=1),
        attempts=1,
        started_at=NOW - timedelta(minutes=5),
        error_code=17,
        error_message="synthetic stale error",
        finished_at=NOW - timedelta(minutes=1),
    )
    session.add(existing)
    session.commit()
    adapter = ProcessingJobPersistenceAdapter(session)

    claimed = adapter.claim_next_job(
        LEASE_OWNER,
        LEASE_EXPIRES_AT,
        max_attempts=MAX_ATTEMPTS,
        now=NOW,
    )

    assert claimed is not None
    assert claimed.id == existing.id
    assert claimed.status is ProcessingJobState.PROCESSING
    assert claimed.lease_owner == LEASE_OWNER
    assert claimed.lease_expires_at == LEASE_EXPIRES_AT
    assert claimed.attempts == 2
    assert claimed.started_at == NOW
    assert claimed.finished_at is None
    assert claimed.error_code is None
    assert claimed.error_message is None


def test_claim_next_job_respects_max_attempts_on_expired_lease(
    session: Session,
) -> None:
    session.add(
        ModelProcessingJob(
            document_id=DOCUMENT_ID,
            status=ProcessingJobState.PROCESSING,
            lease_owner="other-worker",
            lease_expires_at=NOW - timedelta(seconds=1),
            attempts=MAX_ATTEMPTS,
            started_at=NOW - timedelta(minutes=5),
        )
    )
    session.commit()
    adapter = ProcessingJobPersistenceAdapter(session)

    assert (
        adapter.claim_next_job(
            LEASE_OWNER,
            LEASE_EXPIRES_AT,
            max_attempts=MAX_ATTEMPTS,
            now=NOW,
        )
        is None
    )


def test_claim_next_job_leaves_commit_to_caller(session: Session) -> None:
    adapter = ProcessingJobPersistenceAdapter(session)
    job_id = adapter.enqueue_new_job(DOCUMENT_ID)
    session.commit()

    claimed = adapter.claim_next_job(
        LEASE_OWNER,
        LEASE_EXPIRES_AT,
        max_attempts=MAX_ATTEMPTS,
        now=NOW,
    )
    assert claimed is not None
    assert claimed.id == job_id

    session.rollback()

    restored = adapter.get_job_by_id(job_id)
    assert restored is not None
    assert restored.status is ProcessingJobState.PENDING
    assert restored.lease_owner is None
    assert restored.lease_expires_at is None
    assert restored.started_at is None


def test_claim_next_job_requests_skip_locked_claim_query() -> None:
    # SQLite does not implement SKIP LOCKED: inspect PostgreSQL SQL, not concurrency.
    session = Mock(spec=Session)
    pending_job = ModelProcessingJob(
        document_id=DOCUMENT_ID,
        status=ProcessingJobState.PENDING,
        attempts=1,
    )
    pending_job.id = 42
    pending_job.created_at = NOW
    session.scalar.return_value = pending_job

    claimed = ProcessingJobPersistenceAdapter(session).claim_next_job(
        LEASE_OWNER,
        LEASE_EXPIRES_AT,
        max_attempts=MAX_ATTEMPTS,
        now=NOW,
    )

    assert claimed is not None
    assert claimed.id == 42
    claim_statement = session.scalar.call_args.args[0]
    claim_sql = str(claim_statement.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in claim_sql
    assert "SKIP LOCKED" in claim_sql
    assert "processing_jobs" in claim_sql
    session.flush.assert_called_once_with()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def _claim_pending_job(session: Session) -> int:
    adapter = ProcessingJobPersistenceAdapter(session)
    job_id = adapter.enqueue_new_job(DOCUMENT_ID)
    claimed = adapter.claim_next_job(
        LEASE_OWNER,
        LEASE_EXPIRES_AT,
        max_attempts=MAX_ATTEMPTS,
        now=NOW,
    )
    assert claimed is not None
    assert claimed.id == job_id
    session.commit()
    return job_id


def _as_utc(value: datetime) -> datetime:
    # SQLite drops tzinfo on persist/RETURNING; normalize for assertions.
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def test_extend_lease_updates_expiry_for_owner(session: Session) -> None:
    job_id = _claim_pending_job(session)
    adapter = ProcessingJobPersistenceAdapter(session)
    new_expiry = NOW + timedelta(minutes=10)

    assert adapter.extend_lease(job_id, LEASE_OWNER, new_expiry) is True

    job = adapter.get_job_by_id(job_id)
    assert job is not None
    assert job.status is ProcessingJobState.PROCESSING
    assert job.lease_owner == LEASE_OWNER
    assert job.lease_expires_at is not None
    assert _as_utc(job.lease_expires_at) == new_expiry


def test_extend_lease_rejects_wrong_owner_or_non_processing(
    session: Session,
) -> None:
    job_id = _claim_pending_job(session)
    adapter = ProcessingJobPersistenceAdapter(session)
    new_expiry = NOW + timedelta(minutes=10)

    assert adapter.extend_lease(job_id, "other-worker", new_expiry) is False
    assert adapter.complete_job(job_id, LEASE_OWNER, NOW) is not None
    session.commit()
    assert adapter.extend_lease(job_id, LEASE_OWNER, new_expiry) is False


def test_complete_job_marks_succeeded_and_clears_lease(session: Session) -> None:
    job_id = _claim_pending_job(session)
    adapter = ProcessingJobPersistenceAdapter(session)

    completed = adapter.complete_job(job_id, LEASE_OWNER, NOW)

    assert completed is not None
    assert completed.id == job_id
    assert completed.status is ProcessingJobState.SUCCEEDED
    assert completed.finished_at is not None
    assert _as_utc(completed.finished_at) == NOW
    assert completed.lease_owner is None
    assert completed.lease_expires_at is None
    assert completed.error_code is None
    assert completed.error_message is None


def test_complete_job_returns_none_for_wrong_owner(session: Session) -> None:
    job_id = _claim_pending_job(session)
    adapter = ProcessingJobPersistenceAdapter(session)

    assert adapter.complete_job(job_id, "other-worker", NOW) is None
    job = adapter.get_job_by_id(job_id)
    assert job is not None
    assert job.status is ProcessingJobState.PROCESSING
    assert job.lease_owner == LEASE_OWNER


def test_schedule_retry_keeps_processing_and_defers_lease(
    session: Session,
) -> None:
    job_id = _claim_pending_job(session)
    adapter = ProcessingJobPersistenceAdapter(session)
    retry_at = NOW + timedelta(seconds=60)

    retried = adapter.schedule_retry(
        job_id,
        LEASE_OWNER,
        lease_expires_at=retry_at,
        error_code=1000,
        error_message="synthetic transient failure",
    )

    assert retried is not None
    assert retried.status is ProcessingJobState.PROCESSING
    assert retried.lease_owner == LEASE_OWNER
    assert retried.lease_expires_at is not None
    assert _as_utc(retried.lease_expires_at) == retry_at
    assert retried.error_code == 1000
    assert retried.error_message == "synthetic transient failure"
    assert retried.finished_at is None


def test_schedule_retry_blocks_claim_until_lease_expires(session: Session) -> None:
    job_id = _claim_pending_job(session)
    adapter = ProcessingJobPersistenceAdapter(session)
    retry_at = NOW + timedelta(seconds=60)
    assert (
        adapter.schedule_retry(
            job_id,
            LEASE_OWNER,
            lease_expires_at=retry_at,
            error_code=1000,
            error_message="synthetic transient failure",
        )
        is not None
    )
    session.commit()

    assert (
        adapter.claim_next_job(
            "worker-2",
            LEASE_EXPIRES_AT,
            max_attempts=MAX_ATTEMPTS,
            now=NOW + timedelta(seconds=30),
        )
        is None
    )

    reclaimed = adapter.claim_next_job(
        "worker-2",
        LEASE_EXPIRES_AT,
        max_attempts=MAX_ATTEMPTS,
        now=NOW + timedelta(seconds=61),
    )
    assert reclaimed is not None
    assert reclaimed.id == job_id
    assert reclaimed.attempts == 2
    assert reclaimed.lease_owner == "worker-2"


def test_fail_job_marks_failed_and_clears_lease(session: Session) -> None:
    job_id = _claim_pending_job(session)
    adapter = ProcessingJobPersistenceAdapter(session)

    failed = adapter.fail_job(
        job_id,
        LEASE_OWNER,
        error_code=1001,
        error_message="synthetic permanent failure",
        finished_at=NOW,
    )

    assert failed is not None
    assert failed.status is ProcessingJobState.FAILED
    assert failed.finished_at is not None
    assert _as_utc(failed.finished_at) == NOW
    assert failed.lease_owner is None
    assert failed.lease_expires_at is None
    assert failed.error_code == 1001
    assert failed.error_message == "synthetic permanent failure"


def test_fail_job_returns_none_for_wrong_owner(session: Session) -> None:
    job_id = _claim_pending_job(session)
    adapter = ProcessingJobPersistenceAdapter(session)

    assert (
        adapter.fail_job(
            job_id,
            "other-worker",
            error_code=1001,
            error_message="synthetic permanent failure",
            finished_at=NOW,
        )
        is None
    )
    job = adapter.get_job_by_id(job_id)
    assert job is not None
    assert job.status is ProcessingJobState.PROCESSING


def test_retry_then_fail_after_reclaim_reaches_terminal_state(
    session: Session,
) -> None:
    job_id = _claim_pending_job(session)
    adapter = ProcessingJobPersistenceAdapter(session)
    assert (
        adapter.schedule_retry(
            job_id,
            LEASE_OWNER,
            lease_expires_at=NOW + timedelta(seconds=60),
            error_code=1000,
            error_message="synthetic transient failure",
        )
        is not None
    )
    session.commit()

    reclaimed = adapter.claim_next_job(
        "worker-2",
        LEASE_EXPIRES_AT,
        max_attempts=2,
        now=NOW + timedelta(seconds=61),
    )
    assert reclaimed is not None
    assert reclaimed.attempts == 2

    failed = adapter.fail_job(
        job_id,
        "worker-2",
        error_code=1001,
        error_message="synthetic permanent failure",
        finished_at=NOW + timedelta(seconds=61),
    )
    assert failed is not None
    assert failed.status is ProcessingJobState.FAILED
    assert failed.lease_owner is None
    assert failed.lease_expires_at is None

    assert (
        adapter.claim_next_job(
            "worker-3",
            LEASE_EXPIRES_AT,
            max_attempts=2,
            now=NOW + timedelta(minutes=10),
        )
        is None
    )
