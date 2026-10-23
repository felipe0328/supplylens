from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from supplylens.domain.processing_job import ProcessingJobState


@dataclass(frozen=True)
class ProcessingJob:
    id: int
    document_uuid: UUID
    attempts: int
    status: ProcessingJobState
    lease_owner: str | None
    lease_expires_at: datetime | None
    error_code: int | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class ProcessingJobPersistence(Protocol):
    def enqueue_new_job(self, document_uuid: UUID) -> int: ...

    def get_job_by_id(self, id: int) -> ProcessingJob | None: ...
    def get_job_by_document_uuid(self, document_uuid: UUID) -> ProcessingJob | None: ...

    def claim_next_job(
        self,
        lease_owner: str,
        lease_expires_at: datetime,
        *,
        max_attempts: int,
        now: datetime,
    ) -> ProcessingJob | None: ...

    def extend_lease(
        self, job_id: int, lease_owner: str, lease_expires_at: datetime
    ) -> bool: ...

    def complete_job(
        self,
        job_id: int,
        lease_owner: str,
        finished_at: datetime,
    ) -> ProcessingJob | None: ...

    def schedule_retry(
        self,
        job_id: int,
        lease_owner: str,
        *,
        lease_expires_at: datetime,
        error_code: int,
        error_message: str,
    ) -> ProcessingJob | None: ...

    def fail_job(
        self,
        job_id: int,
        lease_owner: str,
        *,
        error_code: int,
        error_message: str,
        finished_at: datetime,
    ) -> ProcessingJob | None: ...
