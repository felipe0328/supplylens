from dataclasses import dataclass
from datetime import UTC, datetime

from supplylens.controllers.processing_jobs.mappers import (
    map_port_processing_job_to_controller_job,
)
from supplylens.controllers.processing_jobs.types import ProcessingJob
from supplylens.port.persistence.processing_job import ProcessingJobPersistence


@dataclass(frozen=True)
class FailJobCommand:
    job_id: int
    lease_owner: str
    error_code: int
    error_message: str


@dataclass(frozen=True)
class FailJobResponse:
    job: ProcessingJob


def fail_job(
    persistence: ProcessingJobPersistence, req: FailJobCommand
) -> FailJobResponse | None:
    now = datetime.now(UTC)
    failed_job = persistence.fail_job(
        job_id=req.job_id,
        lease_owner=req.lease_owner,
        error_code=req.error_code,
        error_message=req.error_message,
        finished_at=now,
    )
    if failed_job is None:
        return None
    return FailJobResponse(job=map_port_processing_job_to_controller_job(failed_job))
