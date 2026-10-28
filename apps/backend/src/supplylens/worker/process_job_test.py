from collections.abc import Iterator
from datetime import UTC, datetime
from unittest.mock import Mock, patch
from uuid import UUID

from supplylens.controllers.documents.process_document_extraction import (
    ProcessDocumentExtractionCommand,
    ProcessDocumentExtractionResult,
)
from supplylens.controllers.processing_jobs.types import ProcessingJob
from supplylens.domain.document_extraction import DocumentExtractionOutcome
from supplylens.domain.processing_job import ProcessingJobState
from supplylens.worker.process_job import process_claimed_job

DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000001")
EXTRACTION_ID = UUID("00000000-0000-0000-0000-0000000000aa")
NOW = datetime(2026, 10, 27, tzinfo=UTC)


def _job() -> ProcessingJob:
    return ProcessingJob(
        id=7,
        document_uuid=DOCUMENT_ID,
        attempts=1,
        status=ProcessingJobState.PROCESSING,
        lease_owner="worker-1",
        lease_expires_at=NOW,
        error_code=None,
        error_message=None,
        created_at=NOW,
        started_at=NOW,
        finished_at=None,
    )


def test_process_claimed_job_wires_adapters_and_controller() -> None:
    session = Mock()
    storage = Mock()
    extractor = Mock()
    documents = Mock()
    extractions = Mock()
    process_result = ProcessDocumentExtractionResult(
        outcome=DocumentExtractionOutcome.EXTRACTED,
        extraction_id=EXTRACTION_ID,
    )

    def fake_get_session() -> Iterator[Mock]:
        yield session

    with (
        patch(
            "supplylens.worker.process_job.StorageAdapter",
            return_value=storage,
        ),
        patch(
            "supplylens.worker.process_job.PdfplumberExtractor",
            return_value=extractor,
        ),
        patch(
            "supplylens.worker.process_job.DocumentPersistenceAdapter",
            return_value=documents,
        ),
        patch(
            "supplylens.worker.process_job.DocumentExtractionPersistenceAdapter",
            return_value=extractions,
        ),
        patch(
            "supplylens.worker.process_job.get_session",
            fake_get_session,
        ),
        patch(
            "supplylens.worker.process_job.process_document_extraction",
            return_value=process_result,
        ) as process_extraction,
    ):
        process_claimed_job(_job())

    process_extraction.assert_called_once()
    args = process_extraction.call_args.args
    assert args[0] is storage
    assert args[1] is documents
    assert args[2] is extractions
    assert args[3] is extractor
    assert args[4] == ProcessDocumentExtractionCommand(
        job_id=7,
        document_id=DOCUMENT_ID,
    )
