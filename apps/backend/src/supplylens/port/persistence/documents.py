from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from supplylens.domain.documents import DocumentProcessingStatus, DocumentUploadStatus


@dataclass(frozen=True)
class Document:
    id: UUID
    filename: str
    size_bytes: int
    document_type: str | None
    page_count: int | None
    upload_status: DocumentUploadStatus
    processing_status: DocumentProcessingStatus
    created_at: datetime
    uploaded_at: datetime | None
    processed_at: datetime | None


class DocumentPersistence(Protocol):
    def create_new_document(
        self,
        id: UUID,
        filename: str,
        size_bytes: int,
    ) -> Document: ...

    def delete_document(self, id: UUID) -> None: ...

    def get_document_data(self, id: UUID) -> Document | None: ...

    def update_document_upload_status(
        self, id: UUID, new_status: DocumentUploadStatus
    ) -> Document: ...
