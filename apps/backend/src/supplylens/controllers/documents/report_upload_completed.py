from dataclasses import dataclass
from uuid import UUID

from supplylens.domain.documents import DocumentUploadStatus
from supplylens.port.persistence.documents import DocumentPersistence
from supplylens.port.storage.storage import ObjectNotFoundError, ObjectStorage

from .exceptions import (
    DocumentInvalidContentTypeError,
    DocumentNotFoundError,
    StoreDocumentInvalidSizeError,
)
from .helpers import create_object_key
from .types import Document


@dataclass(frozen=True)
class ReportUploadCompletedCommandResponse:
    document: Document


def report_upload_completed(
    storage: ObjectStorage,
    persistence: DocumentPersistence,
    id: UUID,
) -> ReportUploadCompletedCommandResponse:

    try:
        stored_document = storage.head_object(create_object_key(id))
    except ObjectNotFoundError:
        raise DocumentNotFoundError(
            f"Document with ID {id} not found in object storage"
        )

    persistence_document = persistence.get_document_data(id)
    if persistence_document is None:
        raise DocumentNotFoundError(
            f"Document with ID {id} not found in object storage"
        )

    if stored_document.size_bytes != persistence_document.size_bytes:
        persistence.update_document_upload_status(
            id=id, new_status=DocumentUploadStatus.FAILED
        )
        persistence.commit()
        storage.delete_object(create_object_key(id))
        raise StoreDocumentInvalidSizeError(
            f"Document with ID {id} has inconsistent size information"
        )

    if stored_document.content_type != "application/pdf":
        persistence.update_document_upload_status(
            id=id, new_status=DocumentUploadStatus.FAILED
        )
        persistence.commit()
        storage.delete_object(create_object_key(id))
        raise DocumentInvalidContentTypeError(
            f"Document with ID {id} has invalid content type: {stored_document.content_type}"  # noqa: E501
        )

    document = persistence.update_document_upload_status(
        id=id, new_status=DocumentUploadStatus.UPLOADED
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
