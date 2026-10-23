from dataclasses import dataclass
from datetime import UTC, datetime

from supplylens.controllers.processing_jobs.mappers import (
    map_port_processing_job_to_controller_job,
)
from supplylens.controllers.processing_jobs.types import ProcessingJob
from supplylens.port.persistence.processing_job import ProcessingJobPersistence


@dataclass(frozen=True)
class FailExpiredExhaustedJobCommand:
    max_attempts: int
    error_code: int
    error_message: str


@dataclass(frozen=True)
class FailExpiredExhaustedJobResponse:
    job: ProcessingJob


def fail_expired_exhausted_job(
    persistence: ProcessingJobPersistence, req: FailExpiredExhaustedJobCommand
) -> FailExpiredExhaustedJobResponse | None:
    now = datetime.now(UTC)
    failed_job = persistence.fail_expired_exhausted_job(
        max_attempts=req.max_attempts,
        now=now,
        finished_at=now,
        error_code=req.error_code,
        error_message=req.error_message,
    )
    if failed_job is None:
        return None
    return FailExpiredExhaustedJobResponse(
        job=map_port_processing_job_to_controller_job(failed_job)
    )
