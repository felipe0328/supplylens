from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from supplylens.controllers.processing_jobs.mappers import (
    map_port_processing_job_to_controller_job,
)
from supplylens.controllers.processing_jobs.types import ProcessingJob
from supplylens.port.persistence.processing_job import ProcessingJobPersistence


@dataclass(frozen=True)
class ClaimNextJobCommand:
    lease_owner: str
    max_attempts: int
    lease_duration_minutes: int


@dataclass(frozen=True)
class ClaimNextJobCommandResult:
    job: ProcessingJob


def claim_next_job(
    persistence: ProcessingJobPersistence, req: ClaimNextJobCommand
) -> ClaimNextJobCommandResult | None:
    now = datetime.now(UTC)
    lease_expires_at = now + timedelta(minutes=req.lease_duration_minutes)
    job = persistence.claim_next_job(
        lease_owner=req.lease_owner,
        lease_expires_at=lease_expires_at,
        max_attempts=req.max_attempts,
        now=now,
    )
    if job is None:
        return None
    return ClaimNextJobCommandResult(job=map_port_processing_job_to_controller_job(job))
