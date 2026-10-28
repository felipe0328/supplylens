from datetime import UTC, datetime
from io import BytesIO
from unittest.mock import Mock
from uuid import UUID

import pytest

from supplylens.controllers.documents.exceptions import DocumentNotFoundError
from supplylens.controllers.documents.helpers import create_object_key
from supplylens.controllers.documents.process_document_extraction import (
    ProcessDocumentExtractionCommand,
    process_document_extraction,
)
from supplylens.domain.document_extraction import DocumentExtractionOutcome
from supplylens.domain.documents import DocumentProcessingStatus, DocumentUploadStatus
from supplylens.port.extraction.pdf_extractor import PdfExtractor, PdfExtractorResult
from supplylens.port.persistence.document_extraction import (
    DocumentExtraction,
    DocumentExtractionPersistence,
)
from supplylens.port.persistence.documents import Document as PersistedDocument
from supplylens.port.persistence.documents import DocumentPersistence
from supplylens.port.storage.storage import ObjectNotFoundError, ObjectStorage

DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000001")
EXTRACTION_ID = UUID("00000000-0000-0000-0000-0000000000aa")
JOB_ID = 42
CREATED_AT = datetime(2026, 10, 27, tzinfo=UTC)
PDF_BYTES = b"%PDF-1.4 synthetic"


def _persisted_document() -> PersistedDocument:
    return PersistedDocument(
        id=DOCUMENT_ID,
        filename="invoice.pdf",
        size_bytes=len(PDF_BYTES),
        document_type="application/pdf",
        page_count=None,
        upload_status=DocumentUploadStatus.UPLOADED,
        processing_status=DocumentProcessingStatus.PENDING,
        created_at=CREATED_AT,
        uploaded_at=CREATED_AT,
        processed_at=None,
    )


def _saved_extraction(
    outcome: DocumentExtractionOutcome,
) -> DocumentExtraction:
    return DocumentExtraction(
        id=EXTRACTION_ID,
        document_id=DOCUMENT_ID,
        processing_job_id=JOB_ID,
        outcome=outcome,
        extraction={"pages": [{"page_number": 1, "text": "ok", "tables": []}]},
        created_at=CREATED_AT,
    )


def test_process_document_extraction_persists_digital_draft() -> None:
    storage = Mock(spec=ObjectStorage)
    documents = Mock(spec=DocumentPersistence)
    extractions = Mock(spec=DocumentExtractionPersistence)
    extractor = Mock(spec=PdfExtractor)

    documents.get_document_data.return_value = _persisted_document()

    def _download(_key: str, target: BytesIO) -> None:
        target.write(PDF_BYTES)

    storage.download_fileobj.side_effect = _download
    extractor.extract.return_value = PdfExtractorResult(
        outcome=DocumentExtractionOutcome.EXTRACTED,
        extraction={"pages": [{"page_number": 1, "text": "ok", "tables": []}]},
        page_count=1,
    )
    extractions.save_extraction_outcome.return_value = _saved_extraction(
        DocumentExtractionOutcome.EXTRACTED
    )

    result = process_document_extraction(
        storage,
        documents,
        extractions,
        extractor,
        ProcessDocumentExtractionCommand(job_id=JOB_ID, document_id=DOCUMENT_ID),
    )

    storage.download_fileobj.assert_called_once()
    assert storage.download_fileobj.call_args.args[0] == create_object_key(DOCUMENT_ID)
    extractor.extract.assert_called_once_with(PDF_BYTES)
    extractions.save_extraction_outcome.assert_called_once_with(
        document_id=DOCUMENT_ID,
        processing_job_id=JOB_ID,
        outcome=DocumentExtractionOutcome.EXTRACTED,
        extraction={"pages": [{"page_number": 1, "text": "ok", "tables": []}]},
    )
    assert result.outcome is DocumentExtractionOutcome.EXTRACTED
    assert result.extraction_id == EXTRACTION_ID


def test_process_document_extraction_persists_unsupported_outcome() -> None:
    storage = Mock(spec=ObjectStorage)
    documents = Mock(spec=DocumentPersistence)
    extractions = Mock(spec=DocumentExtractionPersistence)
    extractor = Mock(spec=PdfExtractor)

    documents.get_document_data.return_value = _persisted_document()
    storage.download_fileobj.side_effect = lambda _key, target: target.write(PDF_BYTES)
    extractor.extract.return_value = PdfExtractorResult(
        outcome=DocumentExtractionOutcome.UNSUPPORTED_IMAGEN_ONLY,
        extraction={"reason": "no_selectable_text", "pages": []},
        page_count=1,
    )
    extractions.save_extraction_outcome.return_value = _saved_extraction(
        DocumentExtractionOutcome.UNSUPPORTED_IMAGEN_ONLY
    )

    result = process_document_extraction(
        storage,
        documents,
        extractions,
        extractor,
        ProcessDocumentExtractionCommand(job_id=JOB_ID, document_id=DOCUMENT_ID),
    )

    assert result.outcome is DocumentExtractionOutcome.UNSUPPORTED_IMAGEN_ONLY
    extractions.save_extraction_outcome.assert_called_once()
    assert (
        extractions.save_extraction_outcome.call_args.kwargs["outcome"]
        is DocumentExtractionOutcome.UNSUPPORTED_IMAGEN_ONLY
    )


def test_process_document_extraction_raises_when_document_missing() -> None:
    storage = Mock(spec=ObjectStorage)
    documents = Mock(spec=DocumentPersistence)
    extractions = Mock(spec=DocumentExtractionPersistence)
    extractor = Mock(spec=PdfExtractor)
    documents.get_document_data.return_value = None

    with pytest.raises(DocumentNotFoundError, match=str(DOCUMENT_ID)):
        process_document_extraction(
            storage,
            documents,
            extractions,
            extractor,
            ProcessDocumentExtractionCommand(job_id=JOB_ID, document_id=DOCUMENT_ID),
        )

    storage.download_fileobj.assert_not_called()
    extractor.extract.assert_not_called()
    extractions.save_extraction_outcome.assert_not_called()


def test_process_document_extraction_raises_when_object_missing() -> None:
    storage = Mock(spec=ObjectStorage)
    documents = Mock(spec=DocumentPersistence)
    extractions = Mock(spec=DocumentExtractionPersistence)
    extractor = Mock(spec=PdfExtractor)
    documents.get_document_data.return_value = _persisted_document()
    storage.download_fileobj.side_effect = ObjectNotFoundError("missing")

    with pytest.raises(DocumentNotFoundError, match="object storage"):
        process_document_extraction(
            storage,
            documents,
            extractions,
            extractor,
            ProcessDocumentExtractionCommand(job_id=JOB_ID, document_id=DOCUMENT_ID),
        )

    extractor.extract.assert_not_called()
    extractions.save_extraction_outcome.assert_not_called()
