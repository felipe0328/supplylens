from supplylens.controllers.documents.types import Document as ControllerDocument
from supplylens.schemas.documents import Document


def map_controller_document_to_schema_document(
    controller_document: ControllerDocument,
) -> Document:
    return Document(
        id=controller_document.id,
        filename=controller_document.filename,
        size_bytes=controller_document.size_bytes,
        document_type=controller_document.document_type,
        page_count=controller_document.page_count,
        upload_status=controller_document.upload_status,
        processing_status=controller_document.processing_status,
        created_at=controller_document.created_at,
        uploaded_at=controller_document.uploaded_at,
        processed_at=controller_document.processed_at,
    )
