from dataclasses import dataclass
from datetime import datetime
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
