from io import BytesIO
from types import SimpleNamespace

from fastapi.testclient import TestClient
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate

from app.main import app
from app.db import Base, SessionLocal, engine
from app.pdf_format import compact_decimal, indian_number, inr, percent
from backend.app import reports_TableFormat
from app import models as m
from app.pdf import quotation_pdf
from sqlalchemy import select
from app.services import invoice_tax_split
from tests.seed_fixture import seed


Base.metadata.create_all(bind=engine)
with SessionLocal() as _database:
    seed(_database)


def _text(payload: bytes) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(payload)).pages)


def _login(client: TestClient) -> None:
    response = client.post("/api/v1/auth/login", json={
        "email": "fixture-admin@example.com", "password": "Admin@12345",
    })
    assert response.status_code == 200


def test_shared_pdf_numeric_formatters_are_decimal_safe():
    assert compact_decimal("12.00") == "12"
    assert compact_decimal("6.50") == "6.5"
    assert compact_decimal("0.25") == "0.25"
    assert indian_number("12345678.5") == "1,23,45,678.50"
    assert inr("12345678.5") == "INR 1,23,45,678.50"
    assert percent("18.00") == "18%"


def test_invoice_tax_components_are_mutually_exclusive_by_jurisdiction():
    intra = invoice_tax_split("180.00", "Telangana", "Hyderabad, Telangana")
    assert intra == {"cgst": 90, "sgst": 90, "igst": 0}
    inter = invoice_tax_split("180.00", "Karnataka", "Hyderabad, Telangana")
    assert inter == {"cgst": 0, "sgst": 0, "igst": 180}


def test_project_book_uses_cards_room_subtotal_and_tax_only_in_final_summary():
    with TestClient(app) as client:
        _login(client)
        project = next(row for row in client.get("/api/v1/projects").json()
                       if row["name"] == "Skyline Towers - Tower A")
        response = client.get(f"/api/v1/projects/{project['id']}/book.pdf")
        assert response.status_code == 200
        text = _text(response.content)
        assert "Room Subtotal Before Tax" in text
        assert "Aggregated Bill of Quantities" in text
        assert "Project Overview" in text and "Application" in text
        assert "Main Board Details" not in text
        assert "Room type" not in text and "Occupancy" not in text
        assert "Financial Summary" in text
        pages = PdfReader(BytesIO(response.content)).pages
        assert all((page.extract_text() or "").count("Room Configuration ·") ==
                   (page.extract_text() or "").count("Room Subtotal Before Tax")
                   for page in pages)
        assert "Taxable Value" in text
        assert "12.00 Nos" not in text
        assert "6.00 Nos" not in text
        room_section = text.split("Room Configuration", 1)[1].split("Aggregated Bill of Quantities", 1)[0]
        assert "CGST" not in room_section and "SGST" not in room_section and "IGST" not in room_section


def test_invoice_is_distinct_complete_and_preview_matches_download_content():
    with TestClient(app) as client:
        _login(client)
        invoice = client.get("/api/v1/invoices?workspace=LIGHTING").json()[0]
        preview = client.get(f"/api/v1/invoices/{invoice['id']}/pdf")
        download = client.get(f"/api/v1/invoices/{invoice['id']}/pdf?download=true")
        assert preview.status_code == download.status_code == 200
        preview_text, download_text = _text(preview.content), _text(download.content)
        assert preview_text == download_text
        for label in ["TAX INVOICE", "Invoice No.", "Due Date", "Place of Supply", "Bill To",
                      "Ship To / Project", "HSN/SAC", "Discount", "Taxable", "Amount in Words",
                      "Payment Status", "Bank / Payment Details", "Authorized Signatory"]:
            assert label in preview_text
        assert "QUOTATION" not in preview_text.upper()
        assert "CGST" in preview_text and "SGST" in preview_text and "IGST" not in preview_text
        assert "12.00 Nos" not in preview_text
        assert preview.headers["content-disposition"].startswith("inline;")
        assert download.headers["content-disposition"].startswith("attachment;")


def test_technical_aliases_and_two_compact_cards(monkeypatch):
    monkeypatch.setattr(reports_TableFormat, "_ordered_specs", lambda *args: [])
    monkeypatch.setattr(reports_TableFormat, "_media_path", lambda product: None)
    product = SimpleNamespace(family=None, name="Downlight", model_number="DL-12", variant_name="Other",
                              sku="STOCK-12", warranty="3 years", warranty_summary=None,
                              specs={"Burning Hours": "50000 h", "Body Material": "Aluminium",
                                     "Input Voltage": "220-240 V", "Control Protocols": ["DALI", "Zigbee"]})
    details = dict(reports_TableFormat._technical_details(None, product, 2, "Nos"))
    assert details["Model"] == "DL-12"
    assert details["Rated Life"] == "50000 h"
    assert details["Body Materials"] == "Aluminium"
    assert details["Control Protocols"] == "DALI / Zigbee"
    assert details["CRI"] is None
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=24*mm, bottomMargin=21*mm)
    styles = reports_TableFormat._styles()
    story = [Paragraph("Product Technical Specifications", styles["h1"])]
    for _ in range(2):
        story.extend(reports_TableFormat._technical_card(None, product, 2, "Nos", styles))
    doc.build(story)
    cards_pdf = PdfReader(BytesIO(buffer.getvalue()))
    assert len(cards_pdf.pages) == 1
    card_text = cards_pdf.pages[0].extract_text()
    assert card_text.count("Model: DL-12") == 2
    for excluded in ("CRI", "Placement", "Description", "Highlights", "Care guide", "Installation"):
        assert excluded not in card_text


def test_room_and_floor_sheets_show_client_location_and_product_counts_only():
    with SessionLocal() as db:
        room = db.scalars(select(m.Room)).first()
        floor = room.floor
        room_text = _text(reports_TableFormat.room_sheet_pdf(db, room, True))
        floor_text = _text(reports_TableFormat.floor_sheet_pdf(db, floor, True))
    room_header = room_text.split("Complete Product List", 1)[0]
    floor_schedule = floor_text.split("Room Schedule", 1)[1].split("Product Technical Specifications", 1)[0]
    for excluded in ("Room type", "Occupancy", "Main Boards", "No main boards"):
        assert excluded not in room_header
        assert excluded not in floor_schedule
    assert "Room Schedule" in floor_text and "Quantity" in floor_text


def test_long_protocol_value_paginates_without_clipping(monkeypatch):
    monkeypatch.setattr(reports_TableFormat, "_ordered_specs", lambda *args: [])
    monkeypatch.setattr(reports_TableFormat, "_media_path", lambda product: None)
    long_protocol = " ".join(["Protocol-Zigbee-DT8"] * 600)
    product = SimpleNamespace(family=None, name="Controller", model_number=None,
                              variant_name="Smart", sku="CTRL-1", warranty=None, warranty_summary=None,
                              specs={"Control Protocols": long_protocol})
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=24*mm, bottomMargin=21*mm)
    doc.build(reports_TableFormat._technical_card(None, product, 1, "Nos", reports_TableFormat._styles()))
    pages = PdfReader(BytesIO(buffer.getvalue())).pages
    assert len(pages) >= 2
    assert sum((page.extract_text() or "").count("Protocol-Zigbee-DT8") for page in pages) == 600


def test_quotation_appendix_has_no_trailing_empty_page():
    with SessionLocal() as db:
        quotation = db.scalars(select(m.Quotation)).first()
        pages = PdfReader(BytesIO(quotation_pdf(db, quotation))).pages
    assert pages
    assert all(len((page.extract_text() or "").strip()) > 70 for page in pages)
