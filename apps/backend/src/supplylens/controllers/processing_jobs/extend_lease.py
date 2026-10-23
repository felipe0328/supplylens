from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from supplylens.port.persistence.processing_job import ProcessingJobPersistence


@dataclass(frozen=True)
class ExtendLeaseCommand:
    job_id: int
    lease_owner: str
    lease_duration_minutes: int


def extend_lease(
    persistence: ProcessingJobPersistence, req: ExtendLeaseCommand
) -> bool:
    now = datetime.now(UTC)
    lease_expires_at = now + timedelta(minutes=req.lease_duration_minutes)
    return persistence.extend_lease(
        job_id=req.job_id,
        lease_owner=req.lease_owner,
        lease_expires_at=lease_expires_at,
    )
