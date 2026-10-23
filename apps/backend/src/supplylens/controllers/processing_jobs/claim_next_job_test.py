from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import UUID

from supplylens.controllers.processing_jobs.claim_next_job import (
    ClaimNextJobCommand,
    claim_next_job,
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
        "lease_expires_at": NOW + timedelta(minutes=5),
        "error_code": None,
        "error_message": None,
        "created_at": NOW,
        "started_at": NOW,
        "finished_at": None,
    }
    values.update(overrides)
    return PortJob(**values)  # type: ignore[arg-type]


def test_claim_next_job_returns_none_when_persistence_has_no_work() -> None:
    persistence = Mock(spec=ProcessingJobPersistence)
    persistence.claim_next_job.return_value = None

    result = claim_next_job(
        persistence,
        ClaimNextJobCommand(
            lease_owner="worker-1",
            max_attempts=3,
            lease_duration_minutes=5,
        ),
    )

    assert result is None
    persistence.claim_next_job.assert_called_once()
    kwargs = persistence.claim_next_job.call_args.kwargs
    assert kwargs["lease_owner"] == "worker-1"
    assert kwargs["max_attempts"] == 3
    assert kwargs["lease_expires_at"] - kwargs["now"] == timedelta(minutes=5)


def test_claim_next_job_maps_claimed_job() -> None:
    persistence = Mock(spec=ProcessingJobPersistence)
    persistence.claim_next_job.return_value = _port_job()

    result = claim_next_job(
        persistence,
        ClaimNextJobCommand(
            lease_owner="worker-1",
            max_attempts=3,
            lease_duration_minutes=5,
        ),
    )

    assert result is not None
    assert result.job.id == 42
    assert result.job.document_uuid == DOCUMENT_ID
    assert result.job.status is ProcessingJobState.PROCESSING
    assert result.job.lease_owner == "worker-1"
