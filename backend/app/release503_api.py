from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from html import escape
from io import BytesIO
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models as m
from .config import settings
from .db import get_db
from .deps import ensure_workspace, get_current_user, require_csrf, require_permission
from .reports_TableFormat import _ordered_specs
from .services import audit

router = APIRouter(prefix="/api/v1/catalogue", tags=["Release 5.0.4 catalogue management"])
APPLICATIONS = {"LIGHTING", "AUTOMATION"}
ADMIN_ROLES = {"ADMIN", "SUPER_ADMIN"}


def workspace(value: str) -> str:
    value = value.upper().strip()
    if value not in APPLICATIONS: raise HTTPException(422, "Application must be LIGHTING or AUTOMATION")
    return value


def admin(user: m.User) -> None:
    if user.role not in ADMIN_ROLES: raise HTTPException(403, "Administrator access required")


def clean(value: str | None) -> str | None:
    if value is None: return None
    if re.search(r"<\s*(script|iframe|object|embed)|on\w+\s*=|javascript:", value, re.I):
        raise HTTPException(422, "Unsafe HTML is not allowed")
    return value.strip()


@router.get("/summary")
def summary(application: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    ws = workspace(application); ensure_workspace(user, ws)
    products = db.scalars(select(m.Product).where(m.Product.workspace == ws)).all()
    definitions = db.scalars(select(m.ProductSpecDefinition).where(
        m.ProductSpecDefinition.workspace == ws, m.ProductSpecDefinition.required.is_(True),
        m.ProductSpecDefinition.status == "ACTIVE")).all()
    required_by_category: dict[str, set[str]] = {}
    for definition in definitions:
        required_by_category.setdefault(definition.category_id, set()).add(definition.spec_key)
    status_counts = {key: 0 for key in ("DRAFT", "ACTIVE", "INACTIVE", "ARCHIVED")}
    for product in products: status_counts[product.status.upper()] = status_counts.get(product.status.upper(), 0) + 1
    imports = db.scalars(select(m.CatalogueImportJob).where(m.CatalogueImportJob.workspace == ws)
                         .order_by(m.CatalogueImportJob.created_at.desc()).limit(5)).all()
    return {
        "application": ws,
        "categories": db.scalar(select(func.count(m.Category.id)).where(m.Category.workspace == ws)) or 0,
        "product_families": db.scalar(select(func.count(m.ProductFamily.id)).where(m.ProductFamily.workspace == ws)) or 0,
        "products": len(products),
        "missing_images": sum(not any(media.upload_status == "READY" and not media.archived_at for media in product.media) for product in products),
        "missing_price": sum(Decimal(product.price or 0) <= 0 for product in products),
        "missing_required_specifications": sum(bool(required_by_category.get(product.category_id, set()) - set((product.specs or {}).keys())) for product in products),
        "status_counts": status_counts,
        "recent_imports": [{"id": row.id, "file_name": row.file_name, "status": row.status,
                            "failed_rows": row.failed_rows, "created_at": row.created_at} for row in imports],
    }


class PublicationIn(BaseModel):
    application: str
    name: str = Field(min_length=1, max_length=180)
    code: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    version: str = Field(min_length=1, max_length=40)
    cover_title: str = Field(min_length=1, max_length=180)
    cover_subtitle: str | None = Field(default=None, max_length=300)
    introduction: str | None = None
    price_mode: str = "NONE"
    category_ids: list[str] = []
    product_ids: list[str] = []
    include_inactive: bool = False
    include_out_of_stock: bool = True
    include_specifications: bool = True
    include_features: bool = True
    include_applications: bool = True
    confidentiality: str | None = Field(default=None, max_length=180)
    effective_date: date | None = None
    expiry_date: date | None = None

    @model_validator(mode="after")
    def validate_options(self):
        self.price_mode = self.price_mode.upper()
        if self.price_mode not in {"NONE", "BASE", "MRP"}: raise ValueError("Unsupported price display mode")
        if self.expiry_date and self.effective_date and self.expiry_date < self.effective_date:
            raise ValueError("Expiry date cannot be before effective date")
        return self


def product_snapshot(db: Session, product: m.Product, body: PublicationIn) -> dict:
    displayed_price = None
    if body.price_mode == "BASE":
        displayed_price = product.price
    elif body.price_mode == "MRP":
        displayed_price = product.mrp_price
    family = product.family
    specs = [{"label": label, "value": value} for label, value in _ordered_specs(db, product, "show_in_catalogue")] if body.include_specifications else []
    return {
        "id": product.id, "name": product.name, "family_name": family.name if family else product.name,
        "variant_name": product.variant_name, "model_number": product.model_number, "sku": product.sku,
        "brand": product.brand, "category": product.category.name, "description": product.description,
        "short_description": family.short_description if family else None,
        "full_description": family.full_description if family else None,
        "highlights": product.highlights or [],
        "features": (product.features or (family.features if family else []) or []) if body.include_features else [],
        "applications": (product.applications or (family.applications if family else []) or []) if body.include_applications else [],
        "installation_summary": product.installation_summary, "care_guide": product.care_guide,
        "warranty_summary": product.warranty_summary,
        "specifications": specs, "warranty": product.warranty, "unit": product.unit,
        "price": str(displayed_price) if displayed_price is not None else None,
        "price_mode": body.price_mode, "status": product.status,
    }


def make_snapshot(db: Session, ws: str, body: PublicationIn) -> dict:
    stmt = select(m.Product).where(m.Product.workspace == ws)
    if body.product_ids: stmt = stmt.where(m.Product.id.in_(body.product_ids))
    if body.category_ids: stmt = stmt.where(m.Product.category_id.in_(body.category_ids))
    if not body.include_inactive: stmt = stmt.where(m.Product.status == "ACTIVE")
    if not body.include_out_of_stock: stmt = stmt.where(m.Product.on_hand > m.Product.reserved)
    rows = db.scalars(stmt.order_by(m.Product.category_id, m.Product.name, m.Product.sku)).all()
    if body.product_ids and len(rows) != len(set(body.product_ids)):
        raise HTTPException(422, "One or more selected products are unavailable or outside this application")
    return {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
            "application": ws, "products": [product_snapshot(db, row, body) for row in rows]}


def publication_json(row: m.CataloguePublication) -> dict:
    return {"id": row.id, "application": row.workspace, "name": row.name, "code": row.code,
            "version": row.version, "status": row.status, "cover_title": row.cover_title,
            "cover_subtitle": row.cover_subtitle, "price_mode": row.price_mode,
            "product_count": len((row.snapshot or {}).get("products", [])), "effective_date": row.effective_date,
            "expiry_date": row.expiry_date, "created_at": row.created_at, "published_at": row.published_at}


@router.get("/versions")
def versions(application: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    ws = workspace(application); ensure_workspace(user, ws)
    rows = db.scalars(select(m.CataloguePublication).where(m.CataloguePublication.workspace == ws)
                      .order_by(m.CataloguePublication.created_at.desc())).all()
    return [publication_json(row) for row in rows]


@router.post("/versions", dependencies=[Depends(require_csrf)])
def publish(body: PublicationIn, db: Session = Depends(get_db), user: m.User = Depends(require_permission("products.create"))):
    admin(user); ws = workspace(body.application); ensure_workspace(user, ws)
    snapshot = make_snapshot(db, ws, body)
    row = m.CataloguePublication(workspace=ws, name=" ".join(body.name.split()), code=body.code.upper(),
        version=body.version, status="PUBLISHED", cover_title=clean(body.cover_title) or body.name,
        cover_subtitle=clean(body.cover_subtitle), introduction=clean(body.introduction), price_mode=body.price_mode,
        settings={"include_inactive": body.include_inactive, "include_out_of_stock": body.include_out_of_stock,
                  "include_specifications": body.include_specifications, "include_features": body.include_features,
                  "include_applications": body.include_applications, "confidentiality": clean(body.confidentiality)},
        snapshot=snapshot, effective_date=body.effective_date, expiry_date=body.expiry_date,
        created_by=user.id, published_at=datetime.now(timezone.utc))
    db.add(row)
    try:
        db.flush()
    except Exception as exc:
        db.rollback(); raise HTTPException(409, "Catalogue code and version already exist in this application") from exc
    audit(db, user.id, "catalogue.publish", "catalogue_publication", row.id,
          {"application": ws, "products": len(snapshot["products"]), "version": row.version})
    db.commit(); return publication_json(row)


@router.post("/versions/{publication_id}/archive", dependencies=[Depends(require_csrf)])
def archive(publication_id: str, db: Session = Depends(get_db), user: m.User = Depends(require_permission("products.create"))):
    admin(user); row = db.get(m.CataloguePublication, publication_id)
    if not row: raise HTTPException(404, "Catalogue version not found")
    ensure_workspace(user, row.workspace); row.status = "ARCHIVED"
    audit(db, user.id, "catalogue.archive", "catalogue_publication", row.id, {"application": row.workspace})
    db.commit(); return publication_json(row)


def catalogue_pdf(row: m.CataloguePublication) -> bytes:
    from .reports_TableFormat import _page_frame
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=24*mm, bottomMargin=21*mm, title=f"{row.name} {row.version}")
    styles = getSampleStyleSheet()
    title = ParagraphStyle("catalogue-title", parent=styles["Title"], fontSize=28, leading=34, textColor=colors.HexColor("#10345f"))
    heading = ParagraphStyle("catalogue-heading", parent=styles["Heading1"], fontSize=18, textColor=colors.HexColor("#10345f"), spaceAfter=8)
    body = ParagraphStyle("catalogue-body", parent=styles["BodyText"], fontSize=9, leading=12)
    small = ParagraphStyle("catalogue-small", parent=body, fontSize=7.5, leading=9)
    products = (row.snapshot or {}).get("products", [])
    story = [Spacer(1, 45*mm), Paragraph(escape(row.cover_title), title)]
    if row.cover_subtitle: story += [Spacer(1, 5*mm), Paragraph(escape(row.cover_subtitle), heading)]
    story += [Spacer(1, 60*mm), Paragraph(f"<b>{escape(settings.company_name)}</b><br/>{escape(settings.company_address)}<br/>{escape(settings.company_email)} · {escape(settings.company_phone)}", body),
              Spacer(1, 8*mm), Paragraph(f"{escape(row.workspace.title())} Catalogue · {escape(row.code)} · Version {escape(row.version)}", body), PageBreak()]
    story += [Paragraph("Contents", heading)]
    for index, product in enumerate(products, 1):
        story.append(Paragraph(f"{index}. {escape(product.get('family_name') or product['name'])} — {escape(product.get('model_number') or product['sku'])}", body))
    if not products: story.append(Paragraph("No products matched the selected publication filters.", body))
    for index, product in enumerate(products, 1):
        story += [PageBreak(), Paragraph(escape(product.get("family_name") or product["name"]), heading),
                  Paragraph(f"{escape(product.get('category') or '')} · {escape(product.get('brand') or '')}", small)]
        facts = [["Model", product.get("model_number") or "—"], ["SKU", product.get("sku") or "—"],
                 ["Variant", product.get("variant_name") or product.get("name") or "—"], ["Warranty", product.get("warranty") or "—"]]
        if product.get("price") is not None: facts.append(["Approved price", f"INR {Decimal(product['price']):,.2f}"])
        table = Table([[Paragraph(f"<b>{escape(str(a))}</b>", small), Paragraph(escape(str(b)), small)] for a,b in facts], colWidths=[44*mm, 136*mm])
        table.setStyle(TableStyle([("LINEBELOW", (0,0), (-1,-1), .35, colors.HexColor("#ccd8e5")), ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#edf3f9")), ("VALIGN", (0,0), (-1,-1), "TOP"), ("PADDING", (0,0), (-1,-1), 5)]))
        story += [Spacer(1, 4*mm), table, Spacer(1, 5*mm)]
        description = product.get("full_description") or product.get("short_description") or product.get("description")
        if description: story += [Paragraph("Overview", styles["Heading2"]), Paragraph(escape(str(description)), body)]
        specs = product.get("specifications") or []
        if specs:
            rows = [[Paragraph("<b>Specification</b>", small), Paragraph("<b>Value</b>", small)]]
            for spec in specs:
                value = spec.get("value")
                if value not in (None, "", []): rows.append([Paragraph(escape(str(spec.get("label") or spec.get("key") or "Specification")), small), Paragraph(escape(str(value)), small)])
            spec_table = Table(rows, colWidths=[63*mm, 117*mm], repeatRows=1)
            spec_table.setStyle(TableStyle([("LINEBELOW", (0,0), (-1,-1), .3, colors.HexColor("#ccd8e5")), ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#10345f")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("VALIGN", (0,0), (-1,-1), "TOP"), ("PADDING", (0,0), (-1,-1), 4)]))
            story += [Spacer(1, 4*mm), Paragraph("Specifications", styles["Heading2"]), spec_table]
        for label, values in (("Highlights", product.get("highlights")), ("Features", product.get("features")), ("Applications", product.get("applications"))):
            if values: story += [Spacer(1, 4*mm), Paragraph(label, styles["Heading2"]), Paragraph(" · ".join(escape(str(v)) for v in values), body)]
        for label, value in (("Installation", product.get("installation_summary")), ("Care guide", product.get("care_guide")), ("Warranty summary", product.get("warranty_summary"))):
            if value: story += [Spacer(1, 4*mm), Paragraph(label, styles["Heading2"]), Paragraph(escape(str(value)), body)]
        story += [Spacer(1, 8*mm), Paragraph("Image unavailable" if True else "", small)]
    confidentiality = (row.settings or {}).get("confidentiality")
    story += [PageBreak(), Spacer(1, 55*mm), Paragraph("Contact", title), Spacer(1, 8*mm),
              Paragraph(f"<b>{escape(settings.company_name)}</b><br/>{escape(settings.company_address)}<br/>{escape(settings.company_email)}<br/>{escape(settings.company_phone)}", body)]
    if confidentiality: story += [Spacer(1, 20*mm), Paragraph(escape(confidentiality), small)]
    page = lambda canvas, current: _page_frame(canvas, current, row.name)
    doc.build(story, onFirstPage=page, onLaterPages=page)
    return buffer.getvalue()


@router.get("/versions/{publication_id}/pdf")
def download(publication_id: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    row = db.get(m.CataloguePublication, publication_id)
    if not row: raise HTTPException(404, "Catalogue version not found")
    ensure_workspace(user, row.workspace)
    filename = f"{row.code}-{row.version}.pdf".replace("/", "-")
    return StreamingResponse(BytesIO(catalogue_pdf(row)), media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})
