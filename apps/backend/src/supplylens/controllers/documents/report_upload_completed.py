from dataclasses import dataclass
from uuid import UUID

from supplylens.domain.documents import DocumentUploadStatus
from supplylens.port.persistence.documents import DocumentPersistence
from supplylens.port.persistence.processing_job import ProcessingJobPersistence
from supplylens.port.storage.storage import ObjectNotFoundError, ObjectStorage

from .exceptions import (
    DocumentInvalidContentTypeError,
    DocumentNotFoundError,
    InvalidJobProcessingID,
    StoreDocumentInvalidSizeError,
)
from .helpers import create_object_key
from .types import Document


@dataclass(frozen=True)
class ReportUploadCompletedCommandResponse:
    document: Document


def report_upload_completed(
    storage: ObjectStorage,
    document_persistence: DocumentPersistence,
    job_processing_persistence: ProcessingJobPersistence,
    id: UUID,
) -> ReportUploadCompletedCommandResponse:

    try:
        stored_document = storage.head_object(create_object_key(id))
    except ObjectNotFoundError:
        raise DocumentNotFoundError(
            f"Document with ID {id} not found in object storage"
        )

    persistence_document = document_persistence.get_document_data(id)
    if persistence_document is None:
        raise DocumentNotFoundError(
            f"Document with ID {id} not found in object storage"
        )

    if stored_document.size_bytes != persistence_document.size_bytes:
        document_persistence.update_document_upload_status(
            id=id, new_status=DocumentUploadStatus.FAILED
        )
        storage.delete_object(create_object_key(id))
        raise StoreDocumentInvalidSizeError(
            f"Document with ID {id} has inconsistent size information"
        )

    if stored_document.content_type != "application/pdf":
        document_persistence.update_document_upload_status(
            id=id, new_status=DocumentUploadStatus.FAILED
        )
        storage.delete_object(create_object_key(id))
        raise DocumentInvalidContentTypeError(
            f"Document with ID {id} has invalid content type: {stored_document.content_type}"  # noqa: E501
        )

    document = document_persistence.update_document_upload_status(
        id=id, new_status=DocumentUploadStatus.UPLOADED
    )

    new_job_id: int = job_processing_persistence.enqueue_new_job(document.id)
    if new_job_id <= 0:
        raise InvalidJobProcessingID(
            f"Document {id} has received wrong job id: {new_job_id} from database "
        )

    return ReportUploadCompletedCommandResponse(
        document=Document(
            id=document.id,
            filename=document.filename,
            size_bytes=document.size_bytes,
            document_type=document.document_type,
            page_count=document.page_count,
            upload_status=document.upload_status,
            processing_status=document.processing_status,
            created_at=document.created_at,
            uploaded_at=document.uploaded_at,
            processed_at=document.processed_at,
        )
    )
