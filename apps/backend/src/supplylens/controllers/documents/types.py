from dataclasses import dataclass
from datetime import datetime
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
