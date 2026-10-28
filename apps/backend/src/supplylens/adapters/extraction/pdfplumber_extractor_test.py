from pathlib import Path

import pytest

from supplylens.adapters.extraction.pdfplumber_extractor import (
    EXTRACTOR_VERSION,
    PROVENANCE,
    PdfplumberExtractor,
)
from supplylens.domain.document_extraction import DocumentExtractionOutcome
from supplylens.port.extraction.pdf_extractor import PdfUnreadableError

FIXTURES_PDF_DIR = Path(__file__).resolve().parents[6] / "fixtures" / "pdfs"


def _minimal_digital_pdf() -> bytes:
    # Synthetic selectable-text PDF for detector/extractor unit tests.
    objects = [
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n",
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n",
        (
            b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] "
            b"/Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n"
        ),
        (
            b"4 0 obj<< /Length 44 >>stream\n"
            b"BT /F1 12 Tf 50 100 Td (Hello SupplyLens) Tj ET\n"
            b"endstream\nendobj\n"
        ),
        b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n",
    ]
    return _assemble_pdf(objects)


def _minimal_image_only_pdf() -> bytes:
    objects = [
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n",
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n",
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>endobj\n",
    ]
    return _assemble_pdf(objects)


def _empty_pdf() -> bytes:
    objects = [
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n",
        b"2 0 obj<< /Type /Pages /Kids [] /Count 0 >>endobj\n",
    ]
    return _assemble_pdf(objects)


def _assemble_pdf(objects: list[bytes]) -> bytes:
    header = b"%PDF-1.4\n"
    body = b"".join(objects)
    offsets = [0]
    cursor = len(header)
    for obj in objects:
        offsets.append(cursor)
        cursor += len(obj)
    xref_entries = [b"0000000000 65535 f \n"]
    xref_entries.extend(
        f"{offset:010d} 00000 n \n".encode("ascii") for offset in offsets[1:]
    )
    xref = (
        f"xref\n0 {len(offsets)}\n".encode("ascii")
        + b"".join(xref_entries)
        + (
            f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\n"
            f"startxref\n{cursor}\n%%EOF\n"
        ).encode("ascii")
    )
    return header + body + xref


def test_extract_digital_pdf_returns_page_linked_text() -> None:
    result = PdfplumberExtractor().extract(_minimal_digital_pdf())

    assert result.outcome is DocumentExtractionOutcome.EXTRACTED
    assert result.page_count == 1
    assert result.extraction["provenance"] == PROVENANCE
    assert result.extraction["extractor_version"] == EXTRACTOR_VERSION
    assert result.extraction["page_count"] == 1
    assert len(result.extraction["pages"]) == 1
    page = result.extraction["pages"][0]
    assert page["page_number"] == 1
    assert "Hello SupplyLens" in page["text"]
    assert isinstance(page["tables"], list)


def test_extract_image_only_pdf_is_explicit_unsupported() -> None:
    result = PdfplumberExtractor().extract(_minimal_image_only_pdf())

    assert result.outcome is DocumentExtractionOutcome.UNSUPPORTED_IMAGEN_ONLY
    assert result.page_count == 1
    assert result.extraction["reason"] == "no_selectable_text"
    assert result.extraction["provenance"] == PROVENANCE
    assert result.extraction["pages"][0]["text"] == ""


def test_extract_rejects_unreadable_bytes() -> None:
    with pytest.raises(PdfUnreadableError, match="could not be read"):
        PdfplumberExtractor().extract(b"not a pdf")


def test_extract_empty_pdf_is_unknown_format() -> None:
    result = PdfplumberExtractor().extract(_empty_pdf())

    assert result.outcome is DocumentExtractionOutcome.UNSUPPORTED_UNKNOWN_FORMAT
    assert result.page_count == 0
    assert result.extraction["reason"] == "empty_pdf"
    assert result.extraction["pages"] == []


def test_extract_fixture_digital_invoice_has_text_and_tables() -> None:
    pdf_path = FIXTURES_PDF_DIR / "01_simple_digital_invoice.pdf"
    assert pdf_path.is_file()

    result = PdfplumberExtractor().extract(pdf_path.read_bytes())

    assert result.outcome is DocumentExtractionOutcome.EXTRACTED
    assert result.page_count >= 1
    first_page = result.extraction["pages"][0]
    assert first_page["page_number"] == 1
    assert "Northstar" in first_page["text"]
    assert first_page["tables"]
    assert all(
        isinstance(cell, str)
        for table in first_page["tables"]
        for row in table
        for cell in row
    )
