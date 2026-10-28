from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from supplylens.adapters.persistence.mappers import (
    map_model_document_extraction_to_abstraction,
)
from supplylens.domain.document_extraction import DocumentExtractionOutcome
from supplylens.models.document_extraction import (
    DocumentExtraction as DocumentExtractionModel,
)
from supplylens.port.persistence.document_extraction import (
    DocumentExtraction as AbstractDocumentExtraction,
)
from supplylens.port.persistence.document_extraction import (
    DocumentExtractionPersistence,
)


class DocumentExtractionPersistenceAdapter(DocumentExtractionPersistence):
    """Flush extraction writes; the caller owns transaction commit and rollback."""

    _session: Session

    def __init__(self, session: Session) -> None:
        self._session = session

    def save_extraction_outcome(
        self,
        *,
        document_id: UUID,
        processing_job_id: int,
        outcome: DocumentExtractionOutcome,
        extraction: dict[str, Any],
    ) -> AbstractDocumentExtraction:
        existing = self._session.scalar(
            select(DocumentExtractionModel).where(
                DocumentExtractionModel.processing_job_id == processing_job_id
            )
        )
        if existing is None:
            existing = DocumentExtractionModel(
                document_id=document_id,
                processing_job_id=processing_job_id,
                outcome=outcome,
                extraction=extraction,
            )
            self._session.add(existing)
        else:
            existing.document_id = document_id
            existing.outcome = outcome
            existing.extraction = extraction

        self._session.flush()
        mapped = map_model_document_extraction_to_abstraction(existing)
        assert mapped is not None
        return mapped

    def get_by_processing_job_id(
        self, processing_job_id: int
    ) -> AbstractDocumentExtraction | None:
        document_extraction = self._session.scalar(
            select(DocumentExtractionModel).where(
                DocumentExtractionModel.processing_job_id == processing_job_id
            )
        )
        return map_model_document_extraction_to_abstraction(document_extraction)
