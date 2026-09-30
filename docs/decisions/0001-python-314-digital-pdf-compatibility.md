# ADR 0001: Python 3.14 for digital PDF extraction

**Status:** Accepted
**Date:** 29 September 2026

## Decision

Keep Python 3.14 as the backend runtime. Automatic extraction in the MVP supports digital PDFs with selectable text. Image-only or scanned PDFs are preserved, marked unsupported for automatic extraction, and routed to manual review.

B0 does not add a PDF extraction dependency. B2 will pin the extraction library when that feature and its tests are implemented.

## Evidence

Python 3.14.7 successfully ran `pdfplumber` 0.11.10 in an isolated environment across all 12 retained digital fixture PDFs. Every fixture opened successfully and produced non-empty page text. This check establishes runtime compatibility; it is not a substitute for B2 field-extraction and provenance tests.

## Consequences

- The backend can continue targeting Python 3.14.
- B0 remains limited to foundation work and does not ship document extraction.
- The fixture set covers digital documents only; image-based extraction is outside the MVP.
