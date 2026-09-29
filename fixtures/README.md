# Synthetic supplier PDF fixtures

These PDFs are invented. They contain no Mulligan data, customer identity, real supplier document, private calculation policy, or production credential. Their purpose is to test **evidence extraction and human review**, not to claim that every supplier uses these layouts.

The machine-readable expectations are in [`expected.json`](expected.json). Money values there are canonical decimal strings with `.` separators, even when the PDF prints a decimal comma. A `business_status_hint` is a human review scenario, **not** a status to infer automatically from a document's title. `expected_warnings` lists the specific issue a fixture is meant to expose; it is not an exhaustive list of every missing optional field.

## Fixture map

| PDF | Scenario and useful assertions |
| --- | --- |
| `01_simple_digital_invoice.pdf` | Baseline digital text, two product rows, consistent arithmetic. |
| `02_invoice_handling_and_msrp.pdf` | Handling row is a charge, not a product; MSRP is distinct from supplier net price. |
| `03_preorder_original.pdf` | A pre-order supports a provisional plan; it is not automatically a recorded purchase. Weight and pack notes are printed. |
| `04_invoice_matches_preorder.pdf` | Same products and prices as 03, a different layout/reference, and a link back to the order. Linking must not double count. |
| `05_sales_order_before_change.pdf` | Original order for a reconciliation case. |
| `06_invoice_changed_quantity_fee.pdf` | Later invoice has fewer units and a new handling fee; linking must flag differences before revising the case. |
| `07_multipage_repeated_header.pdf` | Sixteen product lines across two pages, repeated header, total only on page 2. Every line has the correct source page. |
| `08_scanned_invoice_image_only.pdf` | One raster page with **zero embedded text**. Local OCR should recover its reference, product name, and total. |
| `09_mixed_digital_scanned_pages.pdf` | Page 1 has digital text; page 2 is image-only. OCR is needed for one page, with a single document total. |
| `10_order_discount_and_shared_fees.pdf` | Product subtotal 100.00, separate -10.00 discount, 5.00 service fee, 7.50 freight, total 102.50. Do not apply a discount twice. |
| `11_case_pack_sellable_units_weight.pdf` | Two cases at six sellable boxes per case; distinguish purchased units (2) from sellable units (12), and weight per purchase unit. |
| `12_spanish_eur_missing_weight.pdf` | Spanish headings, EUR, printed decimal comma, no weight. Keep currency distinct from USD and leave weight unknown. |
| `13_ambiguous_currency.pdf` | No currency printed. Never guess USD or COP from the numeric amounts. |
| `14_incorrect_line_and_document_total.pdf` | Deliberately wrong: 3 × 12.00 is 36.00, but line says 35.00; displayed total 40.00 has no supporting charge. Flag both mismatches without silently changing the PDF values. |

Related groups in `expected.json` identify 03–04 and 05–06. Do not merge documents by filename or similar-looking totals alone. Reuploading the **same file** is the exact hash duplicate test; it does not need a second copy in the repository.

## How to use them in backend tests

1. Load `expected.json`, open each `file` relative to this directory, and verify PDF page count and mode. An image-only page must be routed through OCR; a digital page should retain page references.
2. Compare extracted supplier, reference, date, currency, row roles, quantities, decimal amounts, and page numbers to the expected fields. Allow OCR's whitespace and punctuation to vary; use `ocr_assertions` for essential words and values.
3. Test the review workflow separately. Extraction values remain suggestions until a user confirms them. The system must permit missing fields and human corrections without inventing data.
4. For 03–04 and 05–06, exercise document linking and reconciliation. Verify one purchase-case aggregate per linked group, explicit status, no automatic overwrite, and immutable prior revisions.
5. Run reports across USD and EUR cases. Group by currency or require an explicit conversion; never add raw amounts across currencies. No fixture represents payment, inventory, or sales.
6. Run the entire upload → draft → review → report path with no LLM credentials. These PDFs require no external AI service.

Do not require a general parser to handle every deliberately difficult document from the first milestone. Use the fixture map to grow capability, record which documents need manual review, and measure whether later OCR, layout rules, or optional AI reduce correction effort.

## Regeneration and maintenance

The checked-in PDFs are ready to use. To regenerate them, install `reportlab`, `Pillow`, and `pypdf` in a separate fixture tooling environment and install Poppler (`pdftoppm`) for the image-only pages. Run:

```bash
python fixtures/generate_mock_pdfs.py
```

The generator rewrites all PDFs and `expected.json`. Inspect changed renders and OCR output before accepting a regenerated fixture. Do not add authentic supplier PDFs, real addresses, emails, customer IDs, business data, or private price formulas to this directory.
