from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

from supplylens.controllers.processing_jobs.extend_lease import (
    ExtendLeaseCommand,
    extend_lease,
)
from supplylens.port.persistence.processing_job import ProcessingJobPersistence

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)


def test_extend_lease_forwards_computed_expiry() -> None:
    persistence = Mock(spec=ProcessingJobPersistence)
    persistence.extend_lease.return_value = True

    with patch(
        "supplylens.controllers.processing_jobs.extend_lease.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = NOW

        assert (
            extend_lease(
                persistence,
                ExtendLeaseCommand(
                    job_id=42,
                    lease_owner="worker-1",
                    lease_duration_minutes=5,
                ),
            )
            is True
        )

    persistence.extend_lease.assert_called_once_with(
        job_id=42,
        lease_owner="worker-1",
        lease_expires_at=NOW + timedelta(minutes=5),
    )


def test_extend_lease_returns_false_when_persistence_rejects() -> None:
    persistence = Mock(spec=ProcessingJobPersistence)
    persistence.extend_lease.return_value = False

    assert (
        extend_lease(
            persistence,
            ExtendLeaseCommand(
                job_id=42,
                lease_owner="worker-1",
                lease_duration_minutes=5,
            ),
        )
        is False
    )
