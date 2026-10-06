from dataclasses import dataclass
from uuid import UUID

from supplylens.port.persistence.documents import DocumentPersistence

from .exceptions import DocumentNotFoundError
from .types import Document


@dataclass(frozen=True)
class GetDocumentDataCommandResponse:
    document: Document


def get_document_data(
    persistence: DocumentPersistence, id: UUID
) -> GetDocumentDataCommandResponse:
    document = persistence.get_document_data(id=id)
    if document is None:
        raise DocumentNotFoundError(f"Document with ID {id} not found")

    return GetDocumentDataCommandResponse(
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
