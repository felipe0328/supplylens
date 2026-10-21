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
from supplylens.database.database import get_session


def run() -> None:
    settings = WorkerSettings.from_env()
    lease_owner = settings.worker_id or f"worker-{uuid4()}"

    while True:
        with contextmanager(get_session)() as session:
            result = claim_next_job(
                persistence=ProcessingJobPersistenceAdapter(session),
                req=ClaimNextJobCommand(
                    lease_owner=lease_owner,
                    max_attempts=settings.max_attempts,
                    lease_duration_minutes=settings.lease_duration_minutes,
                ),
            )
            if result is None:
                print(f"No job claimed by worker {lease_owner}")
            else:
                print(f"Claimed job: {result.job.id} by worker {lease_owner}")

        time.sleep(settings.interval_seconds)


if __name__ == "__main__":
    run()
