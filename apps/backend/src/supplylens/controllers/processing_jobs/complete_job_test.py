from datetime import UTC, datetime
from unittest.mock import Mock, patch
from uuid import UUID

from supplylens.controllers.processing_jobs.complete_job import (
    CompleteJobCommand,
    complete_job,
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
        "status": ProcessingJobState.SUCCEEDED,
        "lease_owner": None,
        "lease_expires_at": None,
        "error_code": None,
        "error_message": None,
        "created_at": NOW,
        "started_at": NOW,
        "finished_at": NOW,
    }
    values.update(overrides)
    return PortJob(**values)  # type: ignore[arg-type]


def test_complete_job_returns_none_when_persistence_rejects() -> None:
    persistence = Mock(spec=ProcessingJobPersistence)
    persistence.complete_job.return_value = None

    assert (
        complete_job(
            persistence,
            CompleteJobCommand(job_id=42, lease_owner="worker-1"),
        )
        is None
    )


def test_complete_job_maps_succeeded_job() -> None:
    persistence = Mock(spec=ProcessingJobPersistence)
    persistence.complete_job.return_value = _port_job()

    with patch(
        "supplylens.controllers.processing_jobs.complete_job.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = NOW

        result = complete_job(
            persistence,
            CompleteJobCommand(job_id=42, lease_owner="worker-1"),
        )

    assert result is not None
    assert result.job.id == 42
    assert result.job.status is ProcessingJobState.SUCCEEDED
    persistence.complete_job.assert_called_once_with(
        job_id=42,
        lease_owner="worker-1",
        finished_at=NOW,
    )
