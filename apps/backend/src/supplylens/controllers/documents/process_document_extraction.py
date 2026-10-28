from dataclasses import dataclass
from io import BytesIO
from uuid import UUID

from supplylens.controllers.documents.exceptions import DocumentNotFoundError
from supplylens.controllers.documents.helpers import create_object_key
from supplylens.domain.document_extraction import DocumentExtractionOutcome
from supplylens.port.extraction.pdf_extractor import PdfExtractor
from supplylens.port.persistence.document_extraction import (
    DocumentExtractionPersistence,
)
from supplylens.port.persistence.documents import DocumentPersistence
from supplylens.port.storage.storage import ObjectNotFoundError, ObjectStorage


@dataclass(frozen=True)
class ProcessDocumentExtractionCommand:
    job_id: int
    document_id: UUID


@dataclass(frozen=True)
class ProcessDocumentExtractionResult:
    outcome: DocumentExtractionOutcome
    extraction_id: UUID


def process_document_extraction(
    storage: ObjectStorage,
    documents: DocumentPersistence,
    extractions: DocumentExtractionPersistence,
    extractor: PdfExtractor,
    req: ProcessDocumentExtractionCommand,
) -> ProcessDocumentExtractionResult:
    document = documents.get_document_data(req.document_id)
    if document is None:
        raise DocumentNotFoundError(f"Document with ID {req.document_id} not found")

    target = BytesIO()
    try:
        storage.download_fileobj(create_object_key(req.document_id), target)
    except ObjectNotFoundError as exc:
        raise DocumentNotFoundError(
            f"Document with ID {req.document_id} not found in object storage"
        ) from exc

    extracted = extractor.extract(target.getvalue())
    saved = extractions.save_extraction_outcome(
        document_id=req.document_id,
        processing_job_id=req.job_id,
        outcome=extracted.outcome,
        extraction=extracted.extraction,
    )
    return ProcessDocumentExtractionResult(
        outcome=saved.outcome,
        extraction_id=saved.id,
    )
