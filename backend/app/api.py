from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from io import BytesIO
import re
import secrets
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, Request, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, func, or_, desc, delete
from sqlalchemy.orm import Session, selectinload
from openpyxl import Workbook

from .config import settings
from .db import get_db
from .deps import get_current_user, require_csrf, require_permission, ensure_workspace, has_permission
from .security import verify_password, create_access_token, new_refresh_token, token_hash, new_csrf_token, hash_password
from . import models as m
from .services import (
    stock_status, boq_rows, next_number, audit, create_quotation_from_inquiry, create_quotation_revision,
    recalc_quotation, replace_draft_quotation_items, estimate_inquiry,
    convert_quotation_to_order, update_order_status, create_invoice_from_order,
)
from .pdf import invoice_pdf, quotation_pdf

router = APIRouter(prefix="/api/v1")
ADMIN_ROLES = {"ADMIN", "SUPER_ADMIN"}
_LOGIN_ATTEMPTS: dict[str, list[float]] = defaultdict(list)


# ---------- schemas ----------
class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserIn(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    password: str = Field(min_length=10)
    role: str = "USER"
    workspaces: list[str] = []
    permissions: list[str] = []


class ProductIn(BaseModel):
    workspace: str
    category_id: str
    family_id: str | None = None
    sku: str
    name: str
    internal_name: str | None = None
    variant_name: str | None = None
    model_number: str | None = None
    barcode: str | None = None
    manufacturer: str | None = None
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
    brand: str = "AlphaNumeric"
    on_hand: Decimal = 0
    reorder_level: Decimal = 10
    unit: str = "Nos"
    price: Decimal = 0
    cost: Decimal | None = Field(default=None, ge=0)
    mrp_price: Decimal | None = Field(default=None, ge=0)
    project_price: Decimal | None = Field(default=None, ge=0)
    dealer_price: Decimal | None = Field(default=None, ge=0)
    reseller_price: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    minimum_order_quantity: Decimal = Field(default=1, gt=0)
    pricing_status: str = Field(default="DRAFT", pattern=r"^(DRAFT|PRICE_REQUIRED|PENDING_APPROVAL|APPROVED|REJECTED)$")
    tax_rate: Decimal = 18
    hsn_sac: str | None = None
    specs: dict = {}
    lead_time_days: int | None = Field(default=None, ge=0)
    warranty: str | None = None


class CustomerIn(BaseModel):
    company_name: str = Field(min_length=1)
    contact_person: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    gstin: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None


class PartnerIn(BaseModel):
    business_name: str = Field(min_length=1)
    mobile: str = Field(min_length=5)
    email: EmailStr
    address: str = Field(min_length=1)


class RequirementIn(BaseModel):
    product_id: str
    quantity: Decimal = Field(gt=0)
    notes: str | None = None


class RoomIn(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1)
    room_type: str | None = None
    area: Decimal | None = Field(default=None, ge=0)
    occupancy: int | None = Field(default=None, ge=0)
    notes: str | None = None
    requirements: list[RequirementIn] = []


class FloorIn(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1)
    rooms: list[RoomIn] = []


class InquiryCreate(BaseModel):
    workspace: str = "LIGHTING"
    customer_id: str | None = None
    customer: CustomerIn | None = None
    project_id: str | None = None
    building_id: str | None = None
    project_name: str = Field(min_length=1)
    address: str | None = None
    city: str | None = None
    state: str | None = None
    partner: PartnerIn | None = None
    building_name: str = "Tower A"
    floors_data: list[FloorIn] = []
    wizard_step: int = Field(default=1, ge=1, le=5)
    notes: str | None = None
    # Legacy request shape kept for existing clients.
    floors: int | None = Field(default=None, ge=1)
    room_names: list[str] | None = None
    requirements: list[dict] | None = None


class InquiryUpdate(BaseModel):
    customer_id: str | None = None
    customer: CustomerIn | None = None
    building_id: str | None = None
    project_name: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    partner: PartnerIn | None = None
    remove_partner: bool = False
    building_name: str | None = None
    floors_data: list[FloorIn] | None = None
    wizard_step: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None


class StatusIn(BaseModel):
    status: str


class StockIn(BaseModel):
    quantity: Decimal
    reason: str = "Manual adjustment"


class DiscountIn(BaseModel):
    discount_percent: Decimal = 0


class ProjectUserIn(BaseModel):
    existing_user_id: str | None = None
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    role: str = "PROJECT_USER"
    status: str = "ACTIVE"
    permissions: list[str] = []
    building_id: str | None = None


class ProjectUserUpdate(BaseModel):
    role: str | None = None
    status: str | None = None
    name: str | None = None
    phone: str | None = None
    permissions: list[str] | None = None
    building_id: str | None = None


class ProductRequestItemIn(BaseModel):
    product_id: str
    quantity: Decimal = Field(gt=0)
    room_id: str
    notes: str | None = None


class ProductRequestIn(BaseModel):
    project_id: str
    workspace: str = "LIGHTING"
    items: list[ProductRequestItemIn] = Field(min_length=1)
    notes: str | None = None


def f(v):
    return float(v or 0)


def document_filename(prefix: str, number: str, subject: str) -> str:
    safe_number = re.sub(r"[^A-Za-z0-9._-]+", "-", number).strip("-") or prefix
    safe_subject = re.sub(r"[^A-Za-z0-9._-]+", "-", subject).strip("-")[:80] or "Document"
    return f"{prefix}_{safe_number}_{safe_subject}.pdf"


def pdf_disposition(filename: str, download: bool) -> str:
    return f'{"attachment" if download else "inline"}; filename="{filename}"'


def amount_in_words(value: Decimal) -> str:
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
            "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
            "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def under_thousand(number: int) -> str:
        parts: list[str] = []
        if number >= 100:
            parts.extend([ones[number // 100], "Hundred"]); number %= 100
        if number >= 20:
            parts.append(tens[number // 10]); number %= 10
        if number:
            parts.append(ones[number])
        return " ".join(parts)

    rupees = int(value)
    paise = int((value - Decimal(rupees)).quantize(Decimal("0.01")) * 100)
    if rupees == 0:
        words = "Zero"
    else:
        parts: list[str] = []
        for divisor, label in [(10_000_000, "Crore"), (100_000, "Lakh"), (1_000, "Thousand")]:
            if rupees >= divisor:
                parts.extend([under_thousand(rupees // divisor), label]); rupees %= divisor
        if rupees:
            parts.append(under_thousand(rupees))
        words = " ".join(parts)
    suffix = f" and {under_thousand(paise)} Paise" if paise else ""
    return f"Indian Rupees {words}{suffix} Only"


def iso(v):
    return v.isoformat() if v else None


def admin_required(user: m.User):
    if user.role not in {"ADMIN", "SUPER_ADMIN"}:
        raise HTTPException(403, "Admin access required")


def accessible_project_ids(db: Session, user: m.User) -> set[str]:
    if user.role in {"ADMIN", "SUPER_ADMIN"}:
        return set(db.scalars(select(m.Project.id)).all())
    return set(db.scalars(select(m.ProjectUser.project_id).where(
        m.ProjectUser.user_id == user.id, m.ProjectUser.status == "ACTIVE"
    )).all())


def ensure_project_access(db: Session, user: m.User, project_id: str):
    if user.role in ADMIN_ROLES:
        return
    ok = db.scalar(select(m.ProjectUser.id).where(
        m.ProjectUser.project_id == project_id,
        m.ProjectUser.user_id == user.id,
        m.ProjectUser.status == "ACTIVE",
    ).limit(1))
    if not ok:
        raise HTTPException(403, "You do not have access to this project")


def ensure_building_access(db: Session, user: m.User, project_id: str, building_id: str):
    """Enforce an optional building boundary on a project membership."""
    if user.role in ADMIN_ROLES:
        return
    membership = db.scalar(select(m.ProjectUser).where(
        m.ProjectUser.project_id == project_id,
        m.ProjectUser.user_id == user.id,
        m.ProjectUser.status == "ACTIVE",
    ))
    if not membership or (membership.building_id and membership.building_id != building_id):
        raise HTTPException(403, "You do not have access to this building")


def project_permissions(db: Session, user: m.User, project_id: str) -> set[str]:
    if user.role in ADMIN_ROLES:
        return {"*"}
    membership = db.scalar(select(m.ProjectUser).where(
        m.ProjectUser.project_id == project_id,
        m.ProjectUser.user_id == user.id,
        m.ProjectUser.status == "ACTIVE",
    ))
    if not membership:
        return set()
    return {*(user.permissions or []), *(membership.permissions or [])}


def has_project_permission(db: Session, user: m.User, project_id: str, permission: str) -> bool:
    permissions = project_permissions(db, user, project_id)
    return "*" in permissions or permission in permissions


def require_project_permission(db: Session, user: m.User, project_id: str, permission: str) -> None:
    ensure_project_access(db, user, project_id)
    if not has_project_permission(db, user, project_id, permission):
        raise HTTPException(403, "Your project role does not allow this operation")


def can_view_commercial(db: Session, user: m.User, project_id: str) -> bool:
    return user.role in ADMIN_ROLES or has_project_permission(db, user, project_id, "commercial.documents.view")


def can_view_prices(db: Session, user: m.User, project_id: str) -> bool:
    return user.role in ADMIN_ROLES or has_project_permission(db, user, project_id, "commercial.prices.view")


def user_out(u: m.User):
    return {"id": u.id, "name": u.name, "email": u.email, "phone": u.phone, "role": u.role,
            "status": u.status, "partner_id": u.partner_id, "workspaces": u.workspaces or [], "permissions": u.permissions or [],
            "must_change_password": u.must_change_password, "last_login": iso(u.last_login)}


def customer_out(c: m.Customer):
    return {"id": c.id, "company_name": c.company_name, "contact_person": c.contact_person,
            "email": c.email, "phone": c.phone, "gstin": c.gstin, "address": c.address,
            "city": c.city, "state": c.state, "status": c.status, "created_at": iso(c.created_at),
            "updated_at": iso(c.updated_at)}


def partner_out(p: m.Partner | None):
    if not p:
        return None
    return {"id": p.id, "business_name": p.business_name, "mobile": p.mobile,
            "email": p.email, "address": p.address, "created_at": iso(p.created_at)}


def product_out(p: m.Product, include_price: bool = True):
    # Exact sellable-variant media is authoritative.  ProductMedia rows that
    # belong to a variant also appear through ProductFamily.media because they
    # retain the family FK for catalogue grouping, so blindly concatenating the
    # two relationships duplicates those rows and can incorrectly put a
    # family-level primary image ahead of the variant primary image.
    exact_media = [item for item in (p.media or []) if item.archived_at is None]
    family_fallback = [
        item for item in (p.family.media if p.family else [])
        if item.product_id is None and item.archived_at is None
    ]
    source_media = exact_media if exact_media else family_fallback
    media_rows = sorted(
        source_media,
        key=lambda item: (not item.is_primary, item.sort_order, item.created_at, item.id),
    )
    media = [{"id": item.id, "url": f"/api/v1/product-media/{item.id}/secure-file" if item.provider_file_id else f"/api/v1/product-media/{item.id}/file",
              "media_type": item.media_type, "alt_text": item.alt_text,
              "caption": item.caption, "sort_order": item.sort_order,
              "is_primary": item.is_primary, "width": item.width, "height": item.height}
             for item in media_rows]
    legacy_images = [{"id": f"legacy-{idx}", "url": url, "media_type": "image",
                      "alt_text": p.name, "caption": None, "sort_order": idx,
                      "is_primary": idx == 0, "width": None, "height": None}
                     for idx, url in enumerate(p.images or []) if isinstance(url, str)]
    if not media:
        media = legacy_images
    out = {"id": p.id, "workspace": p.workspace, "category_id": p.category_id,
           "category": p.category.name if p.category else "", "sku": p.sku, "name": p.name,
           "description": p.description, "full_description": p.full_description,
           "brand": p.brand, "manufacturer": p.manufacturer or p.brand,
           "barcode": p.barcode, "search_tags": p.search_tags or [], "status": p.status,
           "on_hand": f(p.on_hand), "reserved": f(p.reserved), "available": f(p.available),
           "reorder_level": f(p.reorder_level), "unit": p.unit, "tax_rate": f(p.tax_rate),
           "hsn_sac": p.hsn_sac, "specs": p.specs or {}, "images": [x["url"] for x in media],
           "media": media, "primary_image_url": media[0]["url"] if media else None,
           "family_id": p.family_id, "family_name": p.family.name if p.family else p.name,
           "variant_name": p.variant_name or p.name, "model_number": p.model_number,
           "highlights": p.highlights or [],
           "features": p.features or ((p.family.features if p.family else []) or []),
           "applications": p.applications or ((p.family.applications if p.family else []) or []),
           "installation_summary": p.installation_summary, "care_guide": p.care_guide,
           "warranty_summary": p.warranty_summary,
           "suitability_guidance": p.family.suitability_guidance if p.family else None,
           "lead_time_days": p.lead_time_days, "warranty": p.warranty,
           "currency": p.currency, "minimum_order_quantity": f(p.minimum_order_quantity),
           "pricing_status": p.pricing_status,
           "stock_status": stock_status(p)}
    if include_price:
        out["price"] = f(p.price)
        out["cost"] = f(p.cost) if p.cost is not None else None
        out.update({"internal_name": p.internal_name, "internal_notes": p.internal_notes,
                    "mrp_price": f(p.mrp_price) if p.mrp_price is not None else None,
                    "project_price": f(p.project_price) if p.project_price is not None else None,
                    "dealer_price": f(p.dealer_price) if p.dealer_price is not None else None,
                    "reseller_price": f(p.reseller_price) if p.reseller_price is not None else None})
    else:
        out.pop("on_hand", None); out.pop("reserved", None); out.pop("reorder_level", None)
    return out


def project_basic(p: m.Project):
    return {"id": p.id, "customer_id": p.customer_id, "name": p.name, "city": p.city,
            "state": p.state, "address": p.address, "status": p.status,
            "workspaces": p.workspace_scope or [], "created_at": iso(p.created_at),
            "updated_at": iso(p.updated_at),
            "owner": {"id": p.owner.id, "name": p.owner.name} if p.owner else None}


def inquiry_out(i: m.Inquiry):
    return {"id": i.id, "number": i.number, "customer": customer_out(i.customer),
            "project": project_basic(i.project), "workspace": i.workspace,
            "workspace_scope": i.workspace_scope or [i.workspace],
            "owner": {"id": i.owner.id, "name": i.owner.name}, "status": i.status,
            "source": i.source, "wizard_step": i.wizard_step, "notes": i.notes,
            "building_id": i.building_id, "building_name": i.building.name if i.building else None,
            "is_project_wide": i.is_project_wide,
            "estimated_value": f(i.estimated_value), "submitted_at": iso(i.submitted_at),
            "created_at": iso(i.created_at), "updated_at": iso(i.updated_at)}


def quote_out(q: m.Quotation, db: Session, with_items=True, include_price: bool = True):
    d = {"id": q.id, "number": q.number, "inquiry_id": q.inquiry_id,
         "customer": customer_out(q.customer), "project": project_basic(q.project),
         "workspace": q.workspace, "status": q.status, "quotation_date": iso(q.quotation_date),
         "building_id": q.building_id, "valid_until": iso(q.valid_until),
         "payment_terms": q.payment_terms, "delivery_terms": q.delivery_terms,
         "warranty_terms": q.warranty_terms, "notes": q.notes, "revision": q.revision,
         "supersedes_id": q.supersedes_id, "sent_at": iso(q.sent_at), "accepted_at": iso(q.accepted_at)}
    if include_price:
        d.update({"discount_percent": f(q.discount_percent), "subtotal": f(q.subtotal),
                  "discount_amount": f(q.discount_amount), "tax_total": f(q.tax_total),
                  "grand_total": f(q.grand_total)})
    if with_items:
        d["items"] = []
        for x in db.scalars(select(m.QuotationItem).where(m.QuotationItem.quotation_id == q.id)).all():
            item = {"id": x.id, "product_id": x.product_id, "description": x.description,
                    "sku": x.sku, "qty": f(x.qty)}
            if include_price:
                item.update({"rate": f(x.rate), "tax_rate": f(x.tax_rate), "amount": f(x.amount)})
            d["items"].append(item)
    return d


def order_out(o: m.Order, db: Session, with_items=True, include_price: bool = True):
    d = {"id": o.id, "number": o.number, "quotation_id": o.quotation_id,
         "customer": customer_out(o.customer), "project": project_basic(o.project),
         "workspace": o.workspace, "status": o.status, "building_id": o.building_id,
         "order_date": iso(o.order_date), "delivery_date": iso(o.delivery_date),
         "delivery_address": o.delivery_address, "dispatch_reference": o.dispatch_reference,
         "dispatched_at": iso(o.dispatched_at)}
    if include_price:
        d.update({"subtotal": f(o.subtotal), "tax_total": f(o.tax_total), "grand_total": f(o.grand_total)})
    if with_items:
        d["items"] = []
        for x in db.scalars(select(m.OrderItem).where(m.OrderItem.order_id == o.id)).all():
            item = {"id": x.id, "product_id": x.product_id, "description": x.description,
                    "sku": x.sku, "qty": f(x.qty)}
            if include_price:
                item.update({"rate": f(x.rate), "tax_rate": f(x.tax_rate), "amount": f(x.amount)})
            d["items"].append(item)
    return d


def invoice_out(inv: m.Invoice, db: Session, include_price: bool = True):
    project = inv.project or (inv.order.project if inv.order else None)
    payments = db.scalars(select(m.InvoicePayment).where(m.InvoicePayment.invoice_id == inv.id).order_by(m.InvoicePayment.paid_at)).all()
    paid = sum((Decimal(row.amount) for row in payments), Decimal("0"))
    credits = db.scalar(select(func.coalesce(func.sum(m.FinancialDocument.grand_total), 0)).where(
        m.FinancialDocument.invoice_id == inv.id, m.FinancialDocument.document_type == "CREDIT_NOTE",
        m.FinancialDocument.status == "ISSUED")) or 0
    debits = db.scalar(select(func.coalesce(func.sum(m.FinancialDocument.grand_total), 0)).where(
        m.FinancialDocument.invoice_id == inv.id, m.FinancialDocument.document_type == "DEBIT_NOTE",
        m.FinancialDocument.status == "ISSUED")) or 0
    adjusted_total = Decimal(inv.grand_total) - Decimal(credits) + Decimal(debits)
    result = {"id": inv.id, "number": inv.number, "order_id": inv.order_id,
            "order_number": inv.order.number if inv.order else None,
            "customer": customer_out(inv.customer), "project": project_basic(project) if project else None,
            "building_id": inv.building_id, "workspace": inv.workspace, "status": inv.status,
            "invoice_date": iso(inv.invoice_date), "due_date": iso(inv.due_date),
            "place_of_supply": inv.place_of_supply,
            "company": {"name": settings.company_name, "gstin": settings.company_gstin,
                        "pan": settings.company_pan, "address": settings.company_address,
                        "phone": settings.company_phone, "email": settings.company_email,
                        "logo_path": settings.company_logo_path},
            "bank": {"name": settings.bank_name, "account_name": settings.bank_account_name,
                     "account_number": settings.bank_account_number, "ifsc": settings.bank_ifsc},
            "payments": [{"id": row.id, "amount": f(row.amount), "method": row.method,
                          "reference": row.reference, "paid_at": iso(row.paid_at), "notes": row.notes}
                         for row in payments]}
    result["items"] = []
    for x in db.scalars(select(m.InvoiceItem).where(m.InvoiceItem.invoice_id == inv.id)).all():
        item = {"description": x.description, "sku": x.sku, "hsn_sac": x.hsn_sac,
                "qty": f(x.qty), "unit": x.unit}
        if include_price:
            item.update({"rate": f(x.rate), "tax_rate": f(x.tax_rate), "amount": f(x.amount)})
        result["items"].append(item)
    if include_price:
        result.update({"subtotal": f(inv.subtotal), "cgst": f(inv.cgst), "sgst": f(inv.sgst),
                       "igst": f(inv.igst), "round_off": f(inv.round_off), "grand_total": f(inv.grand_total),
                       "credit_note_total": f(credits), "debit_note_total": f(debits),
                       "adjusted_total": f(adjusted_total), "paid_total": f(paid), "balance_due": f(adjusted_total - paid),
                       "amount_in_words": amount_in_words(Decimal(inv.grand_total))})
    return result


def project_user_out(pu: m.ProjectUser):
    return {"id": pu.id, "project_id": pu.project_id, "user_id": pu.user_id,
            "building_id": pu.building_id, "role": pu.role, "permissions": pu.permissions or [], "status": pu.status, "created_at": iso(pu.created_at),
            "user": user_out(pu.user)}


def project_structure(db: Session, project_id: str, inquiry_id: str | None = None, include_price: bool = True,
                      workspace: str | None = None, building_id: str | None = None):
    buildings = db.scalars(select(m.Building).where(m.Building.project_id == project_id)
                           .order_by(m.Building.sort_order, m.Building.name)).all()
    if building_id:
        buildings = [building for building in buildings if building.id == building_id]
    building_ids = [row.id for row in buildings]
    floors = db.scalars(select(m.Floor).where(m.Floor.building_id.in_(building_ids))
                        .order_by(m.Floor.sort_order, m.Floor.name)).all() if building_ids else []
    floor_ids = [row.id for row in floors]
    rooms = db.scalars(select(m.Room).where(m.Room.floor_id.in_(floor_ids))
                       .order_by(m.Room.sort_order, m.Room.name)).all() if floor_ids else []
    room_ids = [row.id for row in rooms]

    products_by_room: dict[str, list[dict]] = defaultdict(list)
    product_options = (
        selectinload(m.RoomRequirement.product).selectinload(m.Product.category),
        selectinload(m.RoomRequirement.product).selectinload(m.Product.family).selectinload(m.ProductFamily.media),
        selectinload(m.RoomRequirement.product).selectinload(m.Product.media),
    )
    if inquiry_id and room_ids:
        requirements = db.scalars(select(m.RoomRequirement).options(*product_options).where(
            m.RoomRequirement.inquiry_id == inquiry_id, m.RoomRequirement.room_id.in_(room_ids)
        )).unique().all()
        for row in requirements:
            products_by_room[row.room_id].append({"id": row.id, "product": product_out(row.product, include_price),
                                                  "quantity": f(row.quantity), "unit": row.unit,
                                                  "notes": row.notes, "inquiry_id": row.inquiry_id,
                                                  "approval_status": "ADDED", "source": "INQUIRY"})
    elif room_ids:
        selection_stmt = select(m.RoomProduct).join(m.Product).options(
            selectinload(m.RoomProduct.product).selectinload(m.Product.category),
            selectinload(m.RoomProduct.product).selectinload(m.Product.family).selectinload(m.ProductFamily.media),
            selectinload(m.RoomProduct.product).selectinload(m.Product.media),
        ).where(m.RoomProduct.room_id.in_(room_ids))
        if workspace: selection_stmt = selection_stmt.where(m.Product.workspace == workspace)
        selections = db.scalars(selection_stmt.order_by(m.RoomProduct.created_at)).unique().all()
        selected_rooms = {row.room_id for row in selections}
        for row in selections:
            products_by_room[row.room_id].append({"id": row.id, "product": product_out(row.product, include_price),
                                                  "quantity": f(row.quantity), "unit": row.unit,
                                                  "notes": row.notes, "inquiry_id": row.linked_inquiry_id,
                                                  "approval_status": row.approval_status, "source": row.source})
        legacy_rooms = [room_id for room_id in room_ids if room_id not in selected_rooms]
        if legacy_rooms:
            legacy_stmt = select(m.RoomRequirement).join(m.Inquiry).join(m.Product).options(*product_options).where(
                m.RoomRequirement.room_id.in_(legacy_rooms), m.Inquiry.project_id == project_id
            )
            if workspace: legacy_stmt = legacy_stmt.where(m.Inquiry.workspace == workspace, m.Product.workspace == workspace)
            legacy = db.scalars(legacy_stmt.order_by(desc(m.Inquiry.updated_at), desc(m.RoomRequirement.id))).unique().all()
            seen: set[tuple[str, str]] = set()
            for row in legacy:
                key = (row.room_id, row.product_id)
                if key in seen:
                    continue
                seen.add(key)
                products_by_room[row.room_id].append({"id": row.id, "product": product_out(row.product, include_price),
                                                      "quantity": f(row.quantity), "unit": row.unit,
                                                      "notes": row.notes, "inquiry_id": row.inquiry_id,
                                                      "approval_status": "ADDED", "source": "INQUIRY"})

    boards = db.scalars(select(m.MainBoard).where(m.MainBoard.floor_id.in_(floor_ids))).all() if floor_ids else []
    floor_board_count: dict[str, int] = defaultdict(int)
    room_board_count: dict[str, int] = defaultdict(int)
    for board in boards:
        floor_board_count[board.floor_id] += board.quantity
        if board.room_id:
            room_board_count[board.room_id] += board.quantity
    rooms_by_floor: dict[str, list[m.Room]] = defaultdict(list)
    for room in rooms:
        rooms_by_floor[room.floor_id].append(room)
    floors_by_building: dict[str, list[m.Floor]] = defaultdict(list)
    for floor in floors:
        floors_by_building[floor.building_id].append(floor)

    structures = []
    for building in buildings:
        floors_out = []
        for floor in floors_by_building[building.id]:
            rooms_out = []
            for room in rooms_by_floor[floor.id]:
                products = products_by_room[room.id]
                rooms_out.append({"id": room.id, "name": room.name, "room_type": room.room_type,
                                  "area": f(room.area) if room.area is not None else None,
                                  "occupancy": room.occupancy, "notes": room.notes,
                                  "requirements": products, "product_quantity": sum(x["quantity"] for x in products),
                                  "unique_product_count": len(products),
                                  "main_board_count": room_board_count[room.id],
                                  "configuration_status": "CONFIGURED" if products else "NOT_CONFIGURED"})
            floors_out.append({"id": floor.id, "name": floor.name, "sort_order": floor.sort_order,
                               "rooms": rooms_out, "room_count": len(rooms_out),
                               "main_board_count": floor_board_count[floor.id],
                               "unique_product_count": len({item["product"]["id"] for room in rooms_out for item in room["requirements"]}),
                               "product_quantity": sum(room["product_quantity"] for room in rooms_out),
                               "configuration_status": "CONFIGURED" if rooms_out and all(room["requirements"] for room in rooms_out) else "IN_PROGRESS"})
        structures.append({"id": building.id, "project_id": building.project_id, "name": building.name,
                           "code": building.code, "building_type": building.building_type,
                           "address": building.address, "status": building.status,
                           "floors": floors_out, "floor_count": len(floors_out),
                           "room_count": sum(len(floor["rooms"]) for floor in floors_out),
                           "main_board_count": sum(floor["main_board_count"] for floor in floors_out),
                           "unique_product_count": len({item["product"]["id"] for floor in floors_out for room in floor["rooms"] for item in room["requirements"]}),
                           "product_quantity": sum(floor["product_quantity"] for floor in floors_out)})
    return structures


def activity_for(db: Session, entity_type: str, entity_id: str):
    rows = db.scalars(select(m.AuditLog).where(
        m.AuditLog.entity_type == entity_type, m.AuditLog.entity_id == entity_id
    ).order_by(desc(m.AuditLog.created_at))).all()
    actor_ids = {r.actor_id for r in rows if r.actor_id}
    actors = {u.id: u.name for u in db.scalars(select(m.User).where(m.User.id.in_(actor_ids))).all()} if actor_ids else {}
    return [{"id": r.id, "actor": actors.get(r.actor_id, "System"), "action": r.action,
             "metadata": r.metadata_json or {}, "created_at": iso(r.created_at)} for r in rows]


def set_auth_cookies(response: Response, user: m.User, refresh: str, csrf: str):
    response.set_cookie("access_token", create_access_token(user.id), httponly=True,
                        secure=settings.cookie_secure, samesite="lax",
                        max_age=settings.access_token_minutes*60, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=settings.cookie_secure,
                        samesite="lax", max_age=settings.refresh_token_days*86400, path="/api/v1/auth")
    response.set_cookie("csrf_token", csrf, httponly=False, secure=settings.cookie_secure,
                        samesite="lax", max_age=settings.refresh_token_days*86400, path="/")


# ---------- auth ----------
@router.post("/auth/login")
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    key = body.email.strip().lower(); now = time.monotonic()
    _LOGIN_ATTEMPTS[key] = [stamp for stamp in _LOGIN_ATTEMPTS[key] if now - stamp < 300]
    if len(_LOGIN_ATTEMPTS[key]) >= 10:
        raise HTTPException(429, "Too many login attempts; try again later")
    u = db.scalar(select(m.User).where(func.lower(m.User.email) == body.email.lower()))
    if not u or u.status != "ACTIVE" or not verify_password(body.password, u.password_hash):
        _LOGIN_ATTEMPTS[key].append(now)
        raise HTTPException(401, "Invalid email or password")
    _LOGIN_ATTEMPTS.pop(key, None)
    refresh = new_refresh_token(); csrf = new_csrf_token()
    db.add(m.AuthSession(user_id=u.id, refresh_hash=token_hash(refresh),
                         expires_at=datetime.now(timezone.utc)+timedelta(days=settings.refresh_token_days)))
    u.last_login = datetime.now(timezone.utc)
    audit(db, u.id, "auth.login", "user", u.id)
    db.commit(); set_auth_cookies(response, u, refresh, csrf)
    return {"user": user_out(u)}


@router.post("/auth/refresh", dependencies=[Depends(require_csrf)])
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(401, "Refresh required")
    sess = db.scalar(select(m.AuthSession).where(m.AuthSession.refresh_hash == token_hash(token)))
    if not sess or sess.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(401, "Refresh expired")
    user = db.get(m.User, sess.user_id)
    if not user or user.status != "ACTIVE":
        raise HTTPException(401, "User unavailable")
    newr = new_refresh_token(); sess.refresh_hash = token_hash(newr)
    sess.expires_at = datetime.now(timezone.utc)+timedelta(days=settings.refresh_token_days)
    csrf = new_csrf_token(); db.commit(); set_auth_cookies(response, user, newr, csrf)
    return {"user": user_out(user)}


@router.post("/auth/logout", dependencies=[Depends(require_csrf)])
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if token:
        sess = db.scalar(select(m.AuthSession).where(m.AuthSession.refresh_hash == token_hash(token)))
        if sess:
            db.delete(sess); db.commit()
    for c in ["access_token", "refresh_token", "csrf_token"]:
        response.delete_cookie(c, path="/api/v1/auth" if c == "refresh_token" else "/")
    return {"ok": True}


@router.get("/auth/me")
def me(user: m.User = Depends(get_current_user)):
    return {"user": user_out(user)}


# ---------- dashboard ----------
def trend_data(db: Session, user: m.User, workspace: str, range_key: str):
    now = datetime.now(timezone.utc)
    if range_key == "3m":
        start = now - timedelta(days=91); bucket = "week"; count = 13
    elif range_key == "6m":
        start = now - timedelta(days=183); bucket = "month"; count = 6
    else:
        range_key = "30d"; start = now - timedelta(days=29); bucket = "day"; count = 30
    allowed = accessible_project_ids(db, user)
    iq = select(m.Inquiry).where(m.Inquiry.created_at >= start, m.Inquiry.workspace == workspace)
    qq = select(m.Quotation).where(m.Quotation.quotation_date >= start.date(), m.Quotation.workspace == workspace)
    oq = select(m.Order).where(m.Order.order_date >= start.date(), m.Order.workspace == workspace)
    if user.role not in ADMIN_ROLES:
        iq = iq.where(m.Inquiry.project_id.in_(allowed))
        qq = qq.where(m.Quotation.project_id.in_(allowed))
        oq = oq.where(m.Order.project_id.in_(allowed))
    inquiries = db.scalars(iq).all(); quotes = db.scalars(qq).all(); orders = db.scalars(oq).all()

    rows = []
    if bucket == "day":
        for k in range(count):
            d = (start + timedelta(days=k)).date()
            rows.append({"key": d, "label": d.strftime("%b %d")})
        key_for = lambda d: d.date() if isinstance(d, datetime) else d
    elif bucket == "week":
        for k in range(count):
            s = (start + timedelta(days=k*7)).date()
            rows.append({"key": k, "start": s, "end": s+timedelta(days=6), "label": f"{s.strftime('%b %d')}"})
        def key_for(d):
            day = d.date() if isinstance(d, datetime) else d
            return max(0, min(count-1, (day-start.date()).days // 7))
    else:
        today = now.date()
        months = []
        y, mo = today.year, today.month
        for offset in reversed(range(count)):
            total = y*12 + (mo-1) - offset
            yy, mm = divmod(total, 12); mm += 1
            months.append((yy, mm))
        rows = [{"key": x, "label": date(x[0], x[1], 1).strftime("%b %Y")} for x in months]
        key_for = lambda d: ((d.date() if isinstance(d, datetime) else d).year, (d.date() if isinstance(d, datetime) else d).month)

    indexed = {r["key"]: {"label": r["label"], "inquiries": 0, "quotations": 0, "orders": 0} for r in rows}
    for obj, field, name in [(inquiries, "created_at", "inquiries"), (quotes, "quotation_date", "quotations"), (orders, "order_date", "orders")]:
        for x in obj:
            key = key_for(getattr(x, field))
            if key in indexed:
                indexed[key][name] += 1
    return range_key, [indexed[r["key"]] for r in rows]


@router.get("/dashboard")
def dashboard(workspace: str = Query("LIGHTING"), range: str = Query("30d"),
              db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    workspace = workspace.upper(); ensure_workspace(user, workspace)
    allowed = accessible_project_ids(db, user)
    iq = select(m.Inquiry).where(m.Inquiry.workspace == workspace)
    oq = select(m.Order).where(m.Order.workspace == workspace)
    qq = select(m.Quotation).where(m.Quotation.workspace == workspace)
    if user.role not in ADMIN_ROLES:
        iq = iq.where(m.Inquiry.project_id.in_(allowed)); oq = oq.where(m.Order.project_id.in_(allowed)); qq = qq.where(m.Quotation.project_id.in_(allowed))
    inquiries = db.scalars(iq).all(); orders = db.scalars(oq).all(); quotes = db.scalars(qq).all()
    products = db.scalars(select(m.Product).where(m.Product.workspace == workspace)).all()
    alerts = [product_out(p) for p in products if stock_status(p) != "IN_STOCK"][:5] if user.role in ADMIN_ROLES else []
    customers = []
    if user.role in ADMIN_ROLES:
        customers = db.scalars(select(m.Customer).order_by(desc(m.Customer.created_at)).limit(5)).all()
    counts = {s: sum(1 for x in inquiries if x.status == s) for s in ["DRAFT", "IN_PROCESS", "QUOTED", "COMPLETED"]}
    range_key, trend = trend_data(db, user, workspace, range)
    return {"workspace": workspace, "range": range_key, "role": user.role,
            "kpis": {"orders": len(orders), "pending_orders": sum(1 for x in orders if x.status not in ["DELIVERED", "CANCELLED"]),
                     "delivered": sum(1 for x in orders if x.status == "DELIVERED"),
                     "open_inquiries": sum(1 for x in inquiries if x.status not in ["COMPLETED", "CANCELLED"]),
                     "active_quotations": sum(1 for x in quotes if x.status in ["DRAFT", "SENT"])},
            "inquiries": counts, "alerts": alerts,
            "recent_customers": [customer_out(c) for c in customers], "trend": trend}


# ---------- products ----------
@router.get("/categories")
def categories(workspace: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    workspace = workspace.upper(); ensure_workspace(user, workspace)
    cats = db.scalars(select(m.Category).where(m.Category.workspace == workspace).order_by(m.Category.name)).all()
    return [{"id": c.id, "name": c.name, "workspace": c.workspace,
             "count": db.scalar(select(func.count()).select_from(m.Product).where(m.Product.category_id == c.id))} for c in cats]


@router.get("/products")
def products(workspace: str, category_id: str | None = None, q: str | None = None,
             db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    workspace = workspace.upper(); ensure_workspace(user, workspace)
    stmt = select(m.Product).where(m.Product.workspace == workspace, m.Product.status == "ACTIVE")
    if category_id: stmt = stmt.where(m.Product.category_id == category_id)
    if q: stmt = stmt.where(or_(m.Product.name.ilike(f"%{q}%"), m.Product.sku.ilike(f"%{q}%")))
    return [product_out(p, include_price=user.role in ADMIN_ROLES) for p in db.scalars(stmt.order_by(m.Product.name)).all()]


@router.get("/products/{pid}")
def product_detail(pid: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    p = db.get(m.Product, pid)
    if not p: raise HTTPException(404, "Product not found")
    ensure_workspace(user, p.workspace)
    out = product_out(p, include_price=user.role in ADMIN_ROLES)
    if user.role in ADMIN_ROLES:
        out["movements"] = [{"id": x.id, "type": x.movement_type, "quantity": f(x.quantity),
                            "reason": x.reason, "created_at": iso(x.created_at)}
                           for x in db.scalars(select(m.InventoryMovement).where(
                               m.InventoryMovement.product_id == p.id).order_by(desc(m.InventoryMovement.created_at)).limit(10)).all()]
    return out


@router.post("/products", dependencies=[Depends(require_csrf)])
def add_product(body: ProductIn, db: Session = Depends(get_db), user: m.User = Depends(require_permission("products.create"))):
    admin_required(user); workspace = body.workspace.upper(); ensure_workspace(user, workspace)
    category = db.get(m.Category, body.category_id)
    if not category or category.workspace != workspace:
        raise HTTPException(422, "Category does not belong to the selected workspace")
    if db.scalar(select(m.Product.id).where(func.lower(m.Product.sku) == body.sku.lower())):
        raise HTTPException(409, "SKU already exists")
    family = db.get(m.ProductFamily, body.family_id) if body.family_id else None
    if body.family_id and (not family or family.workspace != workspace):
        raise HTTPException(422, "Product family does not belong to the selected workspace")
    if not family:
        base = "-".join(part for part in "".join(ch.lower() if ch.isalnum() else " " for ch in body.name).split()) or "product"
        slug = base[:170]; suffix = 2
        while db.scalar(select(m.ProductFamily.id).where(m.ProductFamily.workspace == workspace, m.ProductFamily.slug == slug)):
            slug = f"{base[:160]}-{suffix}"; suffix += 1
        family = m.ProductFamily(workspace=workspace, category_id=body.category_id, name=body.name,
                                 slug=slug, brand=body.brand, short_description=body.description,
                                 full_description=body.description, features=[], applications=[])
        db.add(family); db.flush()
    data = body.model_dump(exclude={"workspace", "family_id", "variant_name"})
    for field in ("description", "full_description", "installation_summary", "care_guide", "warranty_summary", "internal_notes"):
        value = data.get(field)
        if value and re.search(r"<\s*(script|iframe|object|embed)|on\w+\s*=|javascript:", value, re.I):
            raise HTTPException(422, "Unsafe product content is not allowed")
        if isinstance(value, str): data[field] = value.strip()
    p = m.Product(**data, workspace=workspace, family_id=family.id,
                  variant_name=body.variant_name or body.name, images=[])
    db.add(p); db.flush()
    now = datetime.now(timezone.utc)
    for field, price_type in {"cost": "COST", "price": "BASE", "mrp_price": "MRP", "project_price": "PROJECT", "dealer_price": "DEALER", "reseller_price": "RESELLER"}.items():
        amount = getattr(body, field)
        if amount is not None:
            db.add(m.ProductPriceHistory(product_id=p.id, price_type=price_type, amount=amount,
                currency=body.currency, effective_from=now,
                status="APPROVED" if body.pricing_status == "APPROVED" else "DRAFT",
                approved_by=user.id if body.pricing_status == "APPROVED" else None, created_by=user.id))
    db.add(m.InventoryMovement(product_id=p.id, movement_type="OPENING", quantity=p.on_hand,
                               reason="Opening stock", created_by=user.id))
    audit(db, user.id, "product.created", "product", p.id); db.commit(); db.refresh(p)
    return product_out(p)


@router.post("/products/{pid}/stock", dependencies=[Depends(require_csrf)])
def adjust_stock(pid: str, body: StockIn, db: Session = Depends(get_db), user: m.User = Depends(require_permission("inventory.adjust"))):
    admin_required(user)
    p = db.get(m.Product, pid)
    if not p: raise HTTPException(404, "Product not found")
    p.on_hand = Decimal(p.on_hand or 0)+body.quantity
    if p.on_hand < 0: raise HTTPException(422, "Stock cannot become negative")
    db.add(m.InventoryMovement(product_id=p.id, movement_type="ADJUSTMENT", quantity=body.quantity,
                               reason=body.reason, created_by=user.id))
    audit(db, user.id, "inventory.adjusted", "product", p.id, {"quantity": float(body.quantity)})
    db.commit(); return product_out(p)


# ---------- customers/projects ----------
@router.get("/customers")
def customers(q: str | None = None, status_filter: str | None = Query(None, alias="status"),
              page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=200),
              db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    if user.role not in ADMIN_ROLES:
        return []
    stmt = select(m.Customer)
    if status_filter:
        stmt = stmt.where(m.Customer.status == status_filter.upper())
    if q:
        term = f"%{q.strip()}%"
        project_match = select(m.Project.customer_id).where(or_(m.Project.name.ilike(term), m.Project.city.ilike(term)))
        stmt = stmt.where(or_(m.Customer.company_name.ilike(term), m.Customer.contact_person.ilike(term),
                              m.Customer.phone.ilike(term), m.Customer.email.ilike(term),
                              m.Customer.gstin.ilike(term), m.Customer.city.ilike(term),
                              m.Customer.id.in_(project_match)))
    rows = db.scalars(stmt.order_by(m.Customer.company_name).offset((page - 1) * page_size).limit(page_size)).all()
    result = []
    for customer in rows:
        projects = db.scalars(select(m.Project).where(m.Project.customer_id == customer.id)).all()
        timestamps = [value for value in [customer.updated_at, customer.created_at,
                                           *[project.updated_at for project in projects]] if value]
        latest = max(timestamps) if timestamps else None
        result.append({**customer_out(customer), "project_count": len(projects),
                       "active_project_count": sum(1 for project in projects if project.status == "ACTIVE"),
                       "last_activity": iso(latest)})
    return result


@router.get("/customers/{cid}")
def customer_detail(cid: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    c = db.get(m.Customer, cid)
    if not c: raise HTTPException(404, "Customer not found")
    projects = db.scalars(select(m.Project).where(m.Project.customer_id == c.id).order_by(m.Project.name)).all()
    if user.role not in ADMIN_ROLES:
        allowed = accessible_project_ids(db, user)
        projects = [p for p in projects if p.id in allowed]
        if not projects: raise HTTPException(403, "Customer is not assigned to you")
    pids = {p.id for p in projects}
    inquiries = db.scalars(select(m.Inquiry).where(m.Inquiry.project_id.in_(pids)).order_by(desc(m.Inquiry.created_at))).all() if pids else []
    quotations = db.scalars(select(m.Quotation).where(m.Quotation.project_id.in_(pids)).order_by(desc(m.Quotation.quotation_date))).all() if pids else []
    orders = db.scalars(select(m.Order).where(m.Order.project_id.in_(pids)).order_by(desc(m.Order.order_date))).all() if pids else []
    invoices = db.scalars(select(m.Invoice).where(m.Invoice.project_id.in_(pids)).order_by(desc(m.Invoice.invoice_date))).all() if pids else []
    project_cards = []
    for p in projects:
        buildings_count = db.scalar(select(func.count(m.Building.id)).where(m.Building.project_id == p.id)) or 0
        floors = db.scalar(select(func.count(m.Floor.id)).select_from(m.Floor).join(m.Building).where(m.Building.project_id == p.id)) or 0
        rooms = db.scalar(select(func.count(m.Room.id)).select_from(m.Room).join(m.Floor).join(m.Building).where(m.Building.project_id == p.id)) or 0
        users_count = db.scalar(select(func.count(m.ProjectUser.id)).where(m.ProjectUser.project_id == p.id, m.ProjectUser.status == "ACTIVE")) or 0
        product_quantity = db.scalar(select(func.coalesce(func.sum(m.RoomProduct.quantity), 0)).where(m.RoomProduct.project_id == p.id)) or 0
        project_cards.append({**project_basic(p), "partner": partner_out(p.partner), "buildings": buildings_count,
                              "floors": floors, "rooms": rooms, "product_quantity": f(product_quantity),
                              "users": users_count,
                              "inquiries": sum(1 for x in inquiries if x.project_id == p.id),
                              "quotations": sum(1 for x in quotations if x.project_id == p.id),
                              "orders": sum(1 for x in orders if x.project_id == p.id),
                              "invoices": sum(1 for x in invoices if (x.project_id or (x.order.project_id if x.order else None)) == p.id)})
    building_count = sum(x["buildings"] for x in project_cards)
    floor_count = sum(x["floors"] for x in project_cards)
    room_count = sum(x["rooms"] for x in project_cards)
    user_count = db.scalar(select(func.count(func.distinct(m.ProjectUser.user_id))).where(m.ProjectUser.project_id.in_(pids), m.ProjectUser.status == "ACTIVE")) if pids else 0
    outstanding = sum((Decimal(inv.grand_total) for inv in invoices if inv.status not in {"PAID", "CANCELLED"}), Decimal("0"))
    activity_rows = db.scalars(select(m.AuditLog).where(or_(
        (m.AuditLog.entity_type == "customer") & (m.AuditLog.entity_id == c.id),
        (m.AuditLog.entity_type == "project") & (m.AuditLog.entity_id.in_(pids)) if pids else False,
    )).order_by(desc(m.AuditLog.created_at)).limit(20)).all()
    actors = {u.id: u.name for u in db.scalars(select(m.User).where(m.User.id.in_({row.actor_id for row in activity_rows if row.actor_id}))).all()} if activity_rows else {}
    return {"customer": customer_out(c), "projects": project_cards,
            "summary": {"projects": len(projects), "active_projects": sum(1 for p in projects if p.status == "ACTIVE"),
                        "buildings": building_count, "floors": floor_count, "rooms": room_count,
                        "users": int(user_count or 0), "inquiries": len(inquiries),
                        "quotations": len(quotations), "orders": len(orders), "invoices": len(invoices),
                        "outstanding": f(outstanding)},
            "inquiries": [inquiry_out(i) for i in inquiries],
            "quotations": [quote_out(q, db, False) for q in quotations],
            "orders": [order_out(o, db, False) for o in orders],
            "invoices": [invoice_out(i, db) for i in invoices],
            "activity": [{"id": row.id, "actor": actors.get(row.actor_id, "System"),
                          "action": row.action, "entity_type": row.entity_type,
                          "entity_id": row.entity_id, "created_at": iso(row.created_at)} for row in activity_rows]}


@router.post("/customers", dependencies=[Depends(require_csrf)])
def add_customer(body: CustomerIn, db: Session = Depends(get_db), user: m.User = Depends(require_permission("customers.create"))):
    admin_required(user)
    c = m.Customer(**body.model_dump()); db.add(c); db.flush()
    audit(db, user.id, "customer.created", "customer", c.id); db.commit(); return customer_out(c)


@router.get("/projects")
def projects(workspace: str | None = None, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    w = workspace.upper() if workspace else None
    if w: ensure_workspace(user, w)
    rows = db.scalars(select(m.Project).order_by(m.Project.name)).all()
    if w: rows = [p for p in rows if w in (p.workspace_scope or [])]
    if user.role not in ADMIN_ROLES:
        allowed = accessible_project_ids(db, user); rows = [p for p in rows if p.id in allowed]
    out = []
    for p in rows:
        out.append({**project_basic(p), "customer": customer_out(p.customer), "partner": partner_out(p.partner),
                    "expected_completion": iso(p.expected_completion),
                    "buildings": db.scalar(select(func.count()).select_from(m.Building).where(m.Building.project_id == p.id)) or 0})
    return out


@router.get("/projects/{pid}")
def project_detail(pid: str, workspace: str | None = None, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    p = db.get(m.Project, pid)
    if not p: raise HTTPException(404, "Project not found")
    ensure_project_access(db, user, pid)
    show_prices = can_view_prices(db, user, pid)
    show_commercial = can_view_commercial(db, user, pid)
    active = workspace.upper() if workspace else None
    if active: ensure_workspace(user, active)
    scoped_building = None if user.role in ADMIN_ROLES else db.scalar(select(m.ProjectUser.building_id).where(
        m.ProjectUser.project_id == pid, m.ProjectUser.user_id == user.id, m.ProjectUser.status == "ACTIVE"))
    structure = project_structure(db, pid, include_price=show_prices, workspace=active, building_id=scoped_building)
    project_users = db.scalars(select(m.ProjectUser).where(m.ProjectUser.project_id == pid).order_by(m.ProjectUser.created_at)).all()
    inquiries = db.scalars(select(m.Inquiry).where(m.Inquiry.project_id == pid).order_by(desc(m.Inquiry.created_at))).all()
    quotations = db.scalars(select(m.Quotation).where(m.Quotation.project_id == pid).order_by(desc(m.Quotation.quotation_date))).all()
    orders = db.scalars(select(m.Order).where(m.Order.project_id == pid).order_by(desc(m.Order.order_date))).all()
    invoices = db.scalars(select(m.Invoice).where(m.Invoice.project_id == pid).order_by(desc(m.Invoice.invoice_date))).all()
    if scoped_building:
        inquiries = [row for row in inquiries if row.building_id == scoped_building]
        quotations = [row for row in quotations if row.building_id == scoped_building]
        orders = [row for row in orders if row.building_id == scoped_building]
        invoices = [row for row in invoices if row.building_id == scoped_building]
    if active:
        inquiries = [row for row in inquiries if row.workspace == active]
        quotations = [row for row in quotations if row.workspace == active]
        orders = [row for row in orders if row.workspace == active]
        invoices = [row for row in invoices if row.workspace == active]
    if not invoices:
        order_ids = [o.id for o in orders]
        invoices = db.scalars(select(m.Invoice).where(m.Invoice.order_id.in_(order_ids)).order_by(desc(m.Invoice.invoice_date))).all() if order_ids else []
    rooms = sum(len(fl["rooms"]) for b in structure for fl in b["floors"])
    floors = sum(len(b["floors"]) for b in structure)
    product_qty = sum(room["product_quantity"] for b in structure for fl in b["floors"] for room in fl["rooms"])
    unique_products = len({item["product"]["id"] for b in structure for fl in b["floors"] for room in fl["rooms"] for item in room["requirements"]})
    main_boards = sum(b.get("main_board_count", 0) for b in structure)
    return {"project": project_basic(p), "customer": customer_out(p.customer), "partner": partner_out(p.partner),
            "stats": {"buildings": len(structure), "floors": floors, "rooms": rooms,
                      "main_boards": main_boards, "users": len([x for x in project_users if x.status == "ACTIVE"]),
                      "products": product_qty, "unique_products": unique_products}, "buildings": structure,
            "users": [project_user_out(x) for x in project_users] if user.role in ADMIN_ROLES else [],
            "inquiries": [inquiry_out(x) for x in inquiries],
            "quotations": [quote_out(x, db, False, show_prices) for x in quotations] if show_commercial else [],
            "orders": [order_out(x, db, False, show_prices) for x in orders] if show_commercial else [],
            "invoices": [invoice_out(x, db, show_prices) for x in invoices] if show_commercial else [],
            "activity": activity_for(db, "project", p.id)}


@router.get("/projects/{pid}/structure")
def get_project_structure(pid: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    if not db.get(m.Project, pid): raise HTTPException(404, "Project not found")
    ensure_project_access(db, user, pid)
    scoped_building = None if user.role in ADMIN_ROLES else db.scalar(select(m.ProjectUser.building_id).where(
        m.ProjectUser.project_id == pid, m.ProjectUser.user_id == user.id, m.ProjectUser.status == "ACTIVE"))
    return project_structure(db, pid, include_price=user.role in ADMIN_ROLES, building_id=scoped_building)


@router.get("/projects/{pid}/users")
def get_project_users(pid: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    if not db.get(m.Project, pid): raise HTTPException(404, "Project not found")
    return [project_user_out(x) for x in db.scalars(select(m.ProjectUser).where(m.ProjectUser.project_id == pid)).all()]


@router.post("/projects/{pid}/users", dependencies=[Depends(require_csrf)])
def add_project_user(pid: str, body: ProjectUserIn, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    p = db.get(m.Project, pid)
    if not p: raise HTTPException(404, "Project not found")
    if body.building_id:
        building = db.get(m.Building, body.building_id)
        if not building or building.project_id != pid: raise HTTPException(422, "Building does not belong to this project")
    temporary_password = None
    if body.existing_user_id:
        target = db.get(m.User, body.existing_user_id)
        if not target: raise HTTPException(404, "User not found")
    else:
        if not body.name or not body.email: raise HTTPException(422, "Name and email are required")
        target = db.scalar(select(m.User).where(func.lower(m.User.email) == body.email.lower()))
        if not target:
            temporary_password = f"An!{secrets.token_urlsafe(10)}"
            target = m.User(name=body.name, email=body.email.lower(), phone=body.phone,
                            password_hash=hash_password(temporary_password), role="USER", status="ACTIVE",
                            workspaces=p.workspace_scope or ["LIGHTING", "AUTOMATION"],
                            permissions=["products.view", "projects.view_own"], must_change_password=True)
            db.add(target); db.flush()
    existing = db.scalar(select(m.ProjectUser).where(m.ProjectUser.project_id == pid, m.ProjectUser.user_id == target.id))
    if existing:
        existing.status = "ACTIVE"; existing.role = body.role.upper(); existing.permissions = body.permissions; existing.building_id = body.building_id; pu = existing
    else:
        pu = m.ProjectUser(project_id=pid, user_id=target.id, building_id=body.building_id, role=body.role.upper(), permissions=body.permissions,
                           status=body.status.upper(), created_by=user.id)
        db.add(pu); db.flush()
    audit(db, user.id, "project.user_assigned", "project", pid, {"user_id": target.id})
    db.commit(); db.refresh(pu)
    out = project_user_out(pu)
    if temporary_password:
        out["temporary_password"] = temporary_password
    return out


@router.patch("/projects/{pid}/users/{uid}", dependencies=[Depends(require_csrf)])
def update_project_user(pid: str, uid: str, body: ProjectUserUpdate, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    pu = db.scalar(select(m.ProjectUser).where(m.ProjectUser.project_id == pid, m.ProjectUser.user_id == uid))
    if not pu: raise HTTPException(404, "Project user assignment not found")
    if body.role is not None: pu.role = body.role.upper()
    if body.status is not None: pu.status = body.status.upper()
    if body.name is not None: pu.user.name = body.name
    if body.phone is not None: pu.user.phone = body.phone
    if body.permissions is not None: pu.permissions = body.permissions
    if "building_id" in body.model_fields_set:
        if body.building_id:
            building = db.get(m.Building, body.building_id)
            if not building or building.project_id != pid: raise HTTPException(422, "Building does not belong to this project")
        pu.building_id = body.building_id
    audit(db, user.id, "project.user_updated", "project", pid, {"user_id": uid, "status": pu.status})
    db.commit(); return project_user_out(pu)


@router.delete("/projects/{pid}/users/{uid}", dependencies=[Depends(require_csrf)])
def remove_project_user(pid: str, uid: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    pu = db.scalar(select(m.ProjectUser).where(m.ProjectUser.project_id == pid, m.ProjectUser.user_id == uid))
    if not pu: raise HTTPException(404, "Project user assignment not found")
    db.delete(pu); audit(db, user.id, "project.user_removed", "project", pid, {"user_id": uid}); db.commit()
    return {"ok": True}


def scoped_project_rows(db: Session, user: m.User, pid: str):
    if not db.get(m.Project, pid): raise HTTPException(404, "Project not found")
    ensure_project_access(db, user, pid)


@router.get("/projects/{pid}/inquiries")
def project_inquiries(pid: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    scoped_project_rows(db, user, pid)
    return [inquiry_out(x) for x in db.scalars(select(m.Inquiry).where(m.Inquiry.project_id == pid).order_by(desc(m.Inquiry.created_at))).all()]


@router.get("/projects/{pid}/quotations")
def project_quotations(pid: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    scoped_project_rows(db, user, pid)
    if not can_view_commercial(db, user, pid):
        raise HTTPException(403, "Commercial document permission is required")
    show_prices = can_view_prices(db, user, pid)
    return [quote_out(x, db, False, show_prices) for x in db.scalars(select(m.Quotation).where(m.Quotation.project_id == pid).order_by(desc(m.Quotation.quotation_date))).all()]


@router.get("/projects/{pid}/orders")
def project_orders(pid: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    scoped_project_rows(db, user, pid)
    if not can_view_commercial(db, user, pid):
        raise HTTPException(403, "Commercial document permission is required")
    show_prices = can_view_prices(db, user, pid)
    return [order_out(x, db, False, show_prices) for x in db.scalars(select(m.Order).where(m.Order.project_id == pid).order_by(desc(m.Order.order_date))).all()]


@router.get("/projects/{pid}/invoices")
def project_invoices(pid: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    scoped_project_rows(db, user, pid)
    if not can_view_commercial(db, user, pid):
        raise HTTPException(403, "Commercial document permission is required")
    rows = db.scalars(select(m.Invoice).where(m.Invoice.project_id == pid).order_by(desc(m.Invoice.invoice_date))).all()
    if not rows:
        order_ids = db.scalars(select(m.Order.id).where(m.Order.project_id == pid)).all()
        rows = db.scalars(select(m.Invoice).where(m.Invoice.order_id.in_(order_ids)).order_by(desc(m.Invoice.invoice_date))).all() if order_ids else []
    return [invoice_out(x, db, can_view_prices(db, user, pid)) for x in rows]


# ---------- inquiry structure helpers ----------
def resolve_customer(db: Session, body_customer_id: str | None, body_customer: CustomerIn | None) -> m.Customer:
    if body_customer_id:
        c = db.get(m.Customer, body_customer_id)
        if not c: raise HTTPException(404, "Customer not found")
        return c
    if not body_customer:
        raise HTTPException(422, "Select an existing customer or provide a new customer")
    existing = None
    if body_customer.email:
        existing = db.scalar(select(m.Customer).where(func.lower(m.Customer.email) == body_customer.email.lower()))
    if existing:
        return existing
    c = m.Customer(**body_customer.model_dump()); db.add(c); db.flush(); return c


def normalize_floors(body: InquiryCreate) -> list[FloorIn]:
    if body.floors_data:
        return body.floors_data
    count = body.floors or 1
    room_names = body.room_names or ["Reception"]
    floors = [FloorIn(name="Ground Floor" if i == 0 else f"Floor {i}", rooms=[RoomIn(name=x) for x in room_names]) for i in range(count)]
    # Translate legacy bulk requirements deterministically.
    for raw in body.requirements or []:
        product_id = raw.get("product_id"); qty = raw.get("quantity", 1); note = raw.get("notes")
        source_floor = int(raw.get("floor_index", 0)); source_room = raw.get("room_name") or room_names[0]
        targets: list[tuple[int, str]] = []
        if raw.get("apply_all_rooms"):
            targets = [(fi, rn) for fi in range(count) for rn in room_names]
        elif raw.get("apply_all_floors"):
            targets = [(fi, source_room) for fi in range(count)]
        else:
            targets = [(source_floor, source_room)]
        for fi, rn in targets:
            if 0 <= fi < len(floors):
                room = next((r for r in floors[fi].rooms if r.name == rn), None)
                if room and product_id:
                    room.requirements.append(RequirementIn(product_id=product_id, quantity=qty, notes=note))
    return floors


def update_project_structure(db: Session, project: m.Project, inquiry: m.Inquiry, building_id: str | None,
                             building_name: str, floors_data: list[FloorIn], actor_id: str):
    """Merge an inquiry scope into shared structure without deleting historical rows."""
    if building_id:
        building = db.get(m.Building, building_id)
        if not building or building.project_id != project.id:
            raise HTTPException(422, "Selected building does not belong to the selected project")
    else:
        duplicate = db.scalar(select(m.Building).where(
            m.Building.project_id == project.id,
            func.lower(m.Building.name) == (building_name or "Tower A").strip().lower(),
            m.Building.status == "ACTIVE",
        ))
        if duplicate:
            raise HTTPException(409, "A building with this name already exists; select the existing building")
        next_sort = db.scalar(select(func.max(m.Building.sort_order)).where(m.Building.project_id == project.id)) or -1
        building = m.Building(project_id=project.id, name=(building_name or "Tower A").strip(),
                              planned_floors=len(floors_data), sort_order=next_sort + 1)
        db.add(building); db.flush()
    building.planned_floors = max(building.planned_floors or 0, len(floors_data))
    db.execute(delete(m.RoomRequirement).where(m.RoomRequirement.inquiry_id == inquiry.id))
    # RoomProduct is the authoritative current project configuration. RoomRequirement
    # remains the inquiry snapshot used to generate that inquiry's commercial BOQ.
    db.execute(delete(m.RoomProduct).where(m.RoomProduct.linked_inquiry_id == inquiry.id))
    workspaces: set[str] = set()
    for fi, fin in enumerate(floors_data):
        fl = db.get(m.Floor, fin.id) if fin.id else None
        if fl and fl.building_id != building.id:
            raise HTTPException(422, "Selected floor does not belong to the selected building")
        if not fl:
            fl = db.scalar(select(m.Floor).where(
                m.Floor.building_id == building.id,
                func.lower(m.Floor.name) == fin.name.strip().lower(),
                m.Floor.status == "ACTIVE",
            ))
        if not fl:
            fl = m.Floor(building_id=building.id, name=fin.name.strip(), sort_order=fi)
            db.add(fl); db.flush()
        else:
            fl.name = fin.name.strip(); fl.sort_order = fi; fl.status = "ACTIVE"
        for ri, rin in enumerate(fin.rooms):
            room = db.get(m.Room, rin.id) if rin.id else None
            if room and room.floor_id != fl.id:
                raise HTTPException(422, "Selected room does not belong to the selected floor")
            if not room:
                room = db.scalar(select(m.Room).where(
                    m.Room.floor_id == fl.id,
                    func.lower(m.Room.name) == rin.name.strip().lower(),
                    m.Room.status == "ACTIVE",
                ))
            if not room:
                room = m.Room(floor_id=fl.id, name=rin.name.strip(), sort_order=ri)
                db.add(room); db.flush()
            room.name = rin.name.strip(); room.room_type = rin.room_type; room.area = rin.area
            room.occupancy = rin.occupancy; room.notes = rin.notes; room.sort_order = ri; room.status = "ACTIVE"
            merged: dict[str, RequirementIn] = {}
            for req in rin.requirements:
                p = db.get(m.Product, req.product_id)
                if not p or p.status != "ACTIVE": raise HTTPException(422, f"Invalid product: {req.product_id}")
                if p.workspace != inquiry.workspace:
                    raise HTTPException(422, f"{p.workspace.title()} product cannot be added to a {inquiry.workspace.title()} inquiry")
                workspaces.add(p.workspace)
                if req.product_id in merged:
                    merged[req.product_id].quantity += req.quantity
                else:
                    merged[req.product_id] = req.model_copy(deep=True)
            for req in merged.values():
                p = db.get(m.Product, req.product_id)
                db.add(m.RoomRequirement(inquiry_id=inquiry.id, room_id=room.id, product_id=p.id,
                                         quantity=req.quantity, unit=p.unit, notes=req.notes))
                configured = db.scalar(select(m.RoomProduct).where(
                    m.RoomProduct.room_id == room.id, m.RoomProduct.product_id == p.id
                ))
                if configured:
                    configured.project_id = project.id; configured.building_id = building.id
                    configured.floor_id = fl.id; configured.quantity = req.quantity
                    configured.unit = p.unit; configured.notes = req.notes
                    configured.approval_status = "ADDED"; configured.source = "INQUIRY"
                    configured.linked_inquiry_id = inquiry.id; configured.updated_by = actor_id
                else:
                    db.add(m.RoomProduct(project_id=project.id, building_id=building.id, floor_id=fl.id,
                                         room_id=room.id, product_id=p.id, quantity=req.quantity,
                                         unit=p.unit, notes=req.notes, approval_status="ADDED",
                                         source="INQUIRY", linked_inquiry_id=inquiry.id,
                                         created_by=actor_id, updated_by=actor_id))
    inquiry.workspace_scope = [inquiry.workspace]
    project.workspace_scope = sorted(set(project.workspace_scope or []) | set(inquiry.workspace_scope or []))
    audit(db, actor_id, "project.structure_merged", "inquiry", inquiry.id,
          {"building_id": building.id, "floors": len(floors_data),
           "rooms": sum(len(x.rooms) for x in floors_data)})
    return building


# ---------- inquiries ----------
@router.get("/inquiries")
def inquiries(workspace: str | None = None, status_filter: str | None = Query(None, alias="status"),
              db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    stmt = select(m.Inquiry)
    if workspace:
        w = workspace.upper(); ensure_workspace(user, w); stmt = stmt.where(m.Inquiry.workspace == w)
    if user.role not in ADMIN_ROLES:
        stmt = stmt.where(m.Inquiry.project_id.in_(accessible_project_ids(db, user)))
    if status_filter: stmt = stmt.where(m.Inquiry.status == status_filter.upper())
    return [inquiry_out(i) for i in db.scalars(stmt.order_by(desc(m.Inquiry.created_at))).all()]


@router.get("/inquiries/{iid}")
def inquiry_detail(iid: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    i = db.get(m.Inquiry, iid)
    if not i: raise HTTPException(404, "Inquiry not found")
    ensure_workspace(user, i.workspace)
    ensure_project_access(db, user, i.project_id)
    out = inquiry_out(i)
    out["structure"] = project_structure(db, i.project_id, i.id, include_price=user.role in ADMIN_ROLES)
    out["boq"] = []
    for row in boq_rows(db, iid):
        value = {**row, "quantity": f(row["quantity"])}
        if user.role in ADMIN_ROLES:
            value.update({"rate": f(row["rate"]), "tax_rate": f(row["tax_rate"])})
        else:
            value.pop("rate", None); value.pop("tax_rate", None)
        out["boq"].append(value)
    out["partner"] = partner_out(i.project.partner)
    q = db.scalar(select(m.Quotation).where(m.Quotation.inquiry_id == iid).order_by(desc(m.Quotation.quotation_date)).limit(1))
    out["quotation"] = quote_out(q, db, False) if q else None
    out["activity"] = activity_for(db, "inquiry", i.id)
    return out


@router.post("/inquiries", dependencies=[Depends(require_csrf)])
def create_inquiry(body: InquiryCreate, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    workspace = body.workspace.upper(); ensure_workspace(user, workspace)
    try:
        customer = resolve_customer(db, body.customer_id, body.customer)
        if body.project_id:
            project = db.get(m.Project, body.project_id)
            if not project: raise HTTPException(404, "Project not found")
            if project.customer_id != customer.id: raise HTTPException(409, "Project does not belong to selected customer")
        else:
            duplicate = db.scalar(select(m.Project).where(
                m.Project.customer_id == customer.id,
                func.lower(m.Project.name) == body.project_name.strip().lower(),
                m.Project.status == "ACTIVE",
            ))
            if duplicate:
                raise HTTPException(409, "A project with this name already exists; select the existing project")
            project = m.Project(customer_id=customer.id, name=body.project_name.strip(), address=body.address,
                                city=body.city, state=body.state, workspace_scope=[workspace], owner_id=user.id)
            db.add(project); db.flush(); audit(db, user.id, "project.created", "project", project.id)
        if body.partner:
            partner = m.Partner(**body.partner.model_dump()); db.add(partner); db.flush(); project.partner_id = partner.id
        inquiry = m.Inquiry(number=next_number(db, "inquiry", "ANIPL"), customer_id=customer.id,
                            project_id=project.id, workspace=workspace, workspace_scope=[workspace], owner_id=user.id,
                            status="DRAFT", wizard_step=body.wizard_step, notes=body.notes, source="ADMIN")
        db.add(inquiry); db.flush()
        floors_data = normalize_floors(body)
        building = update_project_structure(db, project, inquiry, body.building_id, body.building_name, floors_data, user.id)
        inquiry.building_id = building.id
        inquiry.is_project_wide = False
        estimate_inquiry(db, inquiry)
        audit(db, user.id, "inquiry.drafted", "inquiry", inquiry.id, {"number": inquiry.number})
        db.commit(); db.refresh(inquiry)
        return inquiry_out(inquiry)
    except HTTPException:
        db.rollback(); raise
    except Exception:
        db.rollback(); raise


@router.patch("/inquiries/{iid}", dependencies=[Depends(require_csrf)])
def update_inquiry(iid: str, body: InquiryUpdate, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    i = db.get(m.Inquiry, iid)
    if not i: raise HTTPException(404, "Inquiry not found")
    project = i.project
    if body.customer_id or body.customer:
        customer = resolve_customer(db, body.customer_id, body.customer)
        i.customer_id = customer.id; project.customer_id = customer.id
    if body.project_name is not None: project.name = body.project_name.strip()
    if body.address is not None: project.address = body.address
    if body.city is not None: project.city = body.city
    if body.state is not None: project.state = body.state
    if body.remove_partner:
        project.partner_id = None
    elif body.partner:
        if project.partner:
            for key, val in body.partner.model_dump().items(): setattr(project.partner, key, val)
        else:
            partner = m.Partner(**body.partner.model_dump()); db.add(partner); db.flush(); project.partner_id = partner.id
    if body.notes is not None: i.notes = body.notes
    if body.wizard_step is not None: i.wizard_step = body.wizard_step
    if body.building_id is not None and body.floors_data is None:
        building = db.get(m.Building, body.building_id)
        if not building or building.project_id != project.id:
            raise HTTPException(422, "Selected building does not belong to this project")
        i.building_id = building.id
    if body.floors_data is not None:
        current_building = db.get(m.Building, body.building_id or i.building_id) if (body.building_id or i.building_id) else None
        target_building = update_project_structure(
            db, project, i, body.building_id or i.building_id,
            body.building_name or (current_building.name if current_building else "Tower A"),
            body.floors_data, user.id,
        )
        i.building_id = target_building.id
        i.is_project_wide = False
    estimate_inquiry(db, i)
    audit(db, user.id, "inquiry.modified", "inquiry", i.id)
    db.commit(); return inquiry_detail(iid, db, user)


@router.post("/inquiries/{iid}/submit", dependencies=[Depends(require_csrf)])
def submit_inquiry(iid: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    i = db.get(m.Inquiry, iid)
    if not i: raise HTTPException(404, "Inquiry not found")
    if i.status != "DRAFT": raise HTTPException(409, "Only a DRAFT inquiry can be submitted")
    if not boq_rows(db, i.id): raise HTTPException(422, "Add at least one room product before submission")
    i.status = "IN_PROCESS"; i.wizard_step = 5; i.submitted_at = datetime.now(timezone.utc)
    estimate_inquiry(db, i)
    try:
        quotation = create_quotation_from_inquiry(db, i, user.id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(422, str(exc))
    audit(db, user.id, "inquiry.submitted", "inquiry", i.id, {"quotation_id": quotation.id})
    db.commit(); db.refresh(i)
    result = inquiry_out(i)
    result["quotation"] = quote_out(quotation, db, False, True)
    result["boq"] = [{**row, "quantity": f(row["quantity"]), "rate": f(row["rate"]),
                       "tax_rate": f(row["tax_rate"]), "line_subtotal": f(row["line_subtotal"]),
                       "tax_amount": f(row["tax_amount"]), "line_total": f(row["line_total"])}
                      for row in boq_rows(db, i.id)]
    return result


@router.get("/inquiries/{iid}/boq")
def inquiry_boq(iid: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    i = db.get(m.Inquiry, iid)
    if not i: raise HTTPException(404, "Inquiry not found")
    ensure_workspace(user, i.workspace)
    ensure_project_access(db, user, i.project_id)
    result = []
    for row in boq_rows(db, iid):
        value = {**row, "quantity": f(row["quantity"])}
        if user.role in ADMIN_ROLES:
            value.update({"rate": f(row["rate"]), "tax_rate": f(row["tax_rate"])})
        else:
            value.pop("rate", None); value.pop("tax_rate", None)
        result.append(value)
    return result


@router.get("/inquiries/{iid}/boq.xlsx")
def inquiry_boq_excel(iid: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    i = db.get(m.Inquiry, iid)
    if not i: raise HTTPException(404, "Inquiry not found")
    ensure_workspace(user, i.workspace)
    ensure_project_access(db, user, i.project_id)
    wb = Workbook(); ws = wb.active; ws.title = "BOQ"
    headers = ["Product ID", "Product", "System", "Category", "Unit", "Quantity"]
    if user.role in ADMIN_ROLES: headers += ["Rate", "Tax %"]
    ws.append(headers)
    for r in boq_rows(db, iid):
        values = [r["sku"], r["name"], r["workspace"], r["category"], r["unit"], float(r["quantity"])]
        if user.role in ADMIN_ROLES: values += [float(r["rate"]), float(r["tax_rate"])]
        ws.append(values)
    bio = BytesIO(); wb.save(bio); bio.seek(0)
    audit(db, user.id, "inquiry.boq_exported", "inquiry", i.id); db.commit()
    return StreamingResponse(bio, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{i.number}-BOQ.xlsx"'})


@router.get("/inquiries/{iid}/quotation")
def inquiry_quotation(iid: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    i = db.get(m.Inquiry, iid)
    if not i: raise HTTPException(404, "Inquiry not found")
    ensure_workspace(user, i.workspace)
    ensure_project_access(db, user, i.project_id)
    q = db.scalar(select(m.Quotation).where(m.Quotation.inquiry_id == iid).order_by(desc(m.Quotation.quotation_date)).limit(1))
    return quote_out(q, db) if q else None


@router.post("/inquiries/{iid}/quotation", dependencies=[Depends(require_csrf)])
def make_quotation(iid: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    i = db.get(m.Inquiry, iid)
    if not i: raise HTTPException(404, "Inquiry not found")
    try:
        q = create_quotation_from_inquiry(db, i, user.id)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    db.commit(); return quote_out(q, db)


@router.post("/inquiries/{iid}/quotation/refresh", dependencies=[Depends(require_csrf)])
def refresh_quotation(iid: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    i = db.get(m.Inquiry, iid)
    if not i: raise HTTPException(404, "Inquiry not found")
    q = db.scalar(select(m.Quotation).where(m.Quotation.inquiry_id == iid).order_by(desc(m.Quotation.quotation_date)).limit(1))
    if not q: raise HTTPException(404, "Quotation not found")
    try: replace_draft_quotation_items(db, q, i, user.id)
    except ValueError as exc: raise HTTPException(409, str(exc))
    db.commit(); return quote_out(q, db)


@router.post("/inquiries/{iid}/quotation/revision", dependencies=[Depends(require_csrf)])
def new_quotation_revision(iid: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    i = db.get(m.Inquiry, iid)
    if not i: raise HTTPException(404, "Inquiry not found")
    try:
        q = create_quotation_revision(db, i, user.id)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    db.commit()
    return quote_out(q, db)


@router.post("/product-requests", dependencies=[Depends(require_csrf)])
def product_request(body: ProductRequestIn, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    if user.role in ADMIN_ROLES: raise HTTPException(422, "Use the inquiry workflow for admin-created requests")
    require_project_permission(db, user, body.project_id, "requests.create")
    project = db.get(m.Project, body.project_id)
    requested_rooms = [db.get(m.Room, item.room_id) for item in body.items]
    if any(room is None for room in requested_rooms):
        raise HTTPException(422, "Every request item must reference an existing room")
    building_ids = {room.floor.building_id for room in requested_rooms if room}
    if len(building_ids) != 1:
        raise HTTPException(422, "Submit separate product requests for different buildings")
    building = db.get(m.Building, next(iter(building_ids)))
    if not building or building.project_id != project.id:
        raise HTTPException(403, "Selected room does not belong to your assigned project")
    workspace = body.workspace.upper(); ensure_workspace(user, workspace)
    if workspace not in {"LIGHTING", "AUTOMATION"}: raise HTTPException(422, "Application must be LIGHTING or AUTOMATION")
    inquiry = m.Inquiry(number=next_number(db, "inquiry", "ANIPL"), customer_id=project.customer_id,
                        project_id=project.id, building_id=building.id, is_project_wide=False,
                        workspace=workspace, workspace_scope=[workspace], owner_id=user.id, status="IN_PROCESS", wizard_step=5,
                        source="USER_REQUEST", notes=body.notes, submitted_at=datetime.now(timezone.utc))
    db.add(inquiry); db.flush(); workspaces = set()
    for item in body.items:
        p = db.get(m.Product, item.product_id)
        if not p or p.status != "ACTIVE": raise HTTPException(422, f"Invalid product {item.product_id}")
        if p.workspace != workspace: raise HTTPException(422, "Cross-application product selection is not allowed")
        room = db.get(m.Room, item.room_id)
        room_project = room.floor.building.project_id
        if room_project != project.id: raise HTTPException(403, "Room does not belong to your assigned project")
        existing = db.scalar(select(m.RoomRequirement).where(m.RoomRequirement.inquiry_id == inquiry.id,
                                                              m.RoomRequirement.room_id == room.id,
                                                              m.RoomRequirement.product_id == p.id))
        if existing: existing.quantity += item.quantity
        else: db.add(m.RoomRequirement(inquiry_id=inquiry.id, room_id=room.id, product_id=p.id,
                                       quantity=item.quantity, unit=p.unit, notes=item.notes))
        workspaces.add(p.workspace)
    inquiry.workspace_scope = [workspace]; estimate_inquiry(db, inquiry)
    audit(db, user.id, "product_request.submitted", "inquiry", inquiry.id, {"project_id": project.id})
    db.commit(); return inquiry_out(inquiry)


# ---------- quotations / orders / invoices ----------
@router.get("/quotations")
def quotations(workspace: str | None = None, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    stmt = select(m.Quotation)
    if workspace:
        w = workspace.upper(); ensure_workspace(user, w); stmt = stmt.where(m.Quotation.workspace == w)
    if user.role not in ADMIN_ROLES: stmt = stmt.where(m.Quotation.project_id.in_(accessible_project_ids(db, user)))
    rows = db.scalars(stmt.order_by(desc(m.Quotation.quotation_date))).all()
    return [quote_out(q, db, False, can_view_prices(db, user, q.project_id)) for q in rows
            if can_view_commercial(db, user, q.project_id)]


@router.get("/quotations/{qid}")
def quotation_detail(qid: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    q = db.get(m.Quotation, qid)
    if not q: raise HTTPException(404, "Quotation not found")
    ensure_workspace(user, q.workspace)
    require_project_permission(db, user, q.project_id, "commercial.documents.view")
    return quote_out(q, db, True, can_view_prices(db, user, q.project_id))


@router.patch("/quotations/{qid}/discount", dependencies=[Depends(require_csrf)])
def quotation_discount(qid: str, body: DiscountIn, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    q = db.get(m.Quotation, qid)
    if not q: raise HTTPException(404, "Quotation not found")
    ensure_workspace(user, q.workspace)
    if q.status != "DRAFT": raise HTTPException(409, "Discount can only be changed while quotation is DRAFT")
    q.discount_percent = max(Decimal("0"), min(Decimal("100"), body.discount_percent)); recalc_quotation(db, q)
    audit(db, user.id, "quotation.discount_changed", "quotation", q.id, {"discount_percent": float(q.discount_percent)})
    db.commit(); return quote_out(q, db)


@router.post("/quotations/{qid}/status", dependencies=[Depends(require_csrf)])
def quotation_status(qid: str, body: StatusIn, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    q = db.get(m.Quotation, qid)
    if not q: raise HTTPException(404, "Quotation not found")
    new = body.status.upper(); allowed = {
        "DRAFT": {"SENT", "REJECTED"},
        "SENT": {"ACCEPTED", "REJECTED", "EXPIRED", "SUPERSEDED"},
        "ACCEPTED": set(), "REJECTED": set(), "EXPIRED": set(), "SUPERSEDED": set(),
    }
    if new not in allowed.get(q.status, set()): raise HTTPException(400, f"Invalid transition {q.status} -> {new}")
    if new == "SENT":
        thresholds = [Decimal(x) for x in db.scalars(select(m.PricingRule.approval_threshold_percent).where(
            m.PricingRule.status == "ACTIVE", m.PricingRule.approval_threshold_percent.is_not(None))).all()]
        if thresholds and Decimal(q.discount_percent or 0) > min(thresholds):
            approval = db.scalar(select(m.ApprovalRequest).where(
                m.ApprovalRequest.entity_type == "QUOTATION", m.ApprovalRequest.entity_id == q.id,
                m.ApprovalRequest.rule_code == "PRICING_DISCOUNT", m.ApprovalRequest.status == "APPROVED"))
            if not approval:
                pending = db.scalar(select(m.ApprovalRequest).where(
                    m.ApprovalRequest.entity_type == "QUOTATION", m.ApprovalRequest.entity_id == q.id,
                    m.ApprovalRequest.rule_code == "PRICING_DISCOUNT", m.ApprovalRequest.status == "PENDING"))
                if not pending:
                    db.add(m.ApprovalRequest(entity_type="QUOTATION", entity_id=q.id, project_id=q.project_id,
                        rule_code="PRICING_DISCOUNT", status="PENDING", requested_by=user.id,
                        comments=f"Discount {q.discount_percent}% exceeds approval threshold {min(thresholds)}%"))
                    db.commit()
                raise HTTPException(409, "Discount approval is required before sending this quotation")
    old = q.status; q.status = new
    if new == "SENT":
        q.sent_at = datetime.now(timezone.utc)
        inquiry = db.get(m.Inquiry, q.inquiry_id) if q.inquiry_id else None
        if inquiry and inquiry.status == "IN_PROCESS":
            inquiry.status = "QUOTED"
    if new == "ACCEPTED": q.accepted_at = datetime.now(timezone.utc)
    audit(db, user.id, "quotation.status_changed", "quotation", q.id, {"from": old, "to": new}); db.commit()
    return quote_out(q, db)


@router.post("/quotations/{qid}/order", dependencies=[Depends(require_csrf)])
def quotation_to_order(qid: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    q = db.get(m.Quotation, qid)
    if not q: raise HTTPException(404, "Quotation not found")
    try: o = convert_quotation_to_order(db, q, user.id)
    except ValueError as e: raise HTTPException(400, str(e))
    db.commit(); return order_out(o, db)


@router.get("/quotations/{qid}/pdf")
def quote_pdf(qid: str, download: bool = Query(False), db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    q = db.get(m.Quotation, qid)
    if not q: raise HTTPException(404, "Quotation not found")
    ensure_workspace(user, q.workspace)
    require_project_permission(db, user, q.project_id, "commercial.documents.view")
    if not can_view_prices(db, user, q.project_id):
        raise HTTPException(403, "Price permission is required for this quotation document")
    filename = document_filename("Quotation", q.number, q.project.name or q.customer.company_name)
    return Response(quotation_pdf(db, q), media_type="application/pdf",
                    headers={"Content-Disposition": pdf_disposition(filename, download),
                             "X-Content-Type-Options": "nosniff"})


@router.get("/orders")
def orders(workspace: str | None = None, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    stmt = select(m.Order)
    if workspace:
        w = workspace.upper(); ensure_workspace(user, w); stmt = stmt.where(m.Order.workspace == w)
    if user.role not in ADMIN_ROLES: stmt = stmt.where(m.Order.project_id.in_(accessible_project_ids(db, user)))
    rows = db.scalars(stmt.order_by(desc(m.Order.order_date))).all()
    return [order_out(o, db, False, can_view_prices(db, user, o.project_id)) for o in rows
            if can_view_commercial(db, user, o.project_id)]


@router.get("/orders/{oid}")
def order_detail(oid: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    o = db.get(m.Order, oid)
    if not o: raise HTTPException(404, "Order not found")
    ensure_workspace(user, o.workspace)
    require_project_permission(db, user, o.project_id, "commercial.documents.view")
    return order_out(o, db, True, can_view_prices(db, user, o.project_id))


@router.post("/orders/{oid}/status", dependencies=[Depends(require_csrf)])
def order_status(oid: str, body: StatusIn, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    o = db.get(m.Order, oid)
    if not o: raise HTTPException(404, "Order not found")
    try: update_order_status(db, o, body.status.upper(), user.id)
    except ValueError as e: raise HTTPException(400, str(e))
    db.commit(); return order_out(o, db)


@router.post("/orders/{oid}/invoice", dependencies=[Depends(require_csrf)])
def order_invoice(oid: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    o = db.get(m.Order, oid)
    if not o: raise HTTPException(404, "Order not found")
    try:
        inv = create_invoice_from_order(db, o, user.id)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    db.commit(); return invoice_out(inv, db)


@router.get("/invoices")
def invoices(workspace: str | None = None, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    stmt = select(m.Invoice)
    if workspace:
        w = workspace.upper(); ensure_workspace(user, w); stmt = stmt.where(m.Invoice.workspace == w)
    if user.role not in ADMIN_ROLES: stmt = stmt.where(m.Invoice.project_id.in_(accessible_project_ids(db, user)))
    rows = db.scalars(stmt.order_by(desc(m.Invoice.invoice_date))).all()
    return [invoice_out(i, db, can_view_prices(db, user, i.project_id or i.order.project_id)) for i in rows
            if can_view_commercial(db, user, i.project_id or i.order.project_id)]


@router.get("/invoices/{iid}")
def invoice_detail(iid: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    inv = db.get(m.Invoice, iid)
    if not inv: raise HTTPException(404, "Invoice not found")
    ensure_workspace(user, inv.workspace)
    pid = inv.project_id or inv.order.project_id
    require_project_permission(db, user, pid, "commercial.documents.view")
    return invoice_out(inv, db, can_view_prices(db, user, pid))


@router.get("/invoices/{iid}/pdf")
def invoice_pdf_ep(iid: str, download: bool = Query(False), db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    inv = db.get(m.Invoice, iid)
    if not inv: raise HTTPException(404, "Invoice not found")
    ensure_workspace(user, inv.workspace)
    pid = inv.project_id or inv.order.project_id
    require_project_permission(db, user, pid, "commercial.documents.view")
    if not can_view_prices(db, user, pid):
        raise HTTPException(403, "Price permission is required for this invoice document")
    subject = inv.project.name if inv.project else inv.customer.company_name
    filename = document_filename("Invoice", inv.number, subject)
    return Response(invoice_pdf(db, inv), media_type="application/pdf",
                    headers={"Content-Disposition": pdf_disposition(filename, download),
                             "X-Content-Type-Options": "nosniff"})


# ---------- admin users/settings/audit ----------
@router.get("/users")
def users(db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user); return [user_out(x) for x in db.scalars(select(m.User).order_by(m.User.name)).all()]


@router.post("/users", dependencies=[Depends(require_csrf)])
def create_user(body: UserIn, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    if db.scalar(select(m.User).where(func.lower(m.User.email) == body.email.lower())): raise HTTPException(409, "Email already exists")
    u = m.User(name=body.name, email=body.email.lower(), phone=body.phone, password_hash=hash_password(body.password),
               role=body.role.upper(), workspaces=[x.upper() for x in body.workspaces], permissions=body.permissions,
               must_change_password=True)
    db.add(u); db.flush(); audit(db, user.id, "user.created", "user", u.id); db.commit(); return user_out(u)


@router.post("/users/{uid}/status", dependencies=[Depends(require_csrf)])
def user_status(uid: str, body: StatusIn, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    u = db.get(m.User, uid)
    if not u: raise HTTPException(404, "User not found")
    if u.id == user.id and body.status.upper() != "ACTIVE": raise HTTPException(400, "Cannot disable current user")
    u.status = body.status.upper(); audit(db, user.id, "user.status_changed", "user", u.id, {"status": u.status}); db.commit(); return user_out(u)


@router.get("/settings")
def get_settings_ep(user: m.User = Depends(get_current_user)):
    admin_required(user)
    return {"company_name": settings.company_name, "company_gstin": settings.company_gstin,
            "company_pan": settings.company_pan, "company_address": settings.company_address,
            "company_phone": settings.company_phone, "company_email": settings.company_email,
            "invoice_prefix": "INV", "order_prefix": "ORD", "quotation_prefix": "QT", "inquiry_prefix": "ANIPL"}


@router.get("/audit-logs")
def audit_logs(limit: int = 100, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    rows = db.scalars(select(m.AuditLog).order_by(desc(m.AuditLog.created_at)).limit(min(max(limit, 1), 500))).all()
    actor_ids = {r.actor_id for r in rows if r.actor_id}
    actors = {u.id: u.name for u in db.scalars(select(m.User).where(m.User.id.in_(actor_ids))).all()} if actor_ids else {}
    return [{"id": r.id, "actor": actors.get(r.actor_id, "System"), "action": r.action,
             "entity_type": r.entity_type, "entity_id": r.entity_id, "metadata": r.metadata_json,
             "created_at": iso(r.created_at)} for r in rows]


# ---------- secure global search ----------
@router.get("/search")
def search(q: str, workspace: str | None = None, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    term = f"%{q.strip()}%"; results = []
    if len(q.strip()) < 2: return results
    family_stmt = select(m.ProductFamily).where(or_(m.ProductFamily.name.ilike(term), m.ProductFamily.brand.ilike(term))).limit(6)
    for family in db.scalars(family_stmt).all():
        if user.role in ADMIN_ROLES or family.workspace in (user.workspaces or []):
            results.append({"type": "product_family", "id": family.id, "label": family.name,
                            "sub": f"{family.brand} · {family.category.name}", "workspace": family.workspace})
    product_stmt = select(m.Product).where(or_(m.Product.name.ilike(term), m.Product.sku.ilike(term))).limit(6)
    for p in db.scalars(product_stmt).all():
        if user.role in ADMIN_ROLES or p.workspace in (user.workspaces or []):
            results.append({"type": "product", "id": p.family_id or p.id,
                            "variant_id": p.id, "label": p.name, "sub": p.sku, "workspace": p.workspace})
    allowed = accessible_project_ids(db, user)
    if user.role in ADMIN_ROLES:
        for c in db.scalars(select(m.Customer).where(m.Customer.company_name.ilike(term)).limit(5)).all():
            results.append({"type": "customer", "id": c.id, "label": c.company_name, "sub": c.city})
    for p in db.scalars(select(m.Project).where(m.Project.name.ilike(term), m.Project.id.in_(allowed)).limit(5)).all():
        results.append({"type": "project", "id": p.id, "customer_id": p.customer_id,
                        "label": p.name, "sub": p.customer.company_name})
    building_stmt = select(m.Building).join(m.Project).where(
        m.Building.name.ilike(term), m.Building.project_id.in_(allowed)
    ).limit(5)
    for building in db.scalars(building_stmt).all():
        results.append({"type": "building", "id": building.id, "project_id": building.project_id,
                        "customer_id": building.project.customer_id, "label": building.name,
                        "sub": building.project.name})
    room_stmt = select(m.Room).join(m.Floor).join(m.Building).join(m.Project).where(
        m.Room.name.ilike(term), m.Building.project_id.in_(allowed)
    ).limit(5)
    for room in db.scalars(room_stmt).all():
        building = room.floor.building
        results.append({"type": "room", "id": room.id, "floor_id": room.floor_id,
                        "building_id": building.id, "project_id": building.project_id,
                        "customer_id": building.project.customer_id, "label": room.name,
                        "sub": f"{room.floor.name} · {building.name}"})
    for i in db.scalars(select(m.Inquiry).where(or_(m.Inquiry.number.ilike(term), m.Inquiry.project_id.in_(
            select(m.Project.id).where(m.Project.name.ilike(term)))), m.Inquiry.project_id.in_(allowed)).limit(5)).all():
        results.append({"type": "inquiry", "id": i.id, "project_id": i.project_id,
                        "customer_id": i.customer_id, "label": i.number,
                        "sub": i.project.name, "workspace": i.workspace})
    for obj, typ, model, num_col, pid_col in [
        (m.Quotation, "quotation", m.Quotation, m.Quotation.number, m.Quotation.project_id),
        (m.Order, "order", m.Order, m.Order.number, m.Order.project_id),
        (m.Invoice, "invoice", m.Invoice, m.Invoice.number, m.Invoice.project_id),
    ]:
        for row in db.scalars(select(model).where(num_col.ilike(term), pid_col.in_(allowed)).limit(5)).all():
            results.append({"type": typ, "id": row.id, "label": row.number,
                            "project_id": row.project_id, "customer_id": row.customer_id,
                            "sub": row.project.name if getattr(row, "project", None) else "", "workspace": row.workspace})
    return results[:25]
