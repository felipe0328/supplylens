from contextlib import contextmanager

from supplylens.adapters.extraction.pdfplumber_extractor import PdfplumberExtractor
from supplylens.adapters.persistence.document_extraction import (
    DocumentExtractionPersistenceAdapter,
)
from supplylens.adapters.persistence.documents import DocumentPersistenceAdapter
from supplylens.adapters.storage.storage import StorageAdapter
from supplylens.controllers.documents.process_document_extraction import (
    ProcessDocumentExtractionCommand,
    process_document_extraction,
)
from supplylens.controllers.processing_jobs.types import ProcessingJob
from supplylens.database.database import get_session


def process_claimed_job(job: ProcessingJob) -> None:
    storage = StorageAdapter()
    extractor = PdfplumberExtractor()
    with contextmanager(get_session)() as session:
        process_document_extraction(
            storage,
            DocumentPersistenceAdapter(session),
            DocumentExtractionPersistenceAdapter(session),
            extractor,
            ProcessDocumentExtractionCommand(
                job_id=job.id,
                document_id=job.document_uuid,
            ),
        )
