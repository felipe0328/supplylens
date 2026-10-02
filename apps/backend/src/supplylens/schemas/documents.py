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
    id: UUID
    upload: UploadInstructions


class ReportUploadCompletedResponse(BaseModel):
    document: Document


class GetDocumentDataResponse(BaseModel):
    document: Document


class GetDocumentURLResponse(BaseModel):
    id: UUID
    url: str
    expires_in_seconds: PositiveInt


class UploadInstructions(BaseModel):
    url: str
    method: Literal["PUT"]
    headers: dict[str, str]
    expires_in_seconds: PositiveInt


class Document(BaseModel):
    id: UUID
    filename: str
    size_bytes: PositiveInt
    document_type: str | None
    page_count: NonNegativeInt | None
    upload_status: DocumentUploadStatus
    processing_status: DocumentProcessingStatus
    created_at: datetime
    uploaded_at: datetime | None
    processed_at: datetime | None
