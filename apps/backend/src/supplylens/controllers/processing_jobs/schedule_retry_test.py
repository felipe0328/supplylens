from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch
from uuid import UUID

from supplylens.controllers.processing_jobs.schedule_retry import (
    ScheduleRetryCommand,
    schedule_retry,
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
        "error_code": 1000,
        "error_message": "synthetic transient failure",
        "created_at": NOW,
        "started_at": NOW,
        "finished_at": None,
    }
    values.update(overrides)
    return PortJob(**values)  # type: ignore[arg-type]


def test_schedule_retry_returns_none_when_persistence_rejects() -> None:
    persistence = Mock(spec=ProcessingJobPersistence)
    persistence.schedule_retry.return_value = None

    assert (
        schedule_retry(
            persistence,
            ScheduleRetryCommand(
                job_id=42,
                lease_owner="worker-1",
                backoff_seconds=30,
                error_code=1000,
                error_message="synthetic transient failure",
            ),
        )
        is None
    )


def test_schedule_retry_forwards_backoff_as_lease_expiry() -> None:
    persistence = Mock(spec=ProcessingJobPersistence)
    persistence.schedule_retry.return_value = _port_job()

    with patch(
        "supplylens.controllers.processing_jobs.schedule_retry.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = NOW

        result = schedule_retry(
            persistence,
            ScheduleRetryCommand(
                job_id=42,
                lease_owner="worker-1",
                backoff_seconds=30,
                error_code=1000,
                error_message="synthetic transient failure",
            ),
        )

    assert result is not None
    assert result.job.status is ProcessingJobState.PROCESSING
    persistence.schedule_retry.assert_called_once_with(
        job_id=42,
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(seconds=30),
        error_code=1000,
        error_message="synthetic transient failure",
    )
