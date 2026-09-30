from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import re
import secrets
import struct
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from . import models as m
from .api import admin_required, product_out
from .config import settings
from .db import get_db
from .deps import ensure_workspace, get_current_user, require_csrf
from .services import audit
from .media_storage import get_media_provider, safe_component
from .release5_api import normalize_spec, upload_product_image as release5_upload_product_image

router = APIRouter(prefix="/api/v1", tags=["catalogue"])
ADMIN_ROLES = {"ADMIN", "SUPER_ADMIN"}


class FamilyIn(BaseModel):
    workspace: str
    category_id: str
    name: str = Field(min_length=1, max_length=180)
    brand: str = Field(default="AlphaNumeric", min_length=1, max_length=100)
    short_description: str | None = Field(default=None, max_length=500)
    full_description: str | None = None
    features: list[str] = []
    applications: list[str] = []
    suitability_guidance: str | None = None
    status: str = "ACTIVE"


class FamilyPatch(BaseModel):
    category_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=180)
    brand: str | None = Field(default=None, min_length=1, max_length=100)
    short_description: str | None = Field(default=None, max_length=500)
    full_description: str | None = None
    features: list[str] | None = None
    applications: list[str] | None = None
    suitability_guidance: str | None = None
    status: str | None = None


class VariantIn(BaseModel):
    sku: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=180)
    internal_name: str | None = Field(default=None, max_length=180)
    variant_name: str | None = Field(default=None, max_length=180)
    model_number: str | None = Field(default=None, max_length=100)
    barcode: str | None = Field(default=None, max_length=100)
    manufacturer: str | None = Field(default=None, max_length=120)
    search_tags: list[str] = []
    description: str | None = None
    full_description: str | None = None
    highlights: list[str] = []
    features: list[str] = []
    applications: list[str] = []
    installation_summary: str | None = None
    care_guide: str | None = None
    warranty_summary: str | None = None
    internal_notes: str | None = None
    unit: str = Field(default="Nos", min_length=1, max_length=30)
    price: Decimal = Field(default=0, ge=0)
    cost: Decimal | None = Field(default=None, ge=0)
    mrp_price: Decimal | None = Field(default=None, ge=0)
    project_price: Decimal | None = Field(default=None, ge=0)
    dealer_price: Decimal | None = Field(default=None, ge=0)
    reseller_price: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    minimum_order_quantity: Decimal = Field(default=1, gt=0)
    pricing_status: str = Field(default="DRAFT", pattern=r"^(DRAFT|PRICE_REQUIRED|PENDING_APPROVAL|APPROVED|REJECTED)$")
    tax_rate: Decimal = Field(default=18, ge=0, le=100)
    hsn_sac: str | None = Field(default=None, max_length=32)
    on_hand: Decimal = Field(default=0, ge=0)
    reorder_level: Decimal = Field(default=10, ge=0)
    specs: dict[str, Any] = {}
    lead_time_days: int | None = Field(default=None, ge=0)
    warranty: str | None = Field(default=None, max_length=120)
    status: str = "ACTIVE"


class VariantPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    internal_name: str | None = Field(default=None, max_length=180)
    variant_name: str | None = Field(default=None, max_length=180)
    model_number: str | None = Field(default=None, max_length=100)
    barcode: str | None = Field(default=None, max_length=100)
    manufacturer: str | None = Field(default=None, max_length=120)
    search_tags: list[str] | None = None
    description: str | None = None
    full_description: str | None = None
    highlights: list[str] | None = None
    features: list[str] | None = None
    applications: list[str] | None = None
    installation_summary: str | None = None
    care_guide: str | None = None
    warranty_summary: str | None = None
    internal_notes: str | None = None
    unit: str | None = Field(default=None, min_length=1, max_length=30)
    price: Decimal | None = Field(default=None, ge=0)
    cost: Decimal | None = Field(default=None, ge=0)
    mrp_price: Decimal | None = Field(default=None, ge=0)
    project_price: Decimal | None = Field(default=None, ge=0)
    dealer_price: Decimal | None = Field(default=None, ge=0)
    reseller_price: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    minimum_order_quantity: Decimal | None = Field(default=None, gt=0)
    pricing_status: str | None = Field(default=None, pattern=r"^(DRAFT|PRICE_REQUIRED|PENDING_APPROVAL|APPROVED|REJECTED)$")
    tax_rate: Decimal | None = Field(default=None, ge=0, le=100)
    hsn_sac: str | None = Field(default=None, max_length=32)
    reorder_level: Decimal | None = Field(default=None, ge=0)
    specs: dict[str, Any] | None = None
    lead_time_days: int | None = Field(default=None, ge=0)
    warranty: str | None = Field(default=None, max_length=120)
    status: str | None = None


class MediaPatch(BaseModel):
    alt_text: str | None = Field(default=None, min_length=1, max_length=255)
    caption: str | None = Field(default=None, max_length=500)
    sort_order: int | None = Field(default=None, ge=0)
    is_primary: bool | None = None


PRICE_FIELDS = {
    "cost": "COST", "price": "BASE", "mrp_price": "MRP",
    "project_price": "PROJECT", "dealer_price": "DEALER", "reseller_price": "RESELLER",
}


def _safe_content(value: str | None) -> str | None:
    if value is None:
        return None
    if re.search(r"<\s*(script|iframe|object|embed)|on\w+\s*=|javascript:", value, re.I):
        raise HTTPException(422, "Unsafe product content is not allowed")
    return value.strip()


def _safe_items(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    cleaned = [_safe_content(value) for value in values]
    return [value for value in cleaned if value]


def _record_prices(db: Session, product: m.Product, changes: dict[str, Any], user_id: str) -> None:
    now = datetime.now(timezone.utc)
    for field, price_type in PRICE_FIELDS.items():
        if field not in changes or changes[field] is None:
            continue
        amount = Decimal(changes[field])
        current = db.scalar(select(m.ProductPriceHistory).where(
            m.ProductPriceHistory.product_id == product.id,
            m.ProductPriceHistory.price_type == price_type,
            m.ProductPriceHistory.effective_until.is_(None),
        ).order_by(m.ProductPriceHistory.effective_from.desc()))
        if current and Decimal(current.amount) == amount and current.currency == product.currency:
            continue
        if current:
            current.effective_until = now
        db.add(m.ProductPriceHistory(
            product_id=product.id, price_type=price_type, amount=amount,
            currency=changes.get("currency") or product.currency or "INR",
            effective_from=now, status="APPROVED" if product.pricing_status == "APPROVED" else "DRAFT",
            approved_by=user_id if product.pricing_status == "APPROVED" else None,
            created_by=user_id,
        ))


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:170] or "product"


def _unique_slug(db: Session, workspace: str, name: str, ignore_id: str | None = None) -> str:
    base = _slug(name)
    value = base
    counter = 2
    while db.scalar(select(m.ProductFamily.id).where(
        m.ProductFamily.workspace == workspace,
        m.ProductFamily.slug == value,
        *([m.ProductFamily.id != ignore_id] if ignore_id else []),
    )):
        value = f"{base[:160]}-{counter}"
        counter += 1
    return value


def _media_out(row: m.ProductMedia) -> dict:
    return {
        "id": row.id,
        "url": f"/api/v1/product-media/{row.id}/secure-file" if row.provider_file_id else f"/api/v1/product-media/{row.id}/file",
        "media_type": row.media_type,
        "alt_text": row.alt_text,
        "caption": row.caption,
        "sort_order": row.sort_order,
        "is_primary": row.is_primary,
        "width": row.width,
        "height": row.height,
    }


def _natural_model_key(value: str) -> tuple:
    return tuple((0, int(part)) if part.isdigit() else (1, part.casefold())
                 for part in re.split(r"(\d+)", value or ""))


def _family_out(db: Session, family: m.ProductFamily, user: m.User, detailed: bool = False) -> dict:
    variants = sorted(
        (item for item in family.variants if item.status == "ACTIVE" or user.role in ADMIN_ROLES),
        key=lambda item: (_natural_model_key(item.variant_name or item.model_number or item.name), item.sku),
    )
    # Family gallery contains only true family-level media; variant media stays scoped to its variant.
    media = sorted(
        [item for item in family.media if item.product_id is None and item.archived_at is None],
        key=lambda item: (not item.is_primary, item.sort_order, item.created_at, item.id),
    )
    primary = next((x for x in media if x.is_primary), media[0] if media else None)
    if primary is None:
        representative = [item for variant in variants for item in (variant.media or []) if item.archived_at is None and item.upload_status == "READY"]
        representative.sort(key=lambda item: (not item.is_primary, item.sort_order, item.created_at, item.id))
        primary = representative[0] if representative else None
    available = sum((max(Decimal("0"), Decimal(v.available)) for v in variants if v.status == "ACTIVE"), Decimal("0"))
    prices = [Decimal(v.price) for v in variants if v.status == "ACTIVE"]
    result = {
        "id": family.id,
        "workspace": family.workspace,
        "category_id": family.category_id,
        "category": family.category.name if family.category else "",
        "name": family.name,
        "slug": family.slug,
        "brand": family.brand,
        "short_description": family.short_description,
        "full_description": family.full_description,
        "features": family.features or [],
        "applications": family.applications or [],
        "suitability_guidance": family.suitability_guidance,
        "status": family.status,
        "variant_count": len(variants),
        "available": float(available),
        "availability": "IN_STOCK" if available > 0 else "OUT_OF_STOCK",
        "primary_image_url": (f"/api/v1/product-media/{primary.id}/secure-file" if primary and primary.provider_file_id else f"/api/v1/product-media/{primary.id}/file") if primary else None,
        "media": [_media_out(x) for x in media],
        "created_at": family.created_at.isoformat() if family.created_at else None,
        "updated_at": family.updated_at.isoformat() if family.updated_at else None,
    }
    if user.role in ADMIN_ROLES and prices:
        result["starting_price"] = float(min(prices))
    if detailed:
        result["variants"] = [product_out(v, include_price=user.role in ADMIN_ROLES) for v in variants]
    return result


@router.get("/product-families")
def list_families(
    workspace: str | None = None,
    category_id: str | None = None,
    brand: str | None = None,
    availability: str | None = None,
    q: str | None = None,
    sort: str = Query("name", pattern="^(name|newest|brand)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    stmt = select(m.ProductFamily).options(
        selectinload(m.ProductFamily.category),
        selectinload(m.ProductFamily.variants).selectinload(m.Product.category),
        selectinload(m.ProductFamily.variants).selectinload(m.Product.media),
        selectinload(m.ProductFamily.media),
    ).where(m.ProductFamily.status == "ACTIVE")
    if workspace:
        value = workspace.upper()
        ensure_workspace(user, value)
        stmt = stmt.where(m.ProductFamily.workspace == value)
    elif user.role not in ADMIN_ROLES:
        stmt = stmt.where(m.ProductFamily.workspace.in_([str(x).upper() for x in (user.workspaces or [])]))
    if category_id:
        stmt = stmt.where(m.ProductFamily.category_id == category_id)
    if brand:
        stmt = stmt.where(func.lower(m.ProductFamily.brand) == brand.lower())
    if q:
        term = f"%{q.strip()}%"
        stmt = stmt.where(or_(
            m.ProductFamily.name.ilike(term),
            m.ProductFamily.brand.ilike(term),
            m.ProductFamily.id.in_(select(m.Product.family_id).where(m.Product.sku.ilike(term))),
        ))
    order = m.ProductFamily.created_at.desc() if sort == "newest" else (
        m.ProductFamily.brand.asc() if sort == "brand" else m.ProductFamily.name.asc()
    )
    families = db.scalars(stmt.order_by(order)).unique().all()
    if availability:
        want = availability.upper()
        families = [family for family in families if _family_out(db, family, user)["availability"] == want]
    total = len(families)
    start = (page - 1) * page_size
    items = families[start:start + page_size]
    brands = sorted({family.brand for family in families})
    return {"items": [_family_out(db, family, user) for family in items], "page": page,
            "page_size": page_size, "total": total, "pages": max(1, (total + page_size - 1) // page_size),
            "brands": brands}


@router.post("/product-families", dependencies=[Depends(require_csrf)])
def create_family(body: FamilyIn, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    workspace = body.workspace.upper()
    ensure_workspace(user, workspace)
    category = db.get(m.Category, body.category_id)
    if not category or category.workspace != workspace:
        raise HTTPException(422, "Category does not belong to the selected workspace")
    family = m.ProductFamily(**body.model_dump(exclude={"workspace", "status"}), workspace=workspace,
                             status=body.status.upper(), slug=_unique_slug(db, workspace, body.name))
    db.add(family); db.flush()
    audit(db, user.id, "product_family.created", "product_family", family.id)
    db.commit(); db.refresh(family)
    return _family_out(db, family, user, True)


@router.get("/product-families/{family_id}")
def family_detail(family_id: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    family = db.scalar(select(m.ProductFamily).options(
        selectinload(m.ProductFamily.category),
        selectinload(m.ProductFamily.variants).selectinload(m.Product.category),
        selectinload(m.ProductFamily.variants).selectinload(m.Product.media),
        selectinload(m.ProductFamily.media),
    ).where(m.ProductFamily.id == family_id))
    if not family:
        raise HTTPException(404, "Product family not found")
    ensure_workspace(user, family.workspace)
    return _family_out(db, family, user, True)


@router.patch("/product-families/{family_id}", dependencies=[Depends(require_csrf)])
def update_family(family_id: str, body: FamilyPatch, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    family = db.get(m.ProductFamily, family_id)
    if not family:
        raise HTTPException(404, "Product family not found")
    data = body.model_dump(exclude_unset=True)
    if "category_id" in data:
        category = db.get(m.Category, data["category_id"])
        if not category or category.workspace != family.workspace:
            raise HTTPException(422, "Category does not belong to this family workspace")
    if "name" in data:
        family.slug = _unique_slug(db, family.workspace, data["name"], family.id)
    for field, value in data.items():
        setattr(family, field, value.upper() if field == "status" and value else value)
    audit(db, user.id, "product_family.updated", "product_family", family.id)
    db.commit(); return _family_out(db, family, user, True)


@router.post("/product-families/{family_id}/variants", dependencies=[Depends(require_csrf)])
def create_variant(family_id: str, body: VariantIn, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    family = db.get(m.ProductFamily, family_id)
    if not family:
        raise HTTPException(404, "Product family not found")
    if db.scalar(select(m.Product.id).where(func.lower(m.Product.sku) == body.sku.lower())):
        raise HTTPException(409, "SKU already exists")
    normalized_specs = _validate_specs(db, family.category_id, body.specs, family.id,
                                       workspace=family.workspace)
    data = body.model_dump(exclude={"status", "specs"})
    for field in ("description", "full_description", "installation_summary", "care_guide", "warranty_summary", "internal_notes"):
        data[field] = _safe_content(data.get(field))
    for field in ("search_tags", "highlights", "features", "applications"):
        data[field] = _safe_items(data.get(field)) or []
    product = m.Product(**data, specs=normalized_specs, status=body.status.upper(),
                        family_id=family.id, workspace=family.workspace, category_id=family.category_id,
                        brand=family.brand, images=[])
    db.add(product); db.flush(); _record_prices(db, product, data, user.id)
    audit(db, user.id, "product_variant.created", "product", product.id, {"family_id": family.id})
    try:
        db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "SKU already exists")
    db.refresh(product)
    return product_out(product, True)


@router.patch("/product-variants/{variant_id}", dependencies=[Depends(require_csrf)])
def update_variant(variant_id: str, body: VariantPatch, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    product = db.get(m.Product, variant_id)
    if not product:
        raise HTTPException(404, "Product variant not found")
    if body.specs is not None:
        body.specs = _validate_specs(db, product.category_id, body.specs, product.family_id,
                                     workspace=product.workspace, existing=product.specs or {})
    data = body.model_dump(exclude_unset=True)
    for field in ("description", "full_description", "installation_summary", "care_guide", "warranty_summary", "internal_notes"):
        if field in data: data[field] = _safe_content(data[field])
    for field in ("search_tags", "highlights", "features", "applications"):
        if field in data: data[field] = _safe_items(data[field]) or []
    for field, value in data.items():
        setattr(product, field, value.upper() if field == "status" and value else value)
    _record_prices(db, product, data, user.id)
    audit(db, user.id, "product_variant.updated", "product", product.id)
    db.commit(); return product_out(product, True)


class PriceHistoryIn(BaseModel):
    price_type: str = Field(pattern=r"^(COST|BASE|MRP|PROJECT|DEALER|RESELLER)$")
    amount: Decimal = Field(ge=0)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    tax_inclusive: bool = False
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    status: str = Field(default="APPROVED", pattern=r"^(DRAFT|PENDING_APPROVAL|APPROVED|REJECTED)$")
    approval_note: str | None = Field(default=None, max_length=500)


def _price_out(row: m.ProductPriceHistory) -> dict:
    return {"id": row.id, "product_id": row.product_id, "price_type": row.price_type,
            "amount": float(row.amount), "currency": row.currency, "tax_inclusive": row.tax_inclusive,
            "effective_from": row.effective_from, "effective_until": row.effective_until,
            "status": row.status, "approval_note": row.approval_note,
            "approved_by": row.approved_by, "created_by": row.created_by, "created_at": row.created_at}


@router.get("/product-variants/{variant_id}/prices")
def price_history(variant_id: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user); product = db.get(m.Product, variant_id)
    if not product: raise HTTPException(404, "Product variant not found")
    ensure_workspace(user, product.workspace)
    rows = db.scalars(select(m.ProductPriceHistory).where(m.ProductPriceHistory.product_id == variant_id)
                      .order_by(m.ProductPriceHistory.effective_from.desc(), m.ProductPriceHistory.created_at.desc())).all()
    return [_price_out(row) for row in rows]


@router.post("/product-variants/{variant_id}/prices", dependencies=[Depends(require_csrf)])
def add_price_history(variant_id: str, body: PriceHistoryIn, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user); product = db.get(m.Product, variant_id)
    if not product: raise HTTPException(404, "Product variant not found")
    ensure_workspace(user, product.workspace)
    start = body.effective_from or datetime.now(timezone.utc)
    if start.tzinfo is None: start = start.replace(tzinfo=timezone.utc)
    end = body.effective_until
    if end and end.tzinfo is None: end = end.replace(tzinfo=timezone.utc)
    if end and end <= start:
        raise HTTPException(422, "Price end date must be after its start date")
    overlaps = db.scalars(select(m.ProductPriceHistory).where(
        m.ProductPriceHistory.product_id == variant_id,
        m.ProductPriceHistory.price_type == body.price_type,
        m.ProductPriceHistory.status == "APPROVED",
        m.ProductPriceHistory.effective_from < (end or datetime.max.replace(tzinfo=timezone.utc)),
        or_(m.ProductPriceHistory.effective_until.is_(None), m.ProductPriceHistory.effective_until > start),
    )).all() if body.status == "APPROVED" else []
    for existing in overlaps:
        existing_start = existing.effective_from if existing.effective_from.tzinfo else existing.effective_from.replace(tzinfo=timezone.utc)
        if existing.effective_until is None and existing_start <= start and start > datetime.now(timezone.utc):
            existing.effective_until = start
        else:
            raise HTTPException(409, "An approved price already overlaps this effective period")
    row = m.ProductPriceHistory(**body.model_dump(exclude={"effective_from", "effective_until", "approval_note"}),
        product_id=variant_id, effective_from=start, effective_until=end, approval_note=_safe_content(body.approval_note),
        approved_by=user.id if body.status == "APPROVED" else None, created_by=user.id)
    db.add(row)
    if body.status == "APPROVED" and start <= datetime.now(timezone.utc) and not body.effective_until:
        field = {value: key for key, value in PRICE_FIELDS.items()}[body.price_type]
        setattr(product, field, body.amount); product.currency = body.currency; product.pricing_status = "APPROVED"
    db.flush(); audit(db, user.id, "product.price.created", "product_price_history", row.id,
                      {"product_id": product.id, "price_type": row.price_type})
    db.commit(); return _price_out(row)


def _validate_specs(db: Session, category_id: str, specs: dict, family_id: str | None = None,
                    *, workspace: str | None = None, existing: dict | None = None) -> dict:
    definitions = db.scalars(select(m.ProductSpecDefinition).where(
        m.ProductSpecDefinition.category_id == category_id,
        m.ProductSpecDefinition.status == "ACTIVE",
        *([m.ProductSpecDefinition.workspace == workspace] if workspace else []),
    )).all()
    definitions = [row for row in definitions if row.product_family_id in {None, family_id}]
    if not definitions:
        return specs
    allowed_keys = {row.spec_key for row in definitions}
    # Older catalogue rows can have provenance keys without a configured field.
    # Permit them only when their submitted value exactly matches the stored value.
    legacy = {key: value for key, value in (existing or {}).items() if key not in allowed_keys}
    unknown = sorted(key for key, value in specs.items()
                     if key not in allowed_keys and (key not in legacy or legacy[key] != value))
    if unknown:
        raise HTTPException(422, f"Unknown specification keys: {', '.join(unknown)}")
    normalized = {}
    for definition in definitions:
        if definition.spec_key in specs or definition.required or definition.default_value is not None:
            result = normalize_spec(definition, specs.get(definition.spec_key))
            if result.get("value") is not None:
                normalized[definition.spec_key] = result["value"]
    # An edit need not resend catalogue provenance or other historical keys.
    # Keep their original values while rejecting any new or changed unknown key.
    return {**legacy, **normalized}


def _image_dimensions(data: bytes, mime: str) -> tuple[int | None, int | None]:
    if mime == "image/png" and len(data) >= 24 and data.startswith(b"\x89PNG\r\n\x1a\n"):
        return struct.unpack(">II", data[16:24])
    if mime == "image/gif" and len(data) >= 10 and data[:6] in {b"GIF87a", b"GIF89a"}:
        return struct.unpack("<HH", data[6:10])
    if mime == "image/jpeg" and data.startswith(b"\xff\xd8"):
        pos = 2
        while pos + 9 < len(data):
            if data[pos] != 0xFF:
                pos += 1; continue
            marker = data[pos + 1]
            pos += 2
            if marker in {0xD8, 0xD9}:
                continue
            if pos + 2 > len(data):
                break
            length = int.from_bytes(data[pos:pos + 2], "big")
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF} and pos + 7 < len(data):
                return int.from_bytes(data[pos + 5:pos + 7], "big"), int.from_bytes(data[pos + 3:pos + 5], "big")
            pos += max(length, 2)
    return None, None


@router.post("/product-variants/{variant_id}/media", dependencies=[Depends(require_csrf)])
async def upload_media(
    variant_id: str,
    file: UploadFile = File(...),
    alt_text: str = Form(...),
    caption: str | None = Form(None),
    is_primary: bool = Form(False),
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    admin_required(user)
    product = db.get(m.Product, variant_id)
    if not product:
        raise HTTPException(404, "Product variant not found")
    # Keep the established endpoint while routing all new writes through the
    # provider abstraction and strict content decoder introduced in release 5.
    uploaded = await release5_upload_product_image(variant_id, file, alt_text, caption, db, user)
    if is_primary and not uploaded.get("is_primary"):
        row = db.get(m.ProductMedia, uploaded["id"])
        for sibling in db.scalars(select(m.ProductMedia).where(m.ProductMedia.product_id == variant_id)).all():
            sibling.is_primary = sibling.id == row.id
        db.commit(); uploaded["is_primary"] = True
    return uploaded
    allowed = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
    mime = (file.content_type or "").lower()
    if mime not in allowed:
        raise HTTPException(422, "Upload a JPG, PNG, WebP, or GIF image")
    data = await file.read(settings.media_max_bytes + 1)
    if not data or len(data) > settings.media_max_bytes:
        raise HTTPException(422, f"Image must be between 1 byte and {settings.media_max_bytes} bytes")
    signatures = {
        "image/jpeg": data.startswith(b"\xff\xd8\xff"),
        "image/png": data.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/gif": data[:6] in {b"GIF87a", b"GIF89a"},
        "image/webp": len(data) > 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP",
    }
    if not signatures[mime]:
        raise HTTPException(422, "File content does not match its declared image type")
    root = Path(settings.media_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    key = f"products/{product.family_id or 'legacy'}/{secrets.token_hex(20)}{allowed[mime]}"
    destination = (root / key).resolve()
    if root not in destination.parents:
        raise HTTPException(422, "Invalid media path")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    width, height = _image_dimensions(data, mime)
    existing_count = db.scalar(
        select(func.count(m.ProductMedia.id)).where(m.ProductMedia.product_id == product.id)
    ) or 0
    primary = is_primary or existing_count == 0
    if primary:
        # Primary selection is per exact sellable variant. Sibling variants must not be changed.
        rows = db.scalars(select(m.ProductMedia).where(m.ProductMedia.product_id == product.id)).all()
        for row in rows:
            row.is_primary = False
    media = m.ProductMedia(product_family_id=product.family_id, product_id=product.id,
                           storage_key=key, media_type=mime, alt_text=alt_text.strip(),
                           caption=caption, sort_order=existing_count, is_primary=primary,
                           width=width, height=height)
    db.add(media); db.flush()
    audit(db, user.id, "product_media.uploaded", "product_media", media.id, {"variant_id": product.id})
    db.commit(); return _media_out(media)


@router.get("/product-media/{media_id}/file")
def media_file(media_id: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    media = db.get(m.ProductMedia, media_id)
    if not media or media.archived_at is not None:
        raise HTTPException(404, "Product media not found")
    workspace = media.product.workspace if media.product else (media.family.workspace if media.family else None)
    if not workspace:
        raise HTTPException(404, "Product media is orphaned")
    ensure_workspace(user, workspace)
    root = Path(settings.media_root).expanduser().resolve()
    path = (root / media.storage_key).resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(404, "Product image file not found")
    return FileResponse(path, media_type=media.media_type, filename=path.name,
                        headers={"Cache-Control": "private, max-age=3600"})


@router.patch("/product-media/{media_id}", dependencies=[Depends(require_csrf)])
def update_media(media_id: str, body: MediaPatch, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    media = db.get(m.ProductMedia, media_id)
    if not media:
        raise HTTPException(404, "Product media not found")
    data = body.model_dump(exclude_unset=True)
    if data.get("is_primary"):
        stmt = select(m.ProductMedia)
        if media.product_id:
            stmt = stmt.where(m.ProductMedia.product_id == media.product_id)
        elif media.product_family_id:
            stmt = stmt.where(
                m.ProductMedia.product_family_id == media.product_family_id,
                m.ProductMedia.product_id.is_(None),
            )
        else:
            stmt = stmt.where(m.ProductMedia.id == media.id)
        stmt = stmt.where(m.ProductMedia.archived_at.is_(None))
        for row in db.scalars(stmt).all():
            row.is_primary = row.id == media.id
        data.pop("is_primary", None)
    for field, value in data.items():
        setattr(media, field, value)
    audit(db, user.id, "product_media.updated", "product_media", media.id)
    db.commit(); return _media_out(media)


@router.delete("/product-media/{media_id}", dependencies=[Depends(require_csrf)])
def delete_media(media_id: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    media = db.get(m.ProductMedia, media_id)
    if not media:
        raise HTTPException(404, "Product media not found")
    if media.archived_at is not None:
        return {"ok": True, "already_archived": True}
    was_primary = media.is_primary
    family_id, product_id = media.product_family_id, media.product_id
    media.archived_at = datetime.now(timezone.utc)
    media.upload_status = "ARCHIVED"
    media.is_primary = False
    db.flush()
    if was_primary:
        stmt = select(m.ProductMedia)
        if product_id:
            stmt = stmt.where(m.ProductMedia.product_id == product_id)
        elif family_id:
            stmt = stmt.where(
                m.ProductMedia.product_family_id == family_id,
                m.ProductMedia.product_id.is_(None),
            )
        else:
            stmt = stmt.where(m.ProductMedia.id == "__none__")
        replacement = db.scalar(stmt.where(m.ProductMedia.archived_at.is_(None), m.ProductMedia.upload_status == "READY")
                                .order_by(m.ProductMedia.sort_order, m.ProductMedia.created_at, m.ProductMedia.id).limit(1))
        if replacement:
            replacement.is_primary = True
    audit(db, user.id, "product_media.archived", "product_media", media_id)
    db.commit()
    return {"ok": True, "archived": True}
