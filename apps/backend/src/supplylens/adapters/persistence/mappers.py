from supplylens.models.document import Document as ModelDocument
from supplylens.port.persistence.documents import Document as AbstractDocument


def map_model_to_abstraction(model_document: ModelDocument) -> AbstractDocument:
    return AbstractDocument(
        id=model_document.id,
        filename=model_document.filename,
        size_bytes=model_document.size_bytes,
        document_type=model_document.document_type,
        page_count=model_document.page_count,
        upload_status=model_document.upload_status,
        processing_status=model_document.processing_status,
        created_at=model_document.created_at,
        uploaded_at=model_document.uploaded_at,
        processed_at=model_document.processed_at,
    )
