from dataclasses import dataclass
from datetime import UTC, datetime

from supplylens.controllers.processing_jobs.mappers import (
    map_port_processing_job_to_controller_job,
)
from supplylens.controllers.processing_jobs.types import ProcessingJob
from supplylens.port.persistence.processing_job import ProcessingJobPersistence


@dataclass(frozen=True)
class CompleteJobCommand:
    job_id: int
    lease_owner: str


@dataclass(frozen=True)
class CompleteJobResponse:
    job: ProcessingJob


def complete_job(
    persistence: ProcessingJobPersistence, req: CompleteJobCommand
) -> CompleteJobResponse | None:
    now = datetime.now(UTC)
    completed_job = persistence.complete_job(
        job_id=req.job_id,
        lease_owner=req.lease_owner,
        finished_at=now,
    )
    if completed_job is None:
        return None
    return CompleteJobResponse(
        job=map_port_processing_job_to_controller_job(completed_job)
    )
