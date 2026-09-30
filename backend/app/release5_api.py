from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO
import secrets
import hashlib
import time
import smtplib
import re
from email.message import EmailMessage
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from PIL import Image, UnidentifiedImageError

from . import models as m
from .config import settings
from .db import get_db
from .deps import ensure_workspace, get_current_user, require_csrf, require_permission
from .media_storage import get_media_provider, safe_component
from .security import hash_password, token_hash
from .services import audit

router = APIRouter(prefix="/api/v1", tags=["Release 5 application isolation"])
APPLICATIONS = {"LIGHTING", "AUTOMATION"}
ADMIN_ROLES = {"ADMIN", "SUPER_ADMIN"}
SPEC_TYPES = {"text", "long_text", "number", "decimal", "boolean", "single_select", "multi_select", "date", "measurement"}


def application(value: str) -> str:
    value = value.upper().strip()
    if value not in APPLICATIONS: raise HTTPException(422, "Application must be LIGHTING or AUTOMATION")
    return value


def admin(user: m.User) -> None:
    if user.role not in ADMIN_ROLES: raise HTTPException(403, "Administrator access required")


def ensure_project(db: Session, user: m.User, project_id: str) -> None:
    if user.role in ADMIN_ROLES: return
    membership = db.scalar(select(m.ProjectUser.id).where(m.ProjectUser.project_id == project_id,
        m.ProjectUser.user_id == user.id, m.ProjectUser.status == "ACTIVE"))
    if not membership: raise HTTPException(403, "Project access denied")


class CategoryIn(BaseModel):
    workspace: str
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=160)
    parent_id: str | None = None
    short_description: str | None = Field(default=None, max_length=500)
    full_description: str | None = None
    image_alt_text: str | None = Field(default=None, max_length=255)
    catalogue_visible: bool = True
    customer_visible: bool = True
    search_visible: bool = True
    page_title: str | None = Field(default=None, max_length=180)
    meta_description: str | None = Field(default=None, max_length=320)
    status: str = "ACTIVE"
    sort_order: int = 0


class CategoryMove(BaseModel):
    id: str
    parent_id: str | None = None
    sort_order: int = Field(ge=0)


class CategoryReorderIn(BaseModel):
    workspace: str
    items: list[CategoryMove] = Field(min_length=1, max_length=500)


def category_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if not slug: raise HTTPException(422, "Category slug must contain letters or numbers")
    return slug


def safe_category_text(value: str | None) -> str | None:
    if not value: return None
    if re.search(r"<\s*(script|iframe|object|embed)|on\w+\s*=|javascript:", value, re.I):
        raise HTTPException(422, "Unsafe HTML is not allowed in category descriptions")
    return value.strip()


@router.get("/catalogue/categories/tree")
def category_tree(workspace: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    ws = application(workspace); ensure_workspace(user, ws)
    rows = db.scalars(select(m.Category).where(m.Category.workspace == ws).order_by(m.Category.sort_order, m.Category.name)).all()
    product_counts = dict(db.execute(select(m.Product.category_id, func.count(m.Product.id)).where(m.Product.workspace == ws).group_by(m.Product.category_id)).all())
    nodes = {x.id: {"id": x.id, "name": x.name, "slug": x.slug, "workspace": x.workspace, "parent_id": x.parent_id,
                    "short_description": x.short_description, "full_description": x.full_description,
                    "image_alt_text": x.image_alt_text, "catalogue_visible": x.catalogue_visible,
                    "customer_visible": x.customer_visible, "search_visible": x.search_visible,
                    "page_title": x.page_title, "meta_description": x.meta_description,
                    "status": x.status, "sort_order": x.sort_order, "product_count": product_counts.get(x.id, 0),
                    "created_at": x.created_at, "updated_at": x.updated_at, "children": []} for x in rows}
    roots = []
    for row in rows:
        (nodes[row.parent_id]["children"] if row.parent_id in nodes else roots).append(nodes[row.id])
    return roots


def check_parent(db: Session, workspace: str, parent_id: str | None, category_id: str | None = None):
    if not parent_id: return
    parent = db.get(m.Category, parent_id)
    if not parent or parent.workspace != workspace: raise HTTPException(422, "Parent category belongs to another application")
    seen = {category_id} if category_id else set()
    while parent:
        if parent.id in seen: raise HTTPException(422, "Circular category hierarchy is not allowed")
        seen.add(parent.id); parent = db.get(m.Category, parent.parent_id) if parent.parent_id else None


@router.post("/catalogue/categories", dependencies=[Depends(require_csrf)])
def create_category(body: CategoryIn, db: Session = Depends(get_db), user: m.User = Depends(require_permission("products.create"))):
    admin(user); ws = application(body.workspace); ensure_workspace(user, ws); check_parent(db, ws, body.parent_id)
    slug = category_slug(body.slug or body.name)
    duplicate = db.scalar(select(m.Category.id).where(m.Category.workspace == ws,
        m.Category.parent_id == body.parent_id, func.lower(m.Category.name) == body.name.strip().lower()))
    if duplicate: raise HTTPException(409, "Category name already exists at this level")
    slug_duplicate = db.scalar(select(m.Category.id).where(m.Category.workspace == ws,
        m.Category.parent_id == body.parent_id, func.lower(m.Category.slug) == slug.lower()))
    if slug_duplicate: raise HTTPException(409, "Category slug already exists at this level")
    row = m.Category(workspace=ws, name=" ".join(body.name.split()), slug=slug, parent_id=body.parent_id,
        short_description=safe_category_text(body.short_description), full_description=safe_category_text(body.full_description),
        image_alt_text=body.image_alt_text, catalogue_visible=body.catalogue_visible,
        customer_visible=body.customer_visible, search_visible=body.search_visible,
        page_title=body.page_title, meta_description=body.meta_description,
        status=body.status.upper(), sort_order=body.sort_order, created_by=user.id, updated_by=user.id)
    db.add(row); db.flush(); audit(db, user.id, "category.create", "category", row.id, {"application": ws}); db.commit()
    return {"id": row.id, "name": row.name, "slug": row.slug, "workspace": row.workspace, "parent_id": row.parent_id, "status": row.status}


@router.patch("/catalogue/categories/{category_id}", dependencies=[Depends(require_csrf)])
def update_category(category_id: str, body: CategoryIn, db: Session = Depends(get_db), user: m.User = Depends(require_permission("products.create"))):
    admin(user); row = db.get(m.Category, category_id)
    if not row: raise HTTPException(404, "Category not found")
    ws = application(body.workspace)
    if ws != row.workspace: raise HTTPException(422, "Category application cannot be changed")
    check_parent(db, ws, body.parent_id, row.id)
    name = " ".join(body.name.split()); slug = category_slug(body.slug or name)
    duplicate = db.scalar(select(m.Category.id).where(m.Category.workspace == ws, m.Category.parent_id == body.parent_id,
        m.Category.id != row.id, or_(func.lower(m.Category.name) == name.lower(), func.lower(m.Category.slug) == slug.lower())))
    if duplicate: raise HTTPException(409, "Category name or slug already exists at this level")
    row.name, row.slug, row.parent_id, row.status, row.sort_order = name, slug, body.parent_id, body.status.upper(), body.sort_order
    row.short_description, row.full_description = safe_category_text(body.short_description), safe_category_text(body.full_description)
    row.image_alt_text, row.catalogue_visible = body.image_alt_text, body.catalogue_visible
    row.customer_visible, row.search_visible = body.customer_visible, body.search_visible
    row.page_title, row.meta_description, row.updated_by = body.page_title, body.meta_description, user.id
    audit(db, user.id, "category.update", "category", row.id, {"application": ws}); db.commit(); return {"id": row.id, "status": row.status}


@router.put("/catalogue/categories/reorder", dependencies=[Depends(require_csrf)])
def reorder_categories(body: CategoryReorderIn, db: Session = Depends(get_db), user: m.User = Depends(require_permission("products.create"))):
    admin(user); ws = application(body.workspace); ensure_workspace(user, ws)
    ids = [item.id for item in body.items]
    if len(ids) != len(set(ids)): raise HTTPException(422, "Each category may appear only once in a reorder request")
    rows = {row.id: row for row in db.scalars(select(m.Category).where(m.Category.id.in_(ids))).all()}
    if len(rows) != len(ids) or any(row.workspace != ws for row in rows.values()):
        raise HTTPException(422, "A category is missing or belongs to another application")
    proposed = {item.id: item.parent_id for item in body.items}
    for item in body.items:
        check_parent(db, ws, item.parent_id, item.id)
        parent_id = item.parent_id
        seen = {item.id}
        while parent_id:
            if parent_id in seen: raise HTTPException(422, "Circular category hierarchy is not allowed")
            seen.add(parent_id)
            parent_id = proposed.get(parent_id, db.get(m.Category, parent_id).parent_id if db.get(m.Category, parent_id) else None)
    for item in body.items:
        row = rows[item.id]; row.parent_id = item.parent_id; row.sort_order = item.sort_order; row.updated_by = user.id
    audit(db, user.id, "category.reorder", "category", ws, {"application": ws, "count": len(body.items)})
    db.commit(); return {"updated": len(body.items)}


class SpecDefinitionIn(BaseModel):
    workspace: str
    category_id: str
    product_family_id: str | None = None
    spec_key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    label: str = Field(min_length=1, max_length=120)
    help_text: str | None = Field(default=None, max_length=500)
    data_type: str
    unit: str | None = None
    allowed_units: list[str] = []
    default_value: Any | None = None
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    precision: int | None = Field(default=None, ge=0, le=8)
    required: bool = False
    allowed_values: list[str] = []
    sort_order: int = 0
    show_in_catalogue: bool = True
    show_in_project_book: bool = True
    show_in_quotation_pdf: bool = False
    show_in_customer_portal: bool = True
    show_in_room_picker: bool = True
    show_in_exports: bool = True
    searchable: bool = False
    status: str = "ACTIVE"

    @field_validator("data_type")
    @classmethod
    def valid_type(cls, value: str):
        value = value.lower()
        if value not in SPEC_TYPES: raise ValueError("Unsupported specification data type")
        return value


@router.get("/specification-definitions")
def spec_definitions(workspace: str, category_id: str | None = None, family_id: str | None = None,
                     db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    ws = application(workspace); ensure_workspace(user, ws)
    stmt = select(m.ProductSpecDefinition).where(m.ProductSpecDefinition.workspace == ws, m.ProductSpecDefinition.status == "ACTIVE")
    if category_id: stmt = stmt.where(m.ProductSpecDefinition.category_id == category_id)
    rows = db.scalars(stmt.order_by(m.ProductSpecDefinition.sort_order, m.ProductSpecDefinition.label)).all()
    if family_id: rows = [x for x in rows if x.product_family_id in {None, family_id}]
    return [{"id": x.id, "workspace": x.workspace, "category_id": x.category_id, "product_family_id": x.product_family_id,
             "spec_key": x.spec_key, "label": x.label, "help_text": x.help_text, "data_type": x.data_type, "unit": x.unit,
             "allowed_units": x.allowed_units or [], "default_value": x.default_value,
             "min_value": float(x.min_value) if x.min_value is not None else None,
             "max_value": float(x.max_value) if x.max_value is not None else None, "precision": x.precision,
             "required": x.required, "allowed_values": x.allowed_values or [], "sort_order": x.sort_order,
             "show_in_catalogue": x.show_in_catalogue, "show_in_project_book": x.show_in_project_book,
             "show_in_quotation_pdf": x.show_in_quotation_pdf, "show_in_customer_portal": x.show_in_customer_portal,
             "show_in_room_picker": x.show_in_room_picker, "show_in_exports": x.show_in_exports, "searchable": x.searchable,
             "status": x.status} for x in rows]


@router.post("/specification-definitions", dependencies=[Depends(require_csrf)])
def add_spec_definition(body: SpecDefinitionIn, db: Session = Depends(get_db), user: m.User = Depends(require_permission("products.create"))):
    admin(user); ws = application(body.workspace); category = db.get(m.Category, body.category_id)
    if not category or category.workspace != ws: raise HTTPException(422, "Category belongs to another application")
    family = db.get(m.ProductFamily, body.product_family_id) if body.product_family_id else None
    if family and (family.workspace != ws or family.category_id != category.id): raise HTTPException(422, "Product family is outside the specification scope")
    duplicate = db.scalar(select(m.ProductSpecDefinition.id).where(
        m.ProductSpecDefinition.workspace == ws,
        m.ProductSpecDefinition.category_id == category.id,
        m.ProductSpecDefinition.product_family_id == body.product_family_id,
        m.ProductSpecDefinition.spec_key == body.spec_key,
    ))
    if duplicate: raise HTTPException(409, "Specification key already exists in this scope")
    if body.min_value is not None and body.max_value is not None and body.min_value > body.max_value:
        raise HTTPException(422, "Minimum value cannot exceed maximum value")
    values = body.model_dump(); values.update(workspace=ws, status=body.status.upper())
    row = m.ProductSpecDefinition(**values)
    db.add(row); db.flush(); audit(db, user.id, "specification.create", "product_spec_definition", row.id, {"application": ws}); db.commit()
    return {"id": row.id, **body.model_dump(), "workspace": ws}


def normalize_spec(definition: m.ProductSpecDefinition, raw: Any) -> dict:
    kind = definition.data_type.lower()
    if raw in (None, "", []):
        if definition.default_value is not None: raw = definition.default_value.get("value") if isinstance(definition.default_value, dict) else definition.default_value
    if raw in (None, "", []):
        if definition.required: raise HTTPException(422, f"{definition.label} is required")
        return {"value": None, "unit": definition.unit}
    try:
        if kind == "number": value = int(raw)
        elif kind == "decimal": value = str(Decimal(str(raw)))
        elif kind == "boolean": value = raw if isinstance(raw, bool) else str(raw).lower() in {"true", "1", "yes"}
        elif kind == "multi_select": value = list(raw) if isinstance(raw, list) else [str(raw)]
        elif kind == "measurement":
            value = ({"amount": str(Decimal(str(raw.get("amount")))), "unit": raw.get("unit") or definition.unit}
                     if isinstance(raw, dict) else {"amount": str(Decimal(str(raw))), "unit": definition.unit})
        elif kind == "date": value = date.fromisoformat(str(raw)).isoformat()
        else: value = str(raw)
    except Exception as exc: raise HTTPException(422, f"Invalid value for {definition.label}") from exc
    if kind in {"number", "decimal"}:
        numeric = Decimal(str(value))
        if definition.min_value is not None and numeric < definition.min_value: raise HTTPException(422, f"{definition.label} is below the minimum")
        if definition.max_value is not None and numeric > definition.max_value: raise HTTPException(422, f"{definition.label} exceeds the maximum")
        if kind == "decimal" and definition.precision is not None:
            value = str(numeric.quantize(Decimal(1).scaleb(-definition.precision)))
    if kind == "measurement":
        units = set(definition.allowed_units or [])
        if units and value.get("unit") not in units: raise HTTPException(422, f"{definition.label} uses an unsupported unit")
        numeric = Decimal(value["amount"])
        if definition.min_value is not None and numeric < definition.min_value: raise HTTPException(422, f"{definition.label} is below the minimum")
        if definition.max_value is not None and numeric > definition.max_value: raise HTTPException(422, f"{definition.label} exceeds the maximum")
        if definition.precision is not None:
            value["amount"] = str(numeric.quantize(Decimal(1).scaleb(-definition.precision)))
    allowed = set(definition.allowed_values or [])
    check = value if isinstance(value, list) else ([] if isinstance(value, dict) else [value])
    if allowed and any(str(x) not in allowed for x in check): raise HTTPException(422, f"{definition.label} contains an unsupported value")
    return {"value": value, "unit": definition.unit, "type": kind}


class SpecValuesIn(BaseModel):
    values: dict[str, Any]


@router.put("/product-variants/{product_id}/specifications", dependencies=[Depends(require_csrf)])
def set_spec_values(product_id: str, body: SpecValuesIn, db: Session = Depends(get_db), user: m.User = Depends(require_permission("products.create"))):
    admin(user); product = db.get(m.Product, product_id)
    if not product: raise HTTPException(404, "Product variant not found")
    ensure_workspace(user, product.workspace)
    definitions = db.scalars(select(m.ProductSpecDefinition).where(m.ProductSpecDefinition.workspace == product.workspace,
        m.ProductSpecDefinition.category_id == product.category_id, m.ProductSpecDefinition.status == "ACTIVE").order_by(m.ProductSpecDefinition.sort_order)).all()
    definitions = [x for x in definitions if x.product_family_id in {None, product.family_id}]
    known = {x.spec_key: x for x in definitions}
    unknown = set(body.values) - set(known)
    if unknown: raise HTTPException(422, f"Unknown specifications: {', '.join(sorted(unknown))}")
    normalized = {key: normalize_spec(definition, body.values.get(key)) for key, definition in known.items() if key in body.values or definition.required}
    for key, value in normalized.items():
        definition = known[key]
        row = db.scalar(select(m.ProductSpecValue).where(m.ProductSpecValue.product_id == product.id, m.ProductSpecValue.definition_id == definition.id))
        if row: row.value = value
        else: db.add(m.ProductSpecValue(product_id=product.id, definition_id=definition.id, value=value))
    product.specs = {key: value["value"] for key, value in normalized.items() if value["value"] is not None}
    audit(db, user.id, "product.specifications.update", "product", product.id, {"application": product.workspace}); db.commit()
    return {"product_id": product.id, "values": normalized}


class InvitationIn(BaseModel):
    contact_name: str = Field(min_length=1)
    email: EmailStr
    phone: str | None = None
    customer_role: str = "CUSTOMER"
    application_access: list[str] = Field(min_length=1)
    send_invitation: bool = True
    invitation_message: str | None = Field(default=None, max_length=1000)
    building_id: str | None = None
    confirm_existing_user: bool = False

    @field_validator("customer_role")
    @classmethod
    def safe_customer_role(cls, value: str):
        value = "_".join(value.upper().replace("-", " ").split())
        if value not in {"CUSTOMER", "PROJECT_USER"}:
            raise ValueError("Invitation role must be CUSTOMER or PROJECT_USER")
        return value


def send_invitation_email(email: str, name: str, link: str, message: str | None) -> bool:
    if not settings.smtp_host: return False
    mail = EmailMessage(); mail["Subject"] = "Activate your AlphaNumeric customer account"; mail["From"] = settings.smtp_from; mail["To"] = email
    mail.set_content(f"Hello {name},\n\n{message or 'Your customer portal access is ready.'}\n\nActivate your account: {link}\n\nThis link expires in {settings.invitation_expiry_hours} hours.")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_use_tls: smtp.starttls()
        if settings.smtp_username: smtp.login(settings.smtp_username, settings.smtp_password or "")
        smtp.send_message(mail)
    return True


@router.post("/inquiries/{inquiry_id}/customer-invitations", dependencies=[Depends(require_csrf)])
def create_invitation(inquiry_id: str, body: InvitationIn, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin(user); inquiry = db.get(m.Inquiry, inquiry_id)
    if not inquiry: raise HTTPException(404, "Inquiry not found")
    allowed = sorted({application(x) for x in body.application_access})
    if inquiry.workspace not in allowed: raise HTTPException(422, "Invitation access must include the inquiry application")
    normalized = body.email.strip().lower()
    account = db.scalar(select(m.User).where(func.lower(m.User.email) == normalized)); reused = account is not None
    if reused and not body.confirm_existing_user:
        raise HTTPException(409, "An account already uses this email. Confirm the existing account before granting access.")
    if not account:
        account = m.User(name=body.contact_name.strip(), email=normalized, phone=body.phone,
            password_hash=hash_password(secrets.token_urlsafe(48)), role="USER", status="PENDING", workspaces=allowed)
        db.add(account); db.flush()
    else:
        account.workspaces = sorted(set((account.workspaces or []) + allowed)); account.phone = body.phone or account.phone
    if body.building_id:
        building = db.get(m.Building, body.building_id)
        if not building or building.project_id != inquiry.project_id: raise HTTPException(422, "Building is outside the inquiry project")
    membership = db.scalar(select(m.ProjectUser).where(m.ProjectUser.project_id == inquiry.project_id, m.ProjectUser.user_id == account.id))
    if not membership:
        db.add(m.ProjectUser(project_id=inquiry.project_id, user_id=account.id, building_id=body.building_id, role=body.customer_role,
            permissions=["commercial.documents.view", "catalogue.view"], status="ACTIVE", created_by=user.id))
    elif body.building_id and membership.building_id and membership.building_id != body.building_id:
        raise HTTPException(409, "This account already has access scoped to another building in the project")
    raw = secrets.token_urlsafe(48); now = datetime.now(timezone.utc)
    already_active = reused and account.status == "ACTIVE"
    row = m.CustomerInvitation(user_id=account.id, inquiry_id=inquiry.id, project_id=inquiry.project_id, building_id=body.building_id,
        normalized_email=normalized, token_hash=token_hash(raw), workspace_scope=allowed, role=body.customer_role,
        message=body.invitation_message, expires_at=now + timedelta(hours=settings.invitation_expiry_hours),
        status="ACCEPTED" if already_active else "PENDING", consumed_at=now if already_active else None,
        created_by=user.id, last_sent_at=now)
    db.add(row); db.flush(); link = f"{settings.public_app_url.rstrip('/')}/activate?token={raw}"
    delivered, warning = False, None
    if already_active:
        warning = "Existing active account was granted project access; no password-reset invitation was sent."
    elif body.send_invitation:
        try: delivered = send_invitation_email(normalized, account.name, link, body.invitation_message)
        except Exception: warning = "Inquiry saved, but invitation email delivery failed. You can resend it."
    if not delivered and not warning: warning = "SMTP is not configured. Copy this activation link now; it will not be shown again."
    audit(db, user.id, "invitation.create", "customer_invitation", row.id, {"application_access": allowed, "delivered": delivered})
    db.commit()
    return {"id": row.id, "user_reused": reused, "email_delivered": delivered,
            "warning": warning, "activation_link": None if delivered or already_active else link, "expires_at": row.expires_at.isoformat()}


class ActivationIn(BaseModel):
    token: str = Field(min_length=32)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str):
        if not (any(x.isupper() for x in value) and any(x.islower() for x in value) and any(x.isdigit() for x in value) and any(not x.isalnum() for x in value)):
            raise ValueError("Password must include upper, lower, number, and symbol")
        return value


@router.post("/auth/activate-invitation")
def activate_invitation(body: ActivationIn, db: Session = Depends(get_db)):
    digest = token_hash(body.token); now = datetime.now(timezone.utc)
    throttle = db.scalar(select(m.InvitationActivationAttempt).where(
        m.InvitationActivationAttempt.token_hash == digest).with_for_update())
    if throttle:
        started = throttle.window_started_at if throttle.window_started_at.tzinfo else throttle.window_started_at.replace(tzinfo=timezone.utc)
        if now - started >= timedelta(minutes=5):
            throttle.attempts = 0; throttle.window_started_at = now
        if throttle.attempts >= 10: raise HTTPException(429, "Too many activation attempts; try again later")
        throttle.attempts += 1; throttle.updated_at = now
    else:
        throttle = m.InvitationActivationAttempt(token_hash=digest, attempts=1, window_started_at=now, updated_at=now)
        db.add(throttle)
    db.commit()
    row = db.scalar(select(m.CustomerInvitation).where(m.CustomerInvitation.token_hash == digest).with_for_update())
    if not row: raise HTTPException(400, "Invalid invitation")
    if row.status != "PENDING" or row.consumed_at or row.revoked_at: raise HTTPException(409, "Invitation is no longer usable")
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    if expires <= now:
        row.status = "EXPIRED"; audit(db, None, "invitation.expire", "customer_invitation", row.id); db.commit(); raise HTTPException(410, "Invitation expired")
    account = db.get(m.User, row.user_id); account.password_hash = hash_password(body.password); account.status = "ACTIVE"; account.must_change_password = False
    row.status = "ACCEPTED"; row.consumed_at = now; audit(db, account.id, "invitation.accept", "customer_invitation", row.id); db.commit()
    db.delete(throttle); db.commit()
    return {"status": "accepted"}


@router.post("/customer-invitations/{invitation_id}/revoke", dependencies=[Depends(require_csrf)])
def revoke_invitation(invitation_id: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin(user); row = db.get(m.CustomerInvitation, invitation_id)
    if not row: raise HTTPException(404, "Invitation not found")
    if row.status != "PENDING": raise HTTPException(409, "Only pending invitations can be revoked")
    row.status = "REVOKED"; row.revoked_at = datetime.now(timezone.utc); audit(db, user.id, "invitation.revoke", "customer_invitation", row.id); db.commit(); return {"status": row.status}


@router.post("/customer-invitations/{invitation_id}/resend", dependencies=[Depends(require_csrf)])
def resend_invitation(invitation_id: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    """Rotate the single-use token and retry delivery without exposing it in logs."""
    admin(user); row = db.get(m.CustomerInvitation, invitation_id)
    if not row: raise HTTPException(404, "Invitation not found")
    if row.status not in {"PENDING", "EXPIRED"} or row.consumed_at or row.revoked_at:
        raise HTTPException(409, "Invitation cannot be resent")
    account = db.get(m.User, row.user_id)
    if not account: raise HTTPException(409, "Invitation account no longer exists")
    raw = secrets.token_urlsafe(48); now = datetime.now(timezone.utc)
    row.token_hash = token_hash(raw); row.status = "PENDING"; row.expires_at = now + timedelta(hours=settings.invitation_expiry_hours)
    row.last_sent_at = now; link = f"{settings.public_app_url.rstrip('/')}/activate?token={raw}"
    delivered, warning = False, None
    try: delivered = send_invitation_email(row.normalized_email, account.name, link, row.message)
    except Exception: warning = "Invitation email delivery failed. Copy the new activation link now."
    if not delivered and not warning: warning = "SMTP is not configured. Copy the new activation link now; it will not be shown again."
    audit(db, user.id, "invitation.resend", "customer_invitation", row.id, {"delivered": delivered})
    db.commit()
    return {"id": row.id, "email_delivered": delivered, "warning": warning,
            "activation_link": None if delivered else link, "expires_at": row.expires_at.isoformat()}


def validate_image(data: bytes, supplied_type: str | None) -> tuple[str, int, int, str]:
    if len(data) > settings.media_max_bytes: raise HTTPException(413, "Image exceeds the configured size limit")
    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
        with Image.open(BytesIO(data)) as image:
            fmt, width, height = image.format, image.width, image.height
    except (UnidentifiedImageError, OSError) as exc: raise HTTPException(422, "File is not a valid image") from exc
    types = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
    mime = types.get(fmt or "")
    if not mime or supplied_type not in {mime, "application/octet-stream", None, ""}: raise HTTPException(422, "Only genuine JPEG, PNG, and WebP images are allowed")
    return mime, width, height, fmt or ""


@router.post("/product-variants/{product_id}/images", dependencies=[Depends(require_csrf)])
async def upload_product_image(product_id: str, file: UploadFile = File(...), alt_text: str = Form(""), caption: str | None = Form(None),
                               db: Session = Depends(get_db), user: m.User = Depends(require_permission("products.create"))):
    admin(user); product = db.get(m.Product, product_id)
    if not product: raise HTTPException(404, "Product variant not found")
    ensure_workspace(user, product.workspace)
    count = db.scalar(select(func.count()).select_from(m.ProductMedia).where(m.ProductMedia.product_id == product.id, m.ProductMedia.archived_at.is_(None))) or 0
    if count >= settings.media_max_files_per_product: raise HTTPException(409, "Product image limit reached")
    data = await file.read(settings.media_max_bytes + 1); mime, width, height, fmt = validate_image(data, file.content_type)
    checksum = hashlib.sha256(data).hexdigest()
    duplicate = db.scalar(select(m.ProductMedia.id).where(m.ProductMedia.product_id == product.id,
        m.ProductMedia.checksum_sha256 == checksum, m.ProductMedia.archived_at.is_(None), m.ProductMedia.upload_status == "READY"))
    if duplicate: raise HTTPException(409, "This exact image is already attached to the product")
    provider = get_media_provider(); folder = f"{safe_component(product.name)}_{product.id}"
    ext = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[fmt]
    stored = None
    last_error = None
    for attempt in range(1, 4):
        try:
            stored = provider.upload(data, filename=f"image-{count + 1}.{ext}", workspace=product.workspace, product_folder=folder, mime_type=mime)
            break
        except Exception as exc:
            last_error = exc
            if attempt < 3: time.sleep(0.2 * (2 ** (attempt - 1)))
    if stored is None: raise HTTPException(503, "Image storage is temporarily unavailable; retry the upload") from last_error
    try:
        row = m.ProductMedia(product_family_id=product.family_id, product_id=product.id, storage_key=stored.storage_key,
            workspace=product.workspace, storage_provider=settings.media_storage_provider.lower(), provider_file_id=stored.file_id,
            provider_parent_id=stored.parent_id, original_filename=safe_component(file.filename or "image"), stored_filename=f"image-{count + 1}.{ext}",
            media_type="image", mime_type=mime, file_size=stored.size, checksum_sha256=stored.checksum,
            alt_text=alt_text.strip() or product.name, caption=caption, sort_order=count, is_primary=count == 0,
            width=width, height=height, upload_status="READY", upload_attempts=attempt, uploaded_by=user.id)
        db.add(row); db.flush(); audit(db, user.id, "product.image.upload", "product_media", row.id, {"application": product.workspace}); db.commit()
    except Exception:
        db.rollback(); provider.delete(stored.file_id, stored.storage_key); raise
    return {"id": row.id, "url": f"/api/v1/product-media/{row.id}/secure-file", "is_primary": row.is_primary, "upload_status": row.upload_status}


@router.get("/product-media/{media_id}/secure-file")
def secure_media(media_id: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    row = db.get(m.ProductMedia, media_id)
    if not row or row.archived_at or row.upload_status != "READY": raise HTTPException(404, "Image unavailable")
    ensure_workspace(user, row.workspace)
    if user.role not in ADMIN_ROLES:
        product_ids = select(m.Product.id).where(
            m.Product.id == row.product_id if row.product_id else m.Product.family_id == row.product_family_id
        )
        inquiry_use = db.scalar(select(m.RoomRequirement.id).join(m.Inquiry).join(
            m.Room, m.Room.id == m.RoomRequirement.room_id
        ).join(m.Floor, m.Floor.id == m.Room.floor_id).join(
            m.ProjectUser, m.ProjectUser.project_id == m.Inquiry.project_id
        ).where(m.RoomRequirement.product_id.in_(product_ids), m.ProjectUser.user_id == user.id,
                m.ProjectUser.status == "ACTIVE",
                or_(m.ProjectUser.building_id.is_(None), m.ProjectUser.building_id == m.Floor.building_id)).limit(1))
        project_use = db.scalar(select(m.RoomProduct.id).join(
            m.ProjectUser, m.ProjectUser.project_id == m.RoomProduct.project_id
        ).where(m.RoomProduct.product_id.in_(product_ids), m.ProjectUser.user_id == user.id,
                m.ProjectUser.status == "ACTIVE",
                or_(m.ProjectUser.building_id.is_(None), m.ProjectUser.building_id == m.RoomProduct.building_id)).limit(1))
        if not (inquiry_use or project_use): raise HTTPException(403, "Media access denied")
    try: stream = get_media_provider(row.storage_provider).open(row.provider_file_id or row.storage_key, row.storage_key)
    except FileNotFoundError: raise HTTPException(404, "Stored image is missing")
    headers = {
        "Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff",
        "Content-Disposition": f'inline; filename="{safe_component(row.stored_filename or "product-image")}"',
    }
    if row.file_size is not None: headers["Content-Length"] = str(row.file_size)
    if row.checksum_sha256: headers["ETag"] = f'"{row.checksum_sha256}"'
    return StreamingResponse(stream, media_type=row.mime_type or "application/octet-stream", headers=headers)


@router.get("/media-storage/quota")
def media_quota(user: m.User = Depends(get_current_user)):
    admin(user); value = get_media_provider().quota(); value["warning"] = bool(value.get("percent") and value["percent"] >= settings.google_drive_quota_warning_percent); return value
