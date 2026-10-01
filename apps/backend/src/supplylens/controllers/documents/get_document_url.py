from dataclasses import dataclass
from uuid import UUID

from supplylens.domain.documents import DocumentUploadStatus
from supplylens.port.persistence.documents import DocumentPersistence
from supplylens.port.storage.storage import ObjectStorage

from .exceptions import DocumentNotFoundError, DocumentNotUploadedError
from .helpers import create_object_key


@dataclass(frozen=True)
class GetDocumentURLCommandResponse:
    id: UUID
    url: str
    expires_in_seconds: int


def get_document_url(
    storage: ObjectStorage, persistence: DocumentPersistence, id: UUID
) -> GetDocumentURLCommandResponse:

    document = persistence.get_document_data(id)
    if document is None:
        raise DocumentNotFoundError(f"Document with ID {id} not found")
    if document.upload_status is not DocumentUploadStatus.UPLOADED:
        raise DocumentNotUploadedError(f"Document with ID {id} not uploaded")

    object_key = create_object_key(id)
    document_url = storage.create_download_url(object_key)

    return GetDocumentURLCommandResponse(
        id=document.id,
        url=document_url.url,
        expires_in_seconds=document_url.expires_in_seconds,
    )
