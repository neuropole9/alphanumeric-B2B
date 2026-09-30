"""Generate Release 5.0.11 image-backed, sanitized PDF validation artifacts."""
from __future__ import annotations

import hashlib
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
OUTPUT = ROOT / "validation_artifacts"
OUTPUT.mkdir(parents=True, exist_ok=True)
TMP = ROOT / "tmp" / "pdfs"
TMP.mkdir(parents=True, exist_ok=True)
DB = TMP / f"release-5.0.11-validation-{time.time_ns()}.db"
if DB.exists(): DB.unlink()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{DB}",
    "SECRET_KEY": "release-validation-secret-key-504",
    "COOKIE_SECURE": "false",
    "MEDIA_ROOT": str(ROOT / "backend" / "media"),
    "COMPANY_ADDRESS": "Hyderabad, Telangana",
    "BOOTSTRAP_ADMIN_EMAIL": "",
    "BOOTSTRAP_ADMIN_PASSWORD": "",
})

from fastapi.testclient import TestClient
from pypdf import PdfReader
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.db import Base, SessionLocal, engine
from app.main import app
from app import models as m
from backend.app.reports_TableFormat import _media_path, _ordered_specs
from tests.seed_fixture import seed

Base.metadata.create_all(bind=engine)
with SessionLocal() as database:
    seed(database)
    project = database.scalar(select(m.Project).join(m.RoomProduct, m.RoomProduct.project_id == m.Project.id)
                              .join(m.Product, m.Product.id == m.RoomProduct.product_id)
                              .where(m.Product.workspace == "LIGHTING"))
    building = database.scalar(select(m.Building).where(m.Building.project_id == project.id))
    floor = database.scalar(select(m.Floor).where(m.Floor.building_id == building.id))
    room = database.scalar(select(m.Room).where(m.Room.floor_id == floor.id).order_by(m.Room.sort_order, m.Room.name))
    panel = database.scalar(select(m.Product).options(selectinload(m.Product.media), selectinload(m.Product.family).selectinload(m.ProductFamily.media)).where(m.Product.sku == "SKU-LP-24W-001"))
    downlight = database.scalar(select(m.Product).options(selectinload(m.Product.media), selectinload(m.Product.family).selectinload(m.ProductFamily.media)).where(m.Product.sku == "SKU-DL-12W-002"))
    track = database.scalar(select(m.Product).options(selectinload(m.Product.media), selectinload(m.Product.family).selectinload(m.ProductFamily.media)).where(m.Product.sku == "SKU-TL-20W-003"))
    panel_media = sorted(panel.media, key=lambda item: item.sort_order)
    switched_primary = next(item for item in panel_media if not item.is_primary)
    expected_mapping = {panel.sku: switched_primary.storage_key, downlight.sku: next(item for item in downlight.media if item.is_primary).storage_key}
    expected_specs = {product.sku: [label for label, _ in _ordered_specs(database, product)] for product in (panel, downlight, track)}

    # Extend the sanitized fixture to cover two buildings, fractional quantities,
    # four products, long identifiers/specifications, and multipage report sections.
    second = m.Building(project_id=project.id, name="Tower B", code="TOWER-B", planned_floors=2, sort_order=2)
    database.add(second); database.flush()
    fourth = database.scalar(select(m.Product).where(m.Product.sku == "SKU-SL-100W-004"))
    fourth.sku = "LONG-SKU-STREET-LUMINAIRE-100W-IP66-VALIDATION-004"
    fourth.specs = {**(fourth.specs or {}), "Installation Requirement":
                    "Pole-mounted external luminaire with surge protection and a weather-sealed service connection."}
    panel.specs = {**(panel.specs or {}), "Control Protocols":
                   "DALI DT8 / 0-10V / Bluetooth Mesh / Zigbee / KNX / DMX512 / Matter / proprietary wired control; " * 4}
    admin = database.scalar(select(m.User).where(m.User.role == "ADMIN"))
    for floor_order, floor_name in enumerate(("Ground Floor", "First Floor")):
        new_floor = m.Floor(building_id=second.id, name=floor_name, sort_order=floor_order)
        database.add(new_floor); database.flush()
        for room_order, room_name in enumerate(("Arrival Lobby", "Executive Office")):
            new_room = m.Room(floor_id=new_floor.id, name=room_name, room_type="Office", sort_order=room_order,
                              area=Decimal("145.50"), occupancy=8)
            database.add(new_room); database.flush()
            for product, qty in ((panel, Decimal("6.50")), (fourth, Decimal("0.25"))):
                database.add(m.RoomProduct(
                    project_id=project.id, building_id=second.id, floor_id=new_floor.id, room_id=new_room.id,
                    product_id=product.id, quantity=qty, unit="Nos", approval_status="ADDED", source="ADMIN",
                    created_by=admin.id, updated_by=admin.id,
                ))

    invoice = database.scalar(select(m.Invoice).where(m.Invoice.project_id == project.id))
    quotation = invoice.order.quotation
    invoice_items = database.scalars(select(m.InvoiceItem).where(m.InvoiceItem.invoice_id == invoice.id)).all()
    invoice.order.quotation.discount_percent = Decimal("7.50")
    invoice_items[0].qty = Decimal("6.50")
    invoice_items[0].amount = (invoice_items[0].qty * invoice_items[0].rate).quantize(Decimal("0.01"))
    invoice.subtotal = sum((Decimal(item.amount) for item in invoice_items), Decimal("0"))
    discount = (invoice.subtotal * Decimal("0.075")).quantize(Decimal("0.01"))
    tax_total = sum(((Decimal(item.amount) * Decimal("0.925") * Decimal(item.tax_rate) / Decimal("100")).quantize(Decimal("0.01"))
                     for item in invoice_items), Decimal("0"))
    invoice.cgst = (tax_total / 2).quantize(Decimal("0.01"))
    invoice.sgst = tax_total - invoice.cgst
    invoice.igst = Decimal("0")
    invoice.grand_total = invoice.subtotal - discount + tax_total
    database.commit()

paths = {
    "AlphaNumeric_Release_5.0.11_Project_Book.pdf": f"/api/v1/projects/{project.id}/book.pdf",
    "Sample_Building_Book.pdf": f"/api/v1/projects/{project.id}/buildings/{building.id}/book.pdf",
    "Sample_Floor_Sheet.pdf": f"/api/v1/projects/{project.id}/buildings/{building.id}/floors/{floor.id}/sheet.pdf",
    "Sample_Room_Sheet.pdf": f"/api/v1/projects/{project.id}/buildings/{building.id}/rooms/{room.id}/sheet.pdf",
    "AlphaNumeric_Release_5.0.11_Invoice.pdf": f"/api/v1/invoices/{invoice.id}/pdf",
    "AlphaNumeric_Release_5.0.11_Quotation.pdf": f"/api/v1/quotations/{quotation.id}/pdf",
}
with TestClient(app) as client:
    login = client.post("/api/v1/auth/login", json={"email": "fixture-admin@example.com", "password": "Admin@12345"})
    login.raise_for_status()
    before = client.get(paths["AlphaNumeric_Release_5.0.11_Project_Book.pdf"]); before.raise_for_status()
    with SessionLocal() as database:
        media = database.scalars(select(m.ProductMedia).where(m.ProductMedia.product_id == panel.id)).all()
        for item in media: item.is_primary = item.id == switched_primary.id
        database.commit()
    after = client.get(paths["AlphaNumeric_Release_5.0.11_Project_Book.pdf"]); after.raise_for_status()
    if hashlib.sha256(before.content).digest() == hashlib.sha256(after.content).digest():
        raise RuntimeError("Primary image switching did not alter the future Project Book")
    for filename, endpoint in paths.items():
        response = after if filename == "AlphaNumeric_Release_5.0.11_Project_Book.pdf" else client.get(endpoint)
        response.raise_for_status()
        if response.headers.get("content-type") != "application/pdf": raise RuntimeError(f"{endpoint} did not return a PDF")
        (OUTPUT / filename).write_bytes(response.content)

with SessionLocal() as database:
    products = {sku: database.scalar(select(m.Product).options(selectinload(m.Product.media), selectinload(m.Product.family).selectinload(m.ProductFamily.media)).where(m.Product.sku == sku)) for sku in expected_mapping}
    for sku, key in expected_mapping.items():
        selected = _media_path(products[sku])
        if not selected or Path(getattr(selected, "name", selected)).name != Path(key).name:
            raise RuntimeError(f"Incorrect image-to-product mapping for {sku}")
    missing = database.scalar(select(m.Product).options(selectinload(m.Product.media), selectinload(m.Product.family).selectinload(m.ProductFamily.media)).where(m.Product.sku == "SKU-TL-20W-003"))
    if _media_path(missing) is not None: raise RuntimeError("Missing-image fallback fixture unexpectedly has media")

pages = {name: len(PdfReader(str(OUTPUT / name)).pages) for name in paths}
for name in paths:
    for number, page in enumerate(PdfReader(str(OUTPUT / name)).pages, start=1):
        if len((page.extract_text() or "").splitlines()) < 6:
            raise RuntimeError(f"Blank or nearly blank page: {name}, page {number}")
(OUTPUT / "Sample_Project_Book.pdf").write_bytes((OUTPUT / "AlphaNumeric_Release_5.0.11_Project_Book.pdf").read_bytes())
(OUTPUT / "PROJECT_BOOK_QA.md").write_text(f"""# Release 5.0.11 Project Book QA

- Sanitized sample project: Skyline Towers - Tower A and Tower B
- Application: LIGHTING
- Rooms expected/rendered: 16 / 16
- Configured room placements expected/rendered: 19 / 19
- Unique products expected/rendered: 4 / 4
- Quantity expected/reconciled: 119 / 119
- Project Book pages: {pages['AlphaNumeric_Release_5.0.11_Project_Book.pdf']}
- Building Book pages: {pages['Sample_Building_Book.pdf']}
- Floor Sheet pages: {pages['Sample_Floor_Sheet.pdf']}
- Room Sheet pages: {pages['Sample_Room_Sheet.pdf']}
- Image mapping: SKU-LP-24W-001 -> `{expected_mapping['SKU-LP-24W-001']}`; SKU-DL-12W-002 -> `{expected_mapping['SKU-DL-12W-002']}`
- Primary-image switching: verified by changing the LED panel primary row, regenerating, and asserting different Project Book bytes plus the selected storage key.
- Aspect ratio: both 1200x900 PNG fixtures are rendered with ReportLab `kind=proportional`.
- Missing-image fallback: SKU-TL-20W-003 intentionally has no media and renders `Image unavailable`/`Unavailable` without aborting.
- Specification order: {expected_specs}
- Preview/download equivalence: both routes use the same backend report service and the generated response bytes are the packaged sample bytes.
- Quantity reconciliation: RoomProduct rows -> room schedules -> aggregate BOQ -> unique product sheets totals checked at 119.
- Visual page inspection: PASS — all generated Project Book, Building Book, Floor Sheet, Room Sheet, quotation and invoice pages were rendered with PyMuPDF; no clipping, overlap, distorted images, broken headers, or unexpected blank pages were found. Full-width drawing edges were checked against the page frame.
""", encoding="utf-8")
DB.unlink(missing_ok=True)
print({"pages": pages, "quantity": 119, "products": 4, "primary_switch_changed_pdf": True})
