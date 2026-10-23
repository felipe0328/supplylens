from dataclasses import dataclass
from enum import StrEnum

from supplylens.controllers.processing_jobs.fail_job import FailJobCommand, fail_job
from supplylens.controllers.processing_jobs.schedule_retry import (
    ScheduleRetryCommand,
    schedule_retry,
)
from supplylens.controllers.processing_jobs.types import ProcessingJob
from supplylens.port.persistence.processing_job import ProcessingJobPersistence


class ProcessingFailureOutcome(StrEnum):
    RETRIED = "retried"
    FAILED = "failed"


@dataclass(frozen=True)
class HandleProcessingFailureCommand:
    job_id: int
    lease_owner: str
    attempts: int
    max_attempts: int
    backoff_seconds: int
    error_code: int
    error_message: str


@dataclass(frozen=True)
class HandleProcessingFailureResult:
    outcome: ProcessingFailureOutcome
    job: ProcessingJob


def handle_processing_failure(
    persistence: ProcessingJobPersistence, req: HandleProcessingFailureCommand
) -> HandleProcessingFailureResult | None:
    if req.attempts >= req.max_attempts:
        failed = fail_job(
            persistence,
            FailJobCommand(
                job_id=req.job_id,
                lease_owner=req.lease_owner,
                error_code=req.error_code,
                error_message=req.error_message,
            ),
        )
        if failed is None:
            return None
        return HandleProcessingFailureResult(
            outcome=ProcessingFailureOutcome.FAILED,
            job=failed.job,
        )

    retried = schedule_retry(
        persistence,
        ScheduleRetryCommand(
            job_id=req.job_id,
            lease_owner=req.lease_owner,
            backoff_seconds=req.backoff_seconds,
            error_code=req.error_code,
            error_message=req.error_message,
        ),
    )
    if retried is None:
        return None
    return HandleProcessingFailureResult(
        outcome=ProcessingFailureOutcome.RETRIED,
        job=retried.job,
    )
