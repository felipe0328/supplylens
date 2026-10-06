from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

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
