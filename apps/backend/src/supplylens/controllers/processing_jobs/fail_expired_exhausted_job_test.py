from datetime import UTC, datetime
from unittest.mock import Mock, patch
from uuid import UUID

from supplylens.controllers.processing_jobs.constants import EXHAUSTED_LEASE_ERROR
from supplylens.controllers.processing_jobs.fail_expired_exhausted_job import (
    FailExpiredExhaustedJobCommand,
    fail_expired_exhausted_job,
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
        "attempts": 3,
        "status": ProcessingJobState.FAILED,
        "lease_owner": None,
        "lease_expires_at": None,
        "error_code": EXHAUSTED_LEASE_ERROR,
        "error_message": "Job exceeded maximum attempts after lease expiry",
        "created_at": NOW,
        "started_at": NOW,
        "finished_at": NOW,
    }
    values.update(overrides)
    return PortJob(**values)  # type: ignore[arg-type]


def test_fail_expired_exhausted_job_returns_none_when_none_due() -> None:
    persistence = Mock(spec=ProcessingJobPersistence)
    persistence.fail_expired_exhausted_job.return_value = None

    assert (
        fail_expired_exhausted_job(
            persistence,
            FailExpiredExhaustedJobCommand(
                max_attempts=3,
                error_code=EXHAUSTED_LEASE_ERROR,
                error_message="Job exceeded maximum attempts after lease expiry",
            ),
        )
        is None
    )


def test_fail_expired_exhausted_job_maps_failed_job() -> None:
    persistence = Mock(spec=ProcessingJobPersistence)
    persistence.fail_expired_exhausted_job.return_value = _port_job()

    with patch(
        "supplylens.controllers.processing_jobs.fail_expired_exhausted_job.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = NOW

        result = fail_expired_exhausted_job(
            persistence,
            FailExpiredExhaustedJobCommand(
                max_attempts=3,
                error_code=EXHAUSTED_LEASE_ERROR,
                error_message="Job exceeded maximum attempts after lease expiry",
            ),
        )

    assert result is not None
    assert result.job.status is ProcessingJobState.FAILED
    assert result.job.error_code == EXHAUSTED_LEASE_ERROR
    persistence.fail_expired_exhausted_job.assert_called_once_with(
        max_attempts=3,
        now=NOW,
        finished_at=NOW,
        error_code=EXHAUSTED_LEASE_ERROR,
        error_message="Job exceeded maximum attempts after lease expiry",
    )
