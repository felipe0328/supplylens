from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import UUID

from supplylens.controllers.processing_jobs.constants import STUB_TRANSIENT_ERROR
from supplylens.controllers.processing_jobs.handle_processing_failure import (
    HandleProcessingFailureCommand,
    ProcessingFailureOutcome,
    handle_processing_failure,
)
from supplylens.domain.processing_job import ProcessingJobState
from supplylens.port.persistence.processing_job import ProcessingJob as PortJob
from supplylens.port.persistence.processing_job import ProcessingJobPersistence

DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)


def _port_job(**overrides: object) -> PortJob:
    values: dict[str, object] = {
        "id": 42,
        "document_uuid": DOCUMENT_ID,
        "attempts": 1,
        "status": ProcessingJobState.PROCESSING,
        "lease_owner": "worker-1",
        "lease_expires_at": NOW + timedelta(seconds=30),
        "error_code": STUB_TRANSIENT_ERROR,
        "error_message": "synthetic transient failure",
        "created_at": NOW,
        "started_at": NOW,
        "finished_at": None,
    }
    values.update(overrides)
    return PortJob(**values)  # type: ignore[arg-type]


def test_handle_processing_failure_schedules_retry_below_max_attempts() -> None:
    persistence = Mock(spec=ProcessingJobPersistence)
    persistence.schedule_retry.return_value = _port_job()

    result = handle_processing_failure(
        persistence,
        HandleProcessingFailureCommand(
            job_id=42,
            lease_owner="worker-1",
            attempts=1,
            max_attempts=3,
            backoff_seconds=30,
            error_code=STUB_TRANSIENT_ERROR,
            error_message="synthetic transient failure",
        ),
    )

    assert result is not None
    assert result.outcome is ProcessingFailureOutcome.RETRIED
    assert result.job.id == 42
    persistence.schedule_retry.assert_called_once()
    persistence.fail_job.assert_not_called()
    kwargs = persistence.schedule_retry.call_args.kwargs
    assert kwargs["error_code"] == STUB_TRANSIENT_ERROR
    assert kwargs["error_message"] == "synthetic transient failure"


def test_handle_processing_failure_fails_at_max_attempts() -> None:
    persistence = Mock(spec=ProcessingJobPersistence)
    persistence.fail_job.return_value = _port_job(
        attempts=3,
        status=ProcessingJobState.FAILED,
        lease_owner=None,
        lease_expires_at=None,
        finished_at=NOW,
    )

    result = handle_processing_failure(
        persistence,
        HandleProcessingFailureCommand(
            job_id=42,
            lease_owner="worker-1",
            attempts=3,
            max_attempts=3,
            backoff_seconds=30,
            error_code=STUB_TRANSIENT_ERROR,
            error_message="synthetic permanent failure",
        ),
    )

    assert result is not None
    assert result.outcome is ProcessingFailureOutcome.FAILED
    persistence.fail_job.assert_called_once()
    persistence.schedule_retry.assert_not_called()
    kwargs = persistence.fail_job.call_args.kwargs
    assert kwargs["error_code"] == STUB_TRANSIENT_ERROR
    assert kwargs["error_message"] == "synthetic permanent failure"


def test_handle_processing_failure_returns_none_when_retry_is_rejected() -> None:
    persistence = Mock(spec=ProcessingJobPersistence)
    persistence.schedule_retry.return_value = None

    assert (
        handle_processing_failure(
            persistence,
            HandleProcessingFailureCommand(
                job_id=42,
                lease_owner="worker-1",
                attempts=1,
                max_attempts=3,
                backoff_seconds=30,
                error_code=STUB_TRANSIENT_ERROR,
                error_message="synthetic transient failure",
            ),
        )
        is None
    )


def test_handle_processing_failure_returns_none_when_fail_is_rejected() -> None:
    persistence = Mock(spec=ProcessingJobPersistence)
    persistence.fail_job.return_value = None

    assert (
        handle_processing_failure(
            persistence,
            HandleProcessingFailureCommand(
                job_id=42,
                lease_owner="worker-1",
                attempts=3,
                max_attempts=3,
                backoff_seconds=30,
                error_code=STUB_TRANSIENT_ERROR,
                error_message="synthetic permanent failure",
            ),
        )
        is None
    )
    persistence.fail_job.assert_called_once()
    persistence.schedule_retry.assert_not_called()
