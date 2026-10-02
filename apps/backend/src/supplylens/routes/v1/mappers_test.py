from datetime import datetime
from uuid import UUID

from supplylens.controllers.documents.types import Document as ControllerDocument
from supplylens.domain.documents import DocumentProcessingStatus, DocumentUploadStatus
from supplylens.routes.v1.mappers import map_controller_document_to_schema_document
from supplylens.schemas.documents import Document


def test_map_controller_document_copies_all_document_fields() -> None:
    document_id = UUID("12345678-1234-5678-1234-567812345678")
    created_at = datetime(2026, 9, 30, 12, 0)
    uploaded_at = datetime(2026, 9, 30, 12, 5)
    processed_at = datetime(2026, 9, 30, 12, 10)
    controller_document = ControllerDocument(
        id=document_id,
        filename="invoice.pdf",
        size_bytes=512,
        document_type="application/pdf",
        page_count=2,
        upload_status=DocumentUploadStatus.UPLOADED,
        processing_status=DocumentProcessingStatus.PROCESSED,
        created_at=created_at,
        uploaded_at=uploaded_at,
        processed_at=processed_at,
    )

    schema_document = map_controller_document_to_schema_document(controller_document)

    assert schema_document == Document(
        id=document_id,
        filename="invoice.pdf",
        size_bytes=512,
        document_type="application/pdf",
        page_count=2,
        upload_status=DocumentUploadStatus.UPLOADED,
        processing_status=DocumentProcessingStatus.PROCESSED,
        created_at=created_at,
        uploaded_at=uploaded_at,
        processed_at=processed_at,
    )
