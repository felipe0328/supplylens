from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from supplylens.controllers.processing_jobs.mappers import (
    map_port_processing_job_to_controller_job,
)
from supplylens.controllers.processing_jobs.types import ProcessingJob
from supplylens.port.persistence.processing_job import ProcessingJobPersistence


@dataclass(frozen=True)
class ScheduleRetryCommand:
    job_id: int
    lease_owner: str
    backoff_seconds: int
    error_code: int
    error_message: str


@dataclass(frozen=True)
class ScheduleRetryResponse:
    job: ProcessingJob


def schedule_retry(
    persistence: ProcessingJobPersistence, req: ScheduleRetryCommand
) -> ScheduleRetryResponse | None:
    now = datetime.now(UTC)
    lease_expires_at = now + timedelta(seconds=req.backoff_seconds)
    scheduled_job = persistence.schedule_retry(
        job_id=req.job_id,
        lease_owner=req.lease_owner,
        lease_expires_at=lease_expires_at,
        error_code=req.error_code,
        error_message=req.error_message,
    )
    if scheduled_job is None:
        return None
    return ScheduleRetryResponse(
        job=map_port_processing_job_to_controller_job(scheduled_job)
    )
