from io import BytesIO
from typing import Any

import pdfplumber

from supplylens.domain.document_extraction import DocumentExtractionOutcome
from supplylens.port.extraction.pdf_extractor import (
    PdfExtractor,
    PdfExtractorResult,
    PdfUnreadableError,
)

EXTRACTOR_VERSION = "supplylens-digital-pdfplumber-v1"
PROVENANCE = "digital_parser"


class PdfplumberExtractor(PdfExtractor):
    def extract(self, pdf_bytes: bytes) -> PdfExtractorResult:
        try:
            with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                pages = [_extract_page(page) for page in pdf.pages]
                page_count = len(pdf.pages)
        except Exception as exc:
            raise PdfUnreadableError("PDF bytes could not be read") from exc

        if page_count == 0:
            return PdfExtractorResult(
                outcome=DocumentExtractionOutcome.UNSUPPORTED_UNKNOWN_FORMAT,
                extraction=_draft_payload(
                    pages=[],
                    page_count=0,
                    reason="empty_pdf",
                ),
                page_count=0,
            )

        if not any(_page_has_selectable_text(page) for page in pages):
            return PdfExtractorResult(
                outcome=DocumentExtractionOutcome.UNSUPPORTED_IMAGEN_ONLY,
                extraction=_draft_payload(
                    pages=pages,
                    page_count=page_count,
                    reason="no_selectable_text",
                ),
                page_count=page_count,
            )

        return PdfExtractorResult(
            outcome=DocumentExtractionOutcome.EXTRACTED,
            extraction=_draft_payload(pages=pages, page_count=page_count),
            page_count=page_count,
        )


def _extract_page(page: Any) -> dict[str, Any]:
    raw_text = page.extract_text()
    text = raw_text if isinstance(raw_text, str) else ""
    raw_tables = page.extract_tables() or []
    tables = [
        [["" if cell is None else str(cell) for cell in row] for row in table]
        for table in raw_tables
    ]
    return {
        "page_number": page.page_number,
        "text": text,
        "tables": tables,
    }


def _page_has_selectable_text(page: dict[str, Any]) -> bool:
    return bool(str(page.get("text", "")).strip())


def _draft_payload(
    *,
    pages: list[dict[str, Any]],
    page_count: int,
    reason: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "provenance": PROVENANCE,
        "extractor_version": EXTRACTOR_VERSION,
        "page_count": page_count,
        "pages": pages,
    }
    if reason is not None:
        payload["reason"] = reason
    return payload
