import time
from contextlib import contextmanager
from uuid import uuid4

from supplylens.adapters.persistence.processing_job import (
    ProcessingJobPersistenceAdapter,
)
from supplylens.config import WorkerSettings
from supplylens.controllers.processing_jobs.claim_next_job import (
    ClaimNextJobCommand,
    claim_next_job,
)
from supplylens.controllers.processing_jobs.complete_job import (
    CompleteJobCommand,
    complete_job,
)
from supplylens.controllers.processing_jobs.constants import STUB_TRANSIENT_ERROR
from supplylens.controllers.processing_jobs.extend_lease import (
    ExtendLeaseCommand,
    extend_lease,
)
from supplylens.controllers.processing_jobs.handle_processing_failure import (
    HandleProcessingFailureCommand,
    handle_processing_failure,
)
from supplylens.database.database import get_session
from supplylens.worker.stub import process_claimed_job


def run() -> None:
    settings = WorkerSettings.from_env()
    lease_owner = settings.worker_id or f"worker-{uuid4()}"

    while True:
        with contextmanager(get_session)() as session:
            claimed = claim_next_job(
                persistence=ProcessingJobPersistenceAdapter(session),
                req=ClaimNextJobCommand(
                    lease_owner=lease_owner,
                    max_attempts=settings.max_attempts,
                    lease_duration_minutes=settings.lease_duration_minutes,
                ),
            )

        if claimed is None:
            print(f"No job claimed by worker {lease_owner}")
            time.sleep(settings.interval_seconds)
            continue

        job = claimed.job
        print(f"Claimed job: {job.id} by worker {lease_owner}")

        with contextmanager(get_session)() as session:
            persistence = ProcessingJobPersistenceAdapter(session)
            extended = extend_lease(
                persistence,
                ExtendLeaseCommand(
                    job_id=job.id,
                    lease_owner=lease_owner,
                    lease_duration_minutes=settings.lease_duration_minutes,
                ),
            )
            if not extended:
                print(f"Lost lease for job {job.id}; skipping")
            else:
                try:
                    process_claimed_job(job)
                    completed = complete_job(
                        persistence,
                        CompleteJobCommand(job_id=job.id, lease_owner=lease_owner),
                    )
                    if completed is None:
                        print(f"Could not complete job {job.id}")
                    else:
                        print(f"Completed job: {job.id}")
                except Exception as exc:
                    failure = handle_processing_failure(
                        persistence,
                        HandleProcessingFailureCommand(
                            job_id=job.id,
                            lease_owner=lease_owner,
                            attempts=job.attempts,
                            max_attempts=settings.max_attempts,
                            backoff_seconds=settings.retry_backoff_seconds,
                            error_code=STUB_TRANSIENT_ERROR,
                            error_message=str(exc)[:500],
                        ),
                    )
                    if failure is None:
                        print(f"Could not record failure for job {job.id}")
                    else:
                        print(
                            f"Job {job.id} outcome={failure.outcome.value} "
                            f"status={failure.job.status.value}"
                        )

        time.sleep(settings.interval_seconds)


if __name__ == "__main__":
    run()
