from supplylens.models.document import Document as ModelDocument
from supplylens.models.processing_job import ProcessingJob as ModelProcessingJob
from supplylens.port.persistence.documents import Document as AbstractDocument
from supplylens.port.persistence.processing_job import (
    ProcessingJob as AbstractProcessingJob,
)


def map_model_document_to_abstraction(
    model_document: ModelDocument,
) -> AbstractDocument:
    return AbstractDocument(
        id=model_document.id,
        filename=model_document.filename,
        size_bytes=model_document.size_bytes,
        document_type=model_document.document_type,
        page_count=model_document.page_count,
        upload_status=model_document.upload_status,
        processing_status=model_document.processing_status,
        created_at=model_document.created_at,
        uploaded_at=model_document.uploaded_at,
        processed_at=model_document.processed_at,
    )


def map_model_processing_job_to_abstraction(
    model_processing_job: ModelProcessingJob | None,
) -> AbstractProcessingJob | None:
    if model_processing_job is None:
        return None
    return AbstractProcessingJob(
        id=model_processing_job.id,
        document_uuid=model_processing_job.document_id,
        attempts=model_processing_job.attempts,
        status=model_processing_job.status,
        lease_owner=model_processing_job.lease_owner,
        lease_expires_at=model_processing_job.lease_expires_at,
        error_code=model_processing_job.error_code,
        error_message=model_processing_job.error_message,
        created_at=model_processing_job.created_at,
        started_at=model_processing_job.started_at,
        finished_at=model_processing_job.finished_at,
    )
