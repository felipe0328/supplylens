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
from supplylens.controllers.processing_jobs.constants import (
    EXHAUSTED_LEASE_ERROR,
    EXTRACTION_TRANSIENT_ERROR,
)
from supplylens.controllers.processing_jobs.extend_lease import (
    ExtendLeaseCommand,
    extend_lease,
)
from supplylens.controllers.processing_jobs.fail_expired_exhausted_job import (
    FailExpiredExhaustedJobCommand,
    fail_expired_exhausted_job,
)
from supplylens.controllers.processing_jobs.handle_processing_failure import (
    HandleProcessingFailureCommand,
    handle_processing_failure,
)
from supplylens.database.database import get_session
from supplylens.helpers.lease_heartbeat import LeaseLostError, run_with_lease_heartbeat
from supplylens.worker.process_job import process_claimed_job


def run() -> None:
    settings = WorkerSettings.from_env()
    lease_owner = settings.worker_id or f"worker-{uuid4()}"

    while True:
        with contextmanager(get_session)() as session:
            persistence = ProcessingJobPersistenceAdapter(session)
            finalized = fail_expired_exhausted_job(
                persistence,
                FailExpiredExhaustedJobCommand(
                    max_attempts=settings.max_attempts,
                    error_code=EXHAUSTED_LEASE_ERROR,
                    error_message=("Job exceeded maximum attempts after lease expiry"),
                ),
            )
            if finalized is not None:
                print(
                    f"Finalized exhausted job: {finalized.job.id} "
                    f"status={finalized.job.status.value}"
                )

            claimed = claim_next_job(
                persistence=persistence,
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
            extended = extend_lease(
                ProcessingJobPersistenceAdapter(session),
                ExtendLeaseCommand(
                    job_id=job.id,
                    lease_owner=lease_owner,
                    lease_duration_minutes=settings.lease_duration_minutes,
                ),
            )
        if not extended:
            print(f"Lost lease for job {job.id}; skipping")
            time.sleep(settings.interval_seconds)
            continue

        def renew_lease() -> bool:
            with contextmanager(get_session)() as session:
                return extend_lease(
                    ProcessingJobPersistenceAdapter(session),
                    ExtendLeaseCommand(
                        job_id=job.id,
                        lease_owner=lease_owner,
                        lease_duration_minutes=settings.lease_duration_minutes,
                    ),
                )

        try:
            run_with_lease_heartbeat(
                lambda: process_claimed_job(job),
                renew_lease,
                interval_seconds=settings.heartbeat_interval_seconds,
            )
        except LeaseLostError:
            print(f"Lost lease for job {job.id} during processing; skipping finish")
            time.sleep(settings.interval_seconds)
            continue
        except Exception as exc:
            with contextmanager(get_session)() as session:
                failure = handle_processing_failure(
                    ProcessingJobPersistenceAdapter(session),
                    HandleProcessingFailureCommand(
                        job_id=job.id,
                        lease_owner=lease_owner,
                        attempts=job.attempts,
                        max_attempts=settings.max_attempts,
                        backoff_seconds=settings.retry_backoff_seconds,
                        error_code=EXTRACTION_TRANSIENT_ERROR,
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
            continue

        with contextmanager(get_session)() as session:
            completed = complete_job(
                ProcessingJobPersistenceAdapter(session),
                CompleteJobCommand(job_id=job.id, lease_owner=lease_owner),
            )
        if completed is None:
            print(f"Could not complete job {job.id}")
        else:
            print(f"Completed job: {job.id}")

        time.sleep(settings.interval_seconds)


if __name__ == "__main__":
    run()
