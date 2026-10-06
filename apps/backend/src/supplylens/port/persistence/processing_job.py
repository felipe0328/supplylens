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
