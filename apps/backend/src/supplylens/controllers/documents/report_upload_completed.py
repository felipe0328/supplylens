from dataclasses import dataclass
from uuid import UUID

from supplylens.domain.documents import DocumentUploadStatus
from supplylens.port.persistence.documents import Document, DocumentPersistence
from supplylens.port.persistence.processing_job import ProcessingJobPersistence
from supplylens.port.storage.storage import (
    ObjectNotFoundError,
    ObjectStorage,
    StorageUnavailableError,
)

from .exceptions import (
    DocumentInvalidContentTypeError,
    DocumentNotFoundError,
    InvalidJobProcessingID,
    StoreDocumentInvalidSizeError,
)
from .helpers import create_object_key


@dataclass(frozen=True)
class ReportUploadCompletedCommandResponse:
    document: Document


@dataclass(frozen=True)
class ReportUploadCompletedRejection:
    """A finished completion failure whose FAILED row must be committed."""

    error: Exception


def report_upload_completed(
    storage: ObjectStorage,
    document_persistence: DocumentPersistence,
    job_processing_persistence: ProcessingJobPersistence,
    id: UUID,
) -> ReportUploadCompletedCommandResponse | ReportUploadCompletedRejection:
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
        return _reject_failed_upload(
            document_persistence,
            storage,
            id,
            StoreDocumentInvalidSizeError(
                f"Document with ID {id} has inconsistent size information"
            ),
        )

    if stored_document.content_type != "application/pdf":
        return _reject_failed_upload(
            document_persistence,
            storage,
            id,
            DocumentInvalidContentTypeError(
                f"Document with ID {id} has invalid content type: "
                f"{stored_document.content_type}"
            ),
        )

    document = document_persistence.update_document_upload_status(
        id=id, new_status=DocumentUploadStatus.UPLOADED
    )

    new_job_id: int = job_processing_persistence.enqueue_new_job(document.id)
    if new_job_id <= 0:
        raise InvalidJobProcessingID(
            f"Document {id} has received wrong job id: {new_job_id} from database "
        )

    return ReportUploadCompletedCommandResponse(document=document)


def _reject_failed_upload(
    document_persistence: DocumentPersistence,
    storage: ObjectStorage,
    document_id: UUID,
    error: Exception,
) -> ReportUploadCompletedRejection:
    document_persistence.update_document_upload_status(
        id=document_id, new_status=DocumentUploadStatus.FAILED
    )
    try:
        storage.delete_object(create_object_key(document_id))
    except StorageUnavailableError as exc:
        return ReportUploadCompletedRejection(error=exc)
    return ReportUploadCompletedRejection(error=error)
