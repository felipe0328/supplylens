"""Generate fully synthetic SupplyLens PDF fixtures and their expected data.

Optional local tools: reportlab, pypdf, Pillow, and Poppler's pdftoppm.
Run from any directory: python fixtures/generate_mock_pdfs.py
The checked-in PDFs are the test inputs; regeneration is only for maintenance.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any

from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parent
PDF_DIR = ROOT / "pdfs"
PAGE_W, PAGE_H = letter


def item(sku: str, description: str, qty: str, price: str, amount: str, **extra: Any) -> dict[str, Any]:
    return {"role": "product", "sku": sku, "description": description,
            "quantity": qty, "unit_price": price, "line_total": amount, **extra}


def charge(label: str, amount: str, role: str = "charge") -> dict[str, Any]:
    return {"role": role, "sku": "", "description": label,
            "quantity": None, "unit_price": None, "line_total": amount}


SPECS: list[dict[str, Any]] = [
    {
        "file": "01_simple_digital_invoice.pdf", "scenario": "digital_baseline",
        "supplier": "Northstar Tabletop Wholesale", "document_type": "invoice",
        "reference": "INV-1001", "date": "2026-03-04", "currency": "USD",
        "status_hint": "purchase_recorded", "layout": "classic", "mode": "digital",
        "rows": [
            item("CARD-101", "Explorer Card Deck", "2", "25.00", "50.00"),
            item("DICE-210", "Amber Dice Set", "3", "6.50", "19.50"),
        ],
        "printed_subtotal": "69.50", "printed_total": "69.50",
    },
    {
        "file": "02_invoice_handling_and_msrp.pdf", "scenario": "charge_row_and_msrp",
        "supplier": "Cedar Play Distribution", "document_type": "invoice",
        "reference": "CP-4420", "date": "2026-03-07", "currency": "USD",
        "status_hint": "purchase_recorded", "layout": "alternate", "mode": "digital",
        "rows": [
            charge("Freight and Handling", "30.00"),
            item("BOX-700", "Collector Booster Display", "1", "68.25", "68.25", msrp="119.76"),
            item("MAT-220", "Nebula Playmat", "2", "12.40", "24.80", msrp="19.99"),
        ],
        "printed_subtotal": "93.05", "printed_total": "123.05",
        "expected_warnings": ["CHARGE_ROW_NOT_PRODUCT"],
    },
    {
        "file": "03_preorder_original.pdf", "scenario": "preorder_planning",
        "supplier": "Northstar Tabletop Wholesale", "document_type": "preorder",
        "reference": "SO-7003", "date": "2026-04-02", "currency": "USD",
        "status_hint": "planned", "layout": "order", "mode": "digital",
        "related_group": "matching_order_invoice", "relationship": "first_document",
        "rows": [
            item("TIN-6", "Moonlight Tin Master Case", "2", "54.00", "108.00", weight_lb="3.80", pack="6 tins per case"),
            item("SLEEVE-01", "Clear Standard Sleeves", "5", "4.00", "20.00", weight_lb="0.28"),
        ],
        "printed_subtotal": "128.00", "printed_total": "128.00",
        "note": "PRE-ORDER ONLY. Allocation and final billing may change. This is not proof of payment or receipt.",
        "expected_warnings": ["PREORDER_NOT_RECORDED_PURCHASE"],
    },
    {
        "file": "04_invoice_matches_preorder.pdf", "scenario": "matching_supporting_document",
        "supplier": "Northstar Tabletop Wholesale", "document_type": "invoice",
        "reference": "INV-7003", "linked_reference": "SO-7003", "date": "2026-04-09", "currency": "USD",
        "status_hint": "purchase_recorded", "layout": "classic", "mode": "digital",
        "related_group": "matching_order_invoice", "relationship": "matches_03",
        "rows": [
            item("TIN-6", "Moonlight Tin Master Case", "2", "54.00", "108.00", weight_lb="3.80", pack="6 tins per case"),
            item("SLEEVE-01", "Clear Standard Sleeves", "5", "4.00", "20.00", weight_lb="0.28"),
        ],
        "printed_subtotal": "128.00", "printed_total": "128.00",
    },
    {
        "file": "05_sales_order_before_change.pdf", "scenario": "order_before_change",
        "supplier": "Redwood Games Supply", "document_type": "sales_order",
        "reference": "SO-8005", "date": "2026-05-12", "currency": "USD",
        "status_hint": "ordered", "layout": "order", "mode": "digital",
        "related_group": "mismatching_order_invoice", "relationship": "first_document",
        "rows": [
            item("GAME-A", "Castle Quest", "4", "18.00", "72.00"),
            item("GAME-B", "River Puzzle", "2", "30.00", "60.00"),
        ],
        "printed_subtotal": "132.00", "printed_total": "132.00",
    },
    {
        "file": "06_invoice_changed_quantity_fee.pdf", "scenario": "later_document_mismatch",
        "supplier": "Redwood Games Supply", "document_type": "invoice",
        "reference": "INV-8005", "linked_reference": "SO-8005", "date": "2026-05-16", "currency": "USD",
        "status_hint": "review_required", "layout": "alternate", "mode": "digital",
        "related_group": "mismatching_order_invoice", "relationship": "differs_from_05",
        "rows": [
            item("GAME-A", "Castle Quest", "3", "18.00", "54.00"),
            item("GAME-B", "River Puzzle", "2", "30.00", "60.00"),
            charge("Handling", "8.00"),
        ],
        "printed_subtotal": "114.00", "printed_total": "122.00",
        "expected_warnings": ["RELATED_DOCUMENT_DIFFERENCE"],
    },
    {
        "file": "07_multipage_repeated_header.pdf", "scenario": "multipage_table",
        "supplier": "Willow Accessories", "document_type": "invoice",
        "reference": "WA-6010", "date": "2026-06-03", "currency": "USD",
        "status_hint": "purchase_recorded", "layout": "classic", "mode": "digital",
        "break_after": 8,
        "rows": [item(f"SLV-{i:02d}", f"Card Sleeve Color Variant {i:02d} - 100 count", "2", "5.25", "10.50") for i in range(1, 13)]
        + [item(f"BOX-{i:02d}", f"Deck Storage Box Variant {i:02d}", "1", "7.00", "7.00") for i in range(13, 17)],
        "printed_subtotal": "154.00", "printed_total": "154.00",
    },
    {
        "file": "08_scanned_invoice_image_only.pdf", "scenario": "scan_requires_ocr",
        "supplier": "Birch Hobby Co", "document_type": "invoice",
        "reference": "BHC-222", "date": "2026-06-11", "currency": "USD",
        "status_hint": "purchase_recorded", "layout": "classic", "mode": "scanned",
        "rows": [
            item("MINI-11", "Miniature Paint Set", "2", "11.50", "23.00"),
            item("BRSH-27", "Fine Brush Kit", "1", "27.00", "27.00"),
        ],
        "printed_subtotal": "50.00", "printed_total": "50.00",
        "expected_warnings": ["OCR_REQUIRED"],
        "ocr_assertions": ["BHC-222", "Miniature Paint Set", "50.00"],
    },
    {
        "file": "09_mixed_digital_scanned_pages.pdf", "scenario": "per_page_ocr",
        "supplier": "Pinecrest Play Goods", "document_type": "invoice",
        "reference": "PPG-430", "date": "2026-06-18", "currency": "USD",
        "status_hint": "purchase_recorded", "layout": "classic", "mode": "mixed",
        "break_after": 1,
        "rows": [
            item("KIT-15", "Starter Kit", "1", "15.00", "15.00"),
            item("SLEEVE-8", "Premium Sleeves", "2", "8.00", "16.00"),
        ],
        "printed_subtotal": "31.00", "printed_total": "31.00",
        "expected_warnings": ["PAGE_2_OCR_REQUIRED"],
        "ocr_assertions": ["PPG-430", "Premium Sleeves", "31.00"],
    },
    {
        "file": "10_order_discount_and_shared_fees.pdf", "scenario": "discount_and_charges",
        "supplier": "Maple Board Games", "document_type": "sales_order",
        "reference": "MBG-931", "date": "2026-07-02", "currency": "USD",
        "status_hint": "ordered", "layout": "alternate", "mode": "digital",
        "rows": [
            item("TOKEN-A", "Acrylic Tokens", "4", "10.00", "40.00"),
            item("BOARD-B", "Foldable Game Board", "3", "20.00", "60.00"),
            charge("Order Discount", "-10.00", role="discount"),
            charge("Supplier Service Fee", "5.00"),
            charge("Freight", "7.50"),
        ],
        "printed_subtotal": "100.00", "printed_total": "102.50",
    },
    {
        "file": "11_case_pack_sellable_units_weight.pdf", "scenario": "pack_expansion_and_weight",
        "supplier": "Summit Collectibles", "document_type": "invoice",
        "reference": "SC-774", "date": "2026-07-15", "currency": "USD",
        "status_hint": "purchase_recorded", "layout": "order", "mode": "digital",
        "rows": [
            item("CASE-TCG", "Trading Card Box Case", "2", "90.00", "180.00", weight_lb="8.40", pack="6 sellable boxes per case", sellable_units_per_purchase_unit="6"),
            item("SINGLE-1", "Single Accessory", "5", "4.00", "20.00", weight_lb="0.12", sellable_units_per_purchase_unit="1"),
        ],
        "printed_subtotal": "200.00", "printed_total": "200.00",
    },
    {
        "file": "12_spanish_eur_missing_weight.pdf", "scenario": "spanish_eur_missing_weight",
        "supplier": "Ludoteca Sol", "document_type": "invoice",
        "reference": "LS-1209", "date": "2026-08-03", "currency": "EUR",
        "status_hint": "purchase_recorded", "layout": "spanish", "mode": "digital", "display_decimal_separator": ",",
        "rows": [
            item("JGO-12", "Juego de mesa cooperativo", "2", "12.00", "24.00"),
            item("DAD-95", "Dados de colores", "1", "9.50", "9.50"),
        ],
        "printed_subtotal": "33.50", "printed_total": "33.50",
        "expected_warnings": ["WEIGHT_MISSING"],
    },
    {
        "file": "13_ambiguous_currency.pdf", "scenario": "currency_missing",
        "supplier": "Quartz Wholesale", "document_type": "unknown",
        "reference": "QW-13", "date": "2026-08-12", "currency": None,
        "status_hint": "review_required", "layout": "classic", "mode": "digital",
        "rows": [item("TOKEN-72", "Wooden Tokens", "2", "7.25", "14.50")],
        "printed_subtotal": "14.50", "printed_total": "14.50",
        "expected_warnings": ["CURRENCY_MISSING", "WEIGHT_MISSING"],
    },
    {
        "file": "14_incorrect_line_and_document_total.pdf", "scenario": "arithmetic_mismatch",
        "supplier": "Harbor Hobby Supply", "document_type": "invoice",
        "reference": "HHS-1400", "date": "2026-08-20", "currency": "USD",
        "status_hint": "review_required", "layout": "classic", "mode": "digital",
        "rows": [item("PNT-12", "Paint Pots", "3", "12.00", "35.00")],
        "printed_subtotal": "35.00", "printed_total": "40.00",
        "expected_warnings": ["LINE_TOTAL_MISMATCH", "DOCUMENT_TOTAL_MISMATCH"],
    },
]


def install_font() -> None:
    options = [Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
               Path("/usr/local/share/fonts/DejaVuSans.ttf")]
    for font in options:
        if font.exists():
            pdfmetrics.registerFont(TTFont("FixtureSans", str(font)))
            return
    raise RuntimeError("DejaVu Sans is needed to regenerate these PDFs")


def line_wrap(text: str, max_chars: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if len(current) + len(word) + (1 if current else 0) > max_chars:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return lines or [""]


def draw_page(pdf: canvas.Canvas, spec: dict[str, Any], rows: list[dict[str, Any]], page: int, pages: int) -> None:
    layout = spec["layout"]
    accent = {"classic": colors.HexColor("#234B60"),
              "alternate": colors.HexColor("#774444"),
              "order": colors.HexColor("#43553A"),
              "spanish": colors.HexColor("#524777")}[layout]
    pdf.setFillColor(colors.HexColor("#F8F9F7"))
    pdf.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    pdf.setFillColor(accent)
    pdf.rect(0, PAGE_H - 88, PAGE_W, 88, fill=1, stroke=0)
    title = {"invoice": "INVOICE", "sales_order": "SALES ORDER", "preorder": "PRE-ORDER", "unknown": "SUPPLIER DOCUMENT"}[spec["document_type"]]
    if layout == "spanish":
        title = "FACTURA"
    pdf.setFillColor(colors.white)
    pdf.setFont("FixtureSans", 15)
    pdf.drawString(36, PAGE_H - 46, spec["supplier"])
    pdf.setFont("FixtureSans", 10)
    pdf.drawRightString(PAGE_W - 36, PAGE_H - 46, title)
    pdf.setFillColor(colors.HexColor("#27323A"))
    pdf.setFont("FixtureSans", 10)
    pdf.drawString(36, PAGE_H - 120, f"{'Referencia' if layout == 'spanish' else 'Reference'}: {spec['reference']}")
    pdf.drawString(36, PAGE_H - 139, f"{'Fecha' if layout == 'spanish' else 'Date'}: {spec['date']}")
    if spec.get("currency"):
        pdf.drawString(270, PAGE_H - 120, f"{'Moneda' if layout == 'spanish' else 'Currency'}: {spec['currency']}")
    if spec.get("linked_reference"):
        pdf.drawString(270, PAGE_H - 139, f"Related order: {spec['linked_reference']}")
    pdf.drawRightString(PAGE_W - 36, PAGE_H - 139, f"Page {page} / {pages}")
    if spec.get("note"):
        pdf.setFillColor(colors.HexColor("#754B20"))
        pdf.setFont("FixtureSans", 8)
        for i, part in enumerate(line_wrap(spec["note"], 100)[:2]):
            pdf.drawString(36, PAGE_H - 166 - i * 11, part)

    y = PAGE_H - 199
    pdf.setFillColor(accent)
    pdf.roundRect(34, y - 5, PAGE_W - 68, 27, 4, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("FixtureSans", 8)
    if layout == "spanish":
        labels = [(44, "ARTICULO"), (128, "DESCRIPCION"), (406, "CANT"), (448, "PRECIO"), (535, "IMPORTE")]
        sku_x, desc_x, qty_x, price_x, desc_chars, detail_chars = 44, 128, 406, 516, 39, 53
    elif layout == "alternate":
        labels = [(44, "DESCRIPTION / MSRP"), (316, "ITEM CODE"), (406, "QTY"), (448, "NET"), (535, "EXT")]
        sku_x, desc_x, qty_x, price_x, desc_chars, detail_chars = 316, 44, 406, 516, 33, 42
    elif layout == "order":
        labels = [(44, "SKU"), (125, "QTY"), (161, "DESCRIPTION / PACK"), (414, "LB/UNIT"), (475, "PRICE"), (535, "AMOUNT")]
        sku_x, desc_x, qty_x, price_x, desc_chars, detail_chars = 44, 161, 125, 519, 32, 39
    else:
        labels = [(44, "SKU"), (128, "DESCRIPTION"), (406, "QTY"), (448, "UNIT"), (535, "AMOUNT")]
        sku_x, desc_x, qty_x, price_x, desc_chars, detail_chars = 44, 128, 406, 516, 39, 53
    for x, value in labels:
        pdf.drawString(x, y + 5, value)
    y -= 31
    pdf.setFillColor(colors.HexColor("#22282D"))
    for row in rows:
        detail = row.get("pack") or (f"Weight: {row['weight_lb']} lb per purchase unit" if row.get("weight_lb") and layout != "order" else "")
        if row.get("pack") and row.get("weight_lb") and layout != "order":
            detail += f" | Weight: {row['weight_lb']} lb/unit"
        if row.get("msrp"):
            detail = f"MSRP: {row['msrp']}" + (f" | {detail}" if detail else "")
        desc_lines = line_wrap(row["description"], desc_chars)[:2]
        detail_lines = line_wrap(detail, detail_chars)[:2] if detail else []
        height = max(37, 14 + 12 * (len(desc_lines) + len(detail_lines)))
        pdf.setFont("FixtureSans", 8.5)
        pdf.drawString(sku_x, y, row["sku"])
        for j, part in enumerate(desc_lines):
            pdf.drawString(desc_x, y - 12 * j, part)
        pdf.setFillColor(colors.HexColor("#64717B"))
        pdf.setFont("FixtureSans", 7)
        for j, part in enumerate(detail_lines):
            pdf.drawString(desc_x, y - 12 * len(desc_lines) - 10 * j, part)
        pdf.setFillColor(colors.HexColor("#22282D"))
        pdf.setFont("FixtureSans", 8.5)
        if row["quantity"] is not None:
            pdf.drawString(qty_x, y, row["quantity"])
        if layout == "order" and row.get("weight_lb"):
            pdf.drawString(414, y, row["weight_lb"])
        if row["unit_price"] is not None:
            pdf.drawRightString(price_x, y, row["unit_price"].replace(".", spec.get("display_decimal_separator", ".")))
        pdf.drawRightString(576, y, row["line_total"].replace(".", spec.get("display_decimal_separator", ".")))
        y -= height
        pdf.setStrokeColor(colors.HexColor("#DCE1E3"))
        pdf.line(36, y + 13, 576, y + 13)

    if page == pages:
        if y < 102:
            raise ValueError(f"Rows collide with totals in {spec['file']}")
        pdf.setFont("FixtureSans", 9)
        pdf.drawRightString(516, y - 2, "Subtotal productos" if layout == "spanish" else "Products subtotal")
        pdf.drawRightString(576, y - 2, spec["printed_subtotal"].replace(".", spec.get("display_decimal_separator", ".")))
        pdf.setFillColor(accent)
        pdf.setFont("FixtureSans", 12)
        pdf.drawRightString(516, y - 27, "TOTAL DOCUMENTO" if layout == "spanish" else "DOCUMENT TOTAL")
        pdf.drawRightString(576, y - 27, spec["printed_total"].replace(".", spec.get("display_decimal_separator", ".")))
    pdf.setFillColor(colors.HexColor("#69757C"))
    pdf.setFont("FixtureSans", 7)
    pdf.drawString(36, 33, "SYNTHETIC TEST FIXTURE - no real supplier, customer, or transaction")
    pdf.drawRightString(576, 33, spec["reference"])
    pdf.showPage()


def raster_page(source: Path, number: int, temp: Path) -> Path:
    prefix = temp / f"scan_{number}"
    subprocess.run(["pdftoppm", "-f", str(number), "-l", str(number),
                    "-r", "180", "-png", "-singlefile", str(source), str(prefix)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    image_path = prefix.with_suffix(".png")
    # Convert to gray and lightly compress, while keeping OCR letters readable.
    with Image.open(image_path) as image:
        image.convert("L").save(image_path, optimize=True)
    page_pdf = temp / f"image_page_{number}.pdf"
    pdf = canvas.Canvas(str(page_pdf), pagesize=letter, pageCompression=0, invariant=1)
    pdf.drawImage(ImageReader(str(image_path)), 0, 0, PAGE_W, PAGE_H)
    pdf.save()
    return page_pdf


def generate_pdf(spec: dict[str, Any]) -> tuple[Path, list[dict[str, Any]], int]:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        vector = temp / "vector.pdf"
        pdf = canvas.Canvas(str(vector), pagesize=letter, pageCompression=1, invariant=1)
        rows = [dict(row) for row in spec["rows"]]
        split = spec.get("break_after")
        chunks = [rows] if split is None else [rows[:split], rows[split:]]
        for page, chunk in enumerate(chunks, 1):
            for row in chunk:
                row["page"] = page
            draw_page(pdf, spec, chunk, page, len(chunks))
        pdf.save()
        out = PDF_DIR / spec["file"]
        if spec["mode"] == "digital":
            out.write_bytes(vector.read_bytes())
        else:
            writer = PdfWriter()
            source = PdfReader(str(vector))
            for page_no in range(1, len(chunks) + 1):
                if spec["mode"] == "scanned" or (spec["mode"] == "mixed" and page_no == 2):
                    scanned = raster_page(vector, page_no, temp)
                    writer.add_page(PdfReader(str(scanned)).pages[0])
                else:
                    writer.add_page(source.pages[page_no - 1])
            with out.open("wb") as stream:
                writer.write(stream)
        return out, rows, len(chunks)


def check_spec(spec: dict[str, Any]) -> None:
    for row in spec["rows"]:
        if row["role"] == "product" and spec["scenario"] != "arithmetic_mismatch":
            assert Decimal(row["quantity"]) * Decimal(row["unit_price"]) == Decimal(row["line_total"]), spec["file"]
    products = sum(Decimal(row["line_total"]) for row in spec["rows"] if row["role"] == "product")
    adjustments = sum(Decimal(row["line_total"]) for row in spec["rows"] if row["role"] != "product")
    assert products == Decimal(spec["printed_subtotal"]), spec["file"]
    if spec["scenario"] != "arithmetic_mismatch":
        assert products + adjustments == Decimal(spec["printed_total"]), spec["file"]


def main() -> None:
    install_font()
    expected = {"schema_version": 1, "notes": [
        "All supplier names, codes, references, dates, and amounts are invented.",
        "Business status is a review hint, never inferred solely from a document type.",
        "Amounts are decimal strings; charges and discounts are separate from sellable products.",
        "OCR output varies by engine; assert key terms and page behavior, not exact whitespace."
    ], "documents": []}
    for spec in SPECS:
        check_spec(spec)
        path, rows, pages = generate_pdf(spec)
        expected["documents"].append({
            "file": f"pdfs/{path.name}", "scenario": spec["scenario"],
            "mode": spec["mode"], "pages": pages,
            "supplier": spec["supplier"], "document_type": spec["document_type"],
            "reference": spec["reference"], "linked_reference": spec.get("linked_reference"),
            "date": spec["date"], "currency": spec["currency"],
            "display_decimal_separator": spec.get("display_decimal_separator", "."),
            "business_status_hint": spec["status_hint"],
            "related_group": spec.get("related_group"),
            "relationship": spec.get("relationship"),
            "rows": rows, "printed_products_subtotal": spec["printed_subtotal"],
            "printed_document_total": spec["printed_total"],
            "expected_warnings": spec.get("expected_warnings", []),
            "ocr_assertions": spec.get("ocr_assertions", []),
        })
        print(f"{path.name}: {pages} page(s), {path.stat().st_size} bytes")
    (ROOT / "expected.json").write_text(json.dumps(expected, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
