from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from supplylens.domain.document_extraction import DocumentExtractionOutcome


@dataclass(frozen=True)
class DocumentExtraction:
    id: UUID
    document_id: UUID
    processing_job_id: int
    outcome: DocumentExtractionOutcome
    extraction: dict[str, Any]
    created_at: datetime


class DocumentExtractionPersistence(Protocol):
    def save_extraction_outcome(
        self,
        *,
        document_id: UUID,
        processing_job_id: int,
        outcome: DocumentExtractionOutcome,
        extraction: dict[str, Any],
    ) -> DocumentExtraction: ...

    def get_by_processing_job_id(
        self, processing_job_id: int
    ) -> DocumentExtraction | None: ...
