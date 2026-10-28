from dataclasses import dataclass
from typing import Any, Protocol

from supplylens.domain.document_extraction import DocumentExtractionOutcome


class PdfExtractionError(Exception):
    """Base error for PDF extraction failures."""


class PdfUnreadableError(PdfExtractionError):
    """The PDF bytes could not be opened or read as a PDF."""


@dataclass(frozen=True)
class PdfExtractorResult:
    outcome: DocumentExtractionOutcome
    extraction: dict[str, Any]
    page_count: int


class PdfExtractor(Protocol):
    def extract(self, pdf_bytes: bytes) -> PdfExtractorResult: ...
