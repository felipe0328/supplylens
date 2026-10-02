from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, PositiveInt

from supplylens.domain.documents import DocumentProcessingStatus, DocumentUploadStatus


class CreateUploadIntentRequest(BaseModel):
    filename: str = Field(
        min_length=1,
        max_length=255,
        description="Original PDF filename, including its extension.",
        examples=["supplier-invoice.pdf"],
    )
    content_type: Literal["application/pdf"] = Field(
        description="MIME type of the document. Only PDF uploads are supported.",
        examples=["application/pdf"],
    )
    size_bytes: PositiveInt = Field(
        description=(
            "Exact size of the PDF in bytes. Must not exceed the configured "
            "upload limit."
        ),
        examples=[245760],
    )


class CreateUploadIntentResponse(BaseModel):
    id: UUID = Field(description="ID assigned to the document.")
    upload: UploadInstructions = Field(
        description=(
            "Short-lived instructions for uploading the PDF directly to object storage."
        )
    )


class ReportUploadCompletedResponse(BaseModel):
    document: Document = Field(
        description="The document after its uploaded PDF was verified."
    )


class GetDocumentDataResponse(BaseModel):
    document: Document = Field(
        description="Stored document metadata and processing state."
    )


class GetDocumentURLResponse(BaseModel):
    id: UUID = Field(description="ID of the requested document.")
    url: str = Field(description="Short-lived URL for downloading the uploaded PDF.")
    expires_in_seconds: PositiveInt = Field(
        description="Number of seconds before the download URL expires."
    )


class UploadInstructions(BaseModel):
    url: str = Field(description="Short-lived object storage URL for the upload.")
    method: Literal["PUT"] = Field(
        description="HTTP method to use when uploading the PDF."
    )
    headers: dict[str, str] = Field(
        description="Headers that must be sent with the upload request."
    )
    expires_in_seconds: PositiveInt = Field(
        description="Number of seconds before the upload URL expires."
    )


class Document(BaseModel):
    id: UUID = Field(description="Stable ID assigned to the document.")
    filename: str = Field(
        description="Original filename supplied when upload was created."
    )
    size_bytes: PositiveInt = Field(
        description="Declared size of the document in bytes."
    )
    document_type: str | None = Field(
        description="Detected document type, when available."
    )
    page_count: NonNegativeInt | None = Field(
        description="Number of pages, when available."
    )
    upload_status: DocumentUploadStatus = Field(
        description="Whether the PDF has been uploaded and verified."
    )
    processing_status: DocumentProcessingStatus = Field(
        description="Current processing state of the document."
    )
    created_at: datetime = Field(
        description="UTC timestamp when the record was created."
    )
    uploaded_at: datetime | None = Field(
        description="UTC timestamp when the upload was verified, if completed."
    )
    processed_at: datetime | None = Field(
        description="UTC timestamp when processing completed, if available."
    )
