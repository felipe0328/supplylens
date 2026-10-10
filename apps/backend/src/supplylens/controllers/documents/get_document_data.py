from dataclasses import dataclass
from uuid import UUID

from supplylens.port.persistence.documents import Document, DocumentPersistence

from .exceptions import DocumentNotFoundError


@dataclass(frozen=True)
class GetDocumentDataCommandResponse:
    document: Document


def get_document_data(
    persistence: DocumentPersistence, id: UUID
) -> GetDocumentDataCommandResponse:
    document = persistence.get_document_data(id=id)
    if document is None:
        raise DocumentNotFoundError(f"Document with ID {id} not found")

    return GetDocumentDataCommandResponse(document=document)
