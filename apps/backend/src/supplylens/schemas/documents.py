from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, PositiveInt

from supplylens.domain.documents import DocumentProcessingStatus, DocumentUploadStatus


class CreateUploadIntentRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: Literal["application/pdf"]
    size_bytes: PositiveInt


class CreateUploadIntentResponse(BaseModel):
    document_id: UUID
    upload: UploadInstructions


class ReportUploadCompletedRequest(BaseModel):
    client_etag: str | None = None


class ReportUploadCompletedResponse(BaseModel):
    document_id: UUID
    upload_status: DocumentUploadStatus
    processing_status: DocumentProcessingStatus


class GetDocumentDataResponse(BaseModel):
    document_id: UUID
    filename: str
    size_bytes: PositiveInt
    page_count: NonNegativeInt | None
    document_type: str | None
    upload_status: DocumentUploadStatus
    processing_status: DocumentProcessingStatus
    created_at: datetime
    uploaded_at: datetime | None
    processed_at: datetime | None


class GetDocumentURLResponse(BaseModel):
    document_id: UUID
    url: str
    expires_in_seconds: PositiveInt


class UploadInstructions(BaseModel):
    url: str
    method: Literal["PUT"]
    headers: dict[str, str]
    expires_in_seconds: PositiveInt
