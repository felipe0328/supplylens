from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from supplylens.domain.processing_job import ProcessingJobState
from supplylens.models.document import Document
from supplylens.models.processing_job import ProcessingJob as ProcessingJobModel
from supplylens.port.persistence.processing_job import (
    ProcessingJob as AbstractProcessingJob,
)
from supplylens.port.persistence.processing_job import ProcessingJobPersistence

from .mappers import map_model_processing_job_to_abstraction


class ProcessingJobPersistenceAdapter(ProcessingJobPersistence):
    """Lock and flush job writes; the caller owns commit and rollback."""

    _session: Session

    def __init__(self, session: Session) -> None:
        self._session = session

    def enqueue_new_job(self, document_uuid: UUID) -> int:
        existing_document = self._session.scalar(
            select(Document.id)
            .where(
                Document.id == document_uuid,
                Document.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if existing_document is None:
            raise ValueError(f"Document {document_uuid} not found")

        existing_job: AbstractProcessingJob | None = self.get_job_by_document_uuid(
            document_uuid
        )

        if existing_job is not None:
            return existing_job.id

        new_job: ProcessingJobModel = ProcessingJobModel(
            document_id=document_uuid,
        )

        self._session.add(new_job)
        self._session.flush()
        return new_job.id

    def get_job_by_id(self, id: int) -> AbstractProcessingJob | None:
        processing_job: ProcessingJobModel | None = self._session.get(
            ProcessingJobModel, id
        )

        return map_model_processing_job_to_abstraction(processing_job)

    def get_job_by_document_uuid(
        self, document_uuid: UUID
    ) -> AbstractProcessingJob | None:
        statement = select(ProcessingJobModel).where(
            ProcessingJobModel.document_id == document_uuid
        )
        processing_job: ProcessingJobModel | None = self._session.scalar(statement)
        return map_model_processing_job_to_abstraction(processing_job)

    def claim_next_job(
        self,
        lease_owner: str,
        lease_expires_at: datetime,
        *,
        max_attempts: int,
        now: datetime,
    ) -> AbstractProcessingJob | None:
        # Enqueued jobs start at attempts=1 (first try). Reclaims of an expired
        # lease increment attempts; stop once attempts has reached max_attempts.
        statement = (
            select(ProcessingJobModel)
            .where(
                or_(
                    and_(
                        ProcessingJobModel.status == ProcessingJobState.PENDING,
                        ProcessingJobModel.attempts <= max_attempts,
                    ),
                    and_(
                        ProcessingJobModel.status == ProcessingJobState.PROCESSING,
                        ProcessingJobModel.lease_expires_at.is_not(None),
                        ProcessingJobModel.lease_expires_at < now,
                        ProcessingJobModel.attempts < max_attempts,
                    ),
                ),
            )
            .order_by(
                ProcessingJobModel.created_at.asc(),
                ProcessingJobModel.id.asc(),
            )
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        job = self._session.scalar(statement)
        if job is None:
            return None

        if job.status == ProcessingJobState.PROCESSING:
            job.attempts = job.attempts + 1
        job.status = ProcessingJobState.PROCESSING
        job.lease_owner = lease_owner
        job.lease_expires_at = lease_expires_at
        job.started_at = now
        job.finished_at = None
        job.error_code = None
        job.error_message = None
        self._session.flush()
        return map_model_processing_job_to_abstraction(job)
