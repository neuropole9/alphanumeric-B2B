from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models as m
from .db import get_db
from .deps import get_current_user, has_permission, require_csrf, require_permission
from .services import audit, next_number

router = APIRouter(prefix="/api/v1")
ADMIN_ROLES = {"ADMIN", "SUPER_ADMIN"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def project_access(db: Session, user: m.User, project_id: str | None, permission: str | None = None) -> None:
    if not project_id or user.role in ADMIN_ROLES:
        return
    assignment = db.scalar(select(m.ProjectUser).where(
        m.ProjectUser.project_id == project_id, m.ProjectUser.user_id == user.id,
        m.ProjectUser.status == "ACTIVE"))
    if not assignment:
        raise HTTPException(403, "Project access denied")
    if permission and "*" not in (assignment.permissions or []) and permission not in (assignment.permissions or []):
        raise HTTPException(403, "Project permission denied")


def admin_or(user: m.User, permission: str) -> None:
    if user.role not in ADMIN_ROLES and not has_permission(user, permission):
        raise HTTPException(403, "Permission denied")


def safe_external_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("Only absolute HTTP(S) URLs without embedded credentials are allowed")
    return value


class PartnerIn(BaseModel):
    business_name: str = Field(min_length=2, max_length=180)
    legal_name: str | None = Field(None, max_length=180)
    partner_type: str = "OTHER"
    mobile: str = Field(min_length=6, max_length=60)
    email: str = Field(min_length=5, max_length=255)
    tax_id: str | None = Field(None, max_length=40)
    address: str = Field(min_length=3, max_length=3000)
    billing_address: str | None = Field(None, max_length=3000)
    shipping_address: str | None = Field(None, max_length=3000)
    territory: str | None = Field(None, max_length=100)
    zone: str | None = Field(None, max_length=100)
    credit_terms_days: int = Field(0, ge=0, le=365)
    credit_limit: Decimal = Field(Decimal("0"), ge=0)
    notes: str | None = Field(None, max_length=5000)

    @field_validator("partner_type")
    @classmethod
    def valid_type(cls, value: str) -> str:
        value = value.upper().replace(" ", "_")
        allowed = {"DEALER", "DISTRIBUTOR", "SYSTEM_INTEGRATOR", "ARCHITECT_CONSULTANT", "CONTRACTOR", "RESELLER", "OTHER"}
        if value not in allowed:
            raise ValueError("Unsupported partner type")
        return value


def partner_json(row: m.Partner) -> dict:
    return {key: getattr(row, key) for key in (
        "id", "business_name", "legal_name", "partner_type", "mobile", "email", "tax_id",
        "address", "billing_address", "shipping_address", "territory", "zone", "status",
        "credit_terms_days", "credit_limit", "notes")}


@router.get("/partners")
def list_partners(q: str | None = None, status: str | None = None, db: Session = Depends(get_db),
                  user: m.User = Depends(get_current_user)):
    admin_or(user, "partners.view")
    stmt = select(m.Partner)
    if user.partner_id:
        stmt = stmt.where(m.Partner.id == user.partner_id)
    if q:
        term = f"%{q.strip()}%"
        stmt = stmt.where(func.lower(m.Partner.business_name).like(func.lower(term)))
    if status:
        stmt = stmt.where(m.Partner.status == status.upper())
    return [partner_json(x) for x in db.scalars(stmt.order_by(m.Partner.business_name)).all()]


@router.post("/partners", dependencies=[Depends(require_csrf)])
def create_partner(body: PartnerIn, db: Session = Depends(get_db),
                   user: m.User = Depends(require_permission("partners.manage"))):
    normalized = " ".join(body.business_name.lower().split())
    duplicate = db.scalar(select(m.Partner).where(
        (func.lower(func.trim(m.Partner.business_name)) == normalized) |
        (func.lower(m.Partner.email) == body.email.lower()) |
        (m.Partner.mobile == body.mobile)))
    if duplicate:
        raise HTTPException(409, "A partner with the same name, email or phone already exists")
    if body.tax_id and db.scalar(select(m.Partner.id).where(func.lower(m.Partner.tax_id) == body.tax_id.lower())):
        raise HTTPException(409, "Tax ID already exists")
    data = body.model_dump()
    data.update(email=body.email.lower(), tax_id=(body.tax_id or None), status="PENDING")
    row = m.Partner(**data)
    db.add(row); db.flush()
    audit(db, user.id, "partner.created", "partner", row.id, {"type": row.partner_type})
    db.commit()
    return partner_json(row)


class StatusBody(BaseModel):
    status: str
    reason: str | None = Field(None, max_length=500)
    notes: str | None = Field(None, max_length=5000)


@router.post("/partners/{partner_id}/status", dependencies=[Depends(require_csrf)])
def partner_status(partner_id: str, body: StatusBody, db: Session = Depends(get_db),
                   user: m.User = Depends(require_permission("partners.manage"))):
    row = db.get(m.Partner, partner_id)
    if not row:
        raise HTTPException(404, "Partner not found")
    target = body.status.upper()
    allowed = {"PENDING": {"ACTIVE", "REJECTED"}, "ACTIVE": {"INACTIVE"}, "INACTIVE": {"ACTIVE"}, "REJECTED": {"PENDING"}}
    if target not in allowed.get(row.status, set()):
        raise HTTPException(409, f"Invalid partner transition {row.status} -> {target}")
    old = row.status; row.status = target
    audit(db, user.id, "partner.status_changed", "partner", row.id, {"from": old, "to": target, "reason": body.reason})
    db.commit()
    return partner_json(row)


INQUIRY_TRANSITIONS = {
    "DRAFT": {"SUBMITTED", "CANCELLED"}, "SUBMITTED": {"UNDER_REVIEW", "CANCELLED"},
    "IN_PROCESS": {"UNDER_REVIEW", "DESIGN_REQUIRED", "BOQ_READY", "CANCELLED"},
    "UNDER_REVIEW": {"DESIGN_REQUIRED", "BOQ_READY", "LOST", "CANCELLED"},
    "DESIGN_REQUIRED": {"DESIGN_IN_PROGRESS", "CANCELLED"},
    "DESIGN_IN_PROGRESS": {"BOQ_READY", "DESIGN_REQUIRED", "CANCELLED"},
    "BOQ_READY": {"QUOTATION_SENT", "DESIGN_IN_PROGRESS"},
    "QUOTED": {"NEGOTIATION", "WON", "LOST", "CANCELLED"},
    "QUOTATION_SENT": {"NEGOTIATION", "WON", "LOST", "CANCELLED"},
    "NEGOTIATION": {"QUOTATION_SENT", "WON", "LOST", "CANCELLED"},
    "WON": set(), "LOST": set(), "CANCELLED": set(), "COMPLETED": set(),
}


@router.post("/inquiries/{inquiry_id}/stage", dependencies=[Depends(require_csrf)])
def transition_inquiry(inquiry_id: str, body: StatusBody, db: Session = Depends(get_db),
                       user: m.User = Depends(get_current_user)):
    admin_or(user, "pipeline.manage")
    row = db.get(m.Inquiry, inquiry_id)
    if not row:
        raise HTTPException(404, "Inquiry not found")
    project_access(db, user, row.project_id, "inquiries.edit")
    target = body.status.upper().replace(" ", "_")
    if target not in INQUIRY_TRANSITIONS.get(row.status, set()):
        raise HTTPException(409, f"Invalid inquiry transition {row.status} -> {target}")
    if target in {"LOST", "CANCELLED"} and not body.reason:
        raise HTTPException(422, "A reason is required")
    old = row.status; row.status = target
    history = m.InquiryStageHistory(inquiry_id=row.id, from_stage=old, to_stage=target,
                                    reason=body.reason, notes=body.notes, actor_id=user.id)
    db.add(history)
    audit(db, user.id, "inquiry.stage_changed", "inquiry", row.id, {"from": old, "to": target, "reason": body.reason})
    db.commit()
    return {"id": row.id, "status": row.status, "history_id": history.id}


@router.get("/inquiries/{inquiry_id}/stage-history")
def inquiry_stage_history(inquiry_id: str, db: Session = Depends(get_db),
                          user: m.User = Depends(get_current_user)):
    row = db.get(m.Inquiry, inquiry_id)
    if not row: raise HTTPException(404, "Inquiry not found")
    project_access(db, user, row.project_id)
    items = db.scalars(select(m.InquiryStageHistory).where(
        m.InquiryStageHistory.inquiry_id == inquiry_id).order_by(m.InquiryStageHistory.created_at)).all()
    return [{"id": x.id, "from": x.from_stage, "to": x.to_stage, "reason": x.reason,
             "notes": x.notes, "actor_id": x.actor_id, "created_at": x.created_at} for x in items]


class WarehouseIn(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=140)
    address: str | None = Field(None, max_length=3000)
    partner_id: str | None = None
    allow_negative: bool = False


@router.get("/warehouses")
def warehouses(db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_or(user, "inventory.view")
    stmt = select(m.Warehouse)
    if user.partner_id: stmt = stmt.where(m.Warehouse.partner_id == user.partner_id)
    return [{"id": x.id, "code": x.code, "name": x.name, "partner_id": x.partner_id,
             "address": x.address, "status": x.status, "allow_negative": x.allow_negative} for x in db.scalars(stmt).all()]


@router.post("/warehouses", dependencies=[Depends(require_csrf)])
def create_warehouse(body: WarehouseIn, db: Session = Depends(get_db),
                     user: m.User = Depends(require_permission("inventory.receive"))):
    if user.partner_id and body.partner_id != user.partner_id:
        raise HTTPException(403, "Partner scope denied")
    data = body.model_dump(); data["code"] = body.code.upper()
    row = m.Warehouse(**data)
    db.add(row)
    try: db.flush()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "Warehouse code already exists in this scope")
    audit(db, user.id, "warehouse.created", "warehouse", row.id)
    db.commit()
    return {"id": row.id, "code": row.code, "name": row.name}


class StockMovementIn(BaseModel):
    warehouse_id: str
    product_id: str
    movement_type: str
    quantity: Decimal = Field(gt=0)
    direction: str
    reference_type: str | None = None
    reference_id: str | None = None
    idempotency_key: str | None = Field(None, max_length=120)
    notes: str | None = Field(None, max_length=2000)

    @field_validator("direction")
    @classmethod
    def direction_value(cls, value: str) -> str:
        value = value.upper()
        if value not in {"IN", "OUT"}: raise ValueError("Direction must be IN or OUT")
        return value


def stock_balance(db: Session, warehouse_id: str, product_id: str) -> Decimal:
    incoming = db.scalar(select(func.coalesce(func.sum(m.StockLedger.quantity), 0)).where(
        m.StockLedger.warehouse_id == warehouse_id, m.StockLedger.product_id == product_id,
        m.StockLedger.direction == "IN")) or 0
    outgoing = db.scalar(select(func.coalesce(func.sum(m.StockLedger.quantity), 0)).where(
        m.StockLedger.warehouse_id == warehouse_id, m.StockLedger.product_id == product_id,
        m.StockLedger.direction == "OUT")) or 0
    return Decimal(incoming) - Decimal(outgoing)


@router.post("/stock/movements", dependencies=[Depends(require_csrf)])
def stock_movement(body: StockMovementIn, db: Session = Depends(get_db),
                   user: m.User = Depends(get_current_user)):
    needed = "inventory.receive" if body.direction == "IN" else "inventory.transfer"
    admin_or(user, needed)
    warehouse = db.scalar(select(m.Warehouse).where(m.Warehouse.id == body.warehouse_id).with_for_update())
    product = db.get(m.Product, body.product_id)
    if not warehouse or not product: raise HTTPException(404, "Warehouse or product not found")
    if user.partner_id and warehouse.partner_id != user.partner_id: raise HTTPException(403, "Partner scope denied")
    if body.idempotency_key:
        existing = db.scalar(select(m.StockLedger).where(m.StockLedger.idempotency_key == body.idempotency_key))
        if existing: return {"id": existing.id, "balance": float(stock_balance(db, body.warehouse_id, body.product_id)), "duplicate": True}
    before = stock_balance(db, body.warehouse_id, body.product_id)
    after = before + body.quantity if body.direction == "IN" else before - body.quantity
    if after < 0 and not warehouse.allow_negative:
        raise HTTPException(409, f"Insufficient stock; available {before}")
    data = body.model_dump(); data["movement_type"] = body.movement_type.upper()
    row = m.StockLedger(**data, actor_id=user.id)
    db.add(row); db.flush()
    audit(db, user.id, "stock.movement_recorded", "stock_ledger", row.id,
          {"before": str(before), "after": str(after), "type": row.movement_type})
    db.commit()
    return {"id": row.id, "balance": float(after), "duplicate": False}


@router.get("/stock/balances")
def stock_balances(warehouse_id: str | None = None, q: str | None = None, db: Session = Depends(get_db),
                   user: m.User = Depends(get_current_user)):
    admin_or(user, "inventory.view")
    warehouses_stmt = select(m.Warehouse)
    if warehouse_id: warehouses_stmt = warehouses_stmt.where(m.Warehouse.id == warehouse_id)
    if user.partner_id: warehouses_stmt = warehouses_stmt.where(m.Warehouse.partner_id == user.partner_id)
    locations = db.scalars(warehouses_stmt).all()
    products = db.scalars(select(m.Product).where(
        m.Product.name.ilike(f"%{q}%") if q else m.Product.id.is_not(None)).order_by(m.Product.name).limit(250)).all()
    return [{"warehouse_id": w.id, "warehouse": w.name, "product_id": p.id, "sku": p.sku,
             "product": p.name, "balance": float(stock_balance(db, w.id, p.id)),
             "low_stock": stock_balance(db, w.id, p.id) <= Decimal(p.reorder_level or 0)}
            for w in locations for p in products if stock_balance(db, w.id, p.id) != 0]


class DispatchLineIn(BaseModel):
    order_item_id: str
    quantity: Decimal = Field(gt=0)


class DispatchIn(BaseModel):
    order_id: str
    warehouse_id: str | None = None
    delivery_address: str = Field(min_length=3, max_length=3000)
    transporter: str | None = Field(None, max_length=140)
    vehicle_number: str | None = Field(None, max_length=80)
    tracking_number: str | None = Field(None, max_length=120)
    expected_delivery: date | None = None
    items: list[DispatchLineIn] = Field(min_length=1)


def dispatch_json(db: Session, row: m.Dispatch) -> dict:
    lines = db.scalars(select(m.DispatchItem).where(m.DispatchItem.dispatch_id == row.id)).all()
    return {"id": row.id, "number": row.number, "order_id": row.order_id, "warehouse_id": row.warehouse_id,
            "status": row.status, "delivery_address": row.delivery_address, "transporter": row.transporter,
            "tracking_number": row.tracking_number, "expected_delivery": row.expected_delivery,
            "dispatched_at": row.dispatched_at, "delivered_at": row.delivered_at,
            "items": [{"order_item_id": x.order_item_id, "quantity": float(x.quantity)} for x in lines]}


@router.get("/dispatches")
def list_dispatches(db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_or(user, "dispatch.manage")
    rows = db.scalars(select(m.Dispatch).order_by(desc(m.Dispatch.created_at))).all()
    if user.role not in ADMIN_ROLES:
        allowed = select(m.ProjectUser.project_id).where(m.ProjectUser.user_id == user.id, m.ProjectUser.status == "ACTIVE")
        rows = [x for x in rows if x.order.project_id in set(db.scalars(allowed).all())]
    return [dispatch_json(db, x) for x in rows]


@router.post("/dispatches", dependencies=[Depends(require_csrf)])
def create_dispatch(body: DispatchIn, db: Session = Depends(get_db),
                    user: m.User = Depends(require_permission("dispatch.manage"))):
    order = db.scalar(select(m.Order).where(m.Order.id == body.order_id).with_for_update())
    if not order: raise HTTPException(404, "Order not found")
    project_access(db, user, order.project_id)
    if order.status in {"CANCELLED", "DELIVERED", "COMPLETED"}: raise HTTPException(409, "Order cannot be dispatched")
    row = m.Dispatch(number=next_number(db, "dispatch", "DSP"), order_id=order.id,
                     warehouse_id=body.warehouse_id, delivery_address=body.delivery_address,
                     transporter=body.transporter, vehicle_number=body.vehicle_number,
                     tracking_number=body.tracking_number, expected_delivery=body.expected_delivery,
                     created_by=user.id)
    db.add(row); db.flush()
    for requested in body.items:
        item = db.get(m.OrderItem, requested.order_item_id)
        if not item or item.order_id != order.id: raise HTTPException(422, "Dispatch line does not belong to this order")
        already = db.scalar(select(func.coalesce(func.sum(m.DispatchItem.quantity), 0)).join(
            m.Dispatch, m.Dispatch.id == m.DispatchItem.dispatch_id).where(
            m.DispatchItem.order_item_id == item.id, m.Dispatch.status != "CANCELLED")) or 0
        remaining = Decimal(item.qty) - Decimal(already)
        if requested.quantity > remaining:
            raise HTTPException(409, f"Dispatch quantity exceeds remaining quantity for {item.sku}; remaining {remaining}")
        db.add(m.DispatchItem(dispatch_id=row.id, order_item_id=item.id, quantity=requested.quantity))
    audit(db, user.id, "dispatch.created", "dispatch", row.id, {"order_id": order.id})
    db.commit()
    return dispatch_json(db, row)


@router.post("/dispatches/{dispatch_id}/status", dependencies=[Depends(require_csrf)])
def dispatch_status(dispatch_id: str, body: StatusBody, db: Session = Depends(get_db),
                    user: m.User = Depends(require_permission("dispatch.manage"))):
    row = db.scalar(select(m.Dispatch).where(m.Dispatch.id == dispatch_id).with_for_update())
    if not row: raise HTTPException(404, "Dispatch not found")
    project_access(db, user, row.order.project_id)
    target = body.status.upper()
    allowed = {"DRAFT": {"READY", "CANCELLED"}, "READY": {"DISPATCHED", "CANCELLED"},
               "DISPATCHED": {"DELIVERED"}, "DELIVERED": set(), "CANCELLED": set()}
    if target not in allowed.get(row.status, set()): raise HTTPException(409, f"Invalid dispatch transition {row.status} -> {target}")
    old = row.status; row.status = target
    if target == "DISPATCHED":
        if not row.warehouse_id:
            raise HTTPException(409, "A warehouse is required before dispatch")
        warehouse = db.scalar(select(m.Warehouse).where(m.Warehouse.id == row.warehouse_id).with_for_update())
        for line in db.scalars(select(m.DispatchItem).where(m.DispatchItem.dispatch_id == row.id)).all():
            item = db.get(m.OrderItem, line.order_item_id)
            before = stock_balance(db, warehouse.id, item.product_id)
            if before < Decimal(line.quantity) and not warehouse.allow_negative:
                raise HTTPException(409, f"Insufficient physical stock for {item.sku}; available {before}")
            key = f"dispatch:{row.id}:{line.id}"
            if not db.scalar(select(m.StockLedger.id).where(m.StockLedger.idempotency_key == key)):
                db.add(m.StockLedger(product_id=item.product_id, warehouse_id=warehouse.id,
                    movement_type="DISPATCH", quantity=line.quantity, direction="OUT", reference_type="DISPATCH",
                    reference_id=row.id, idempotency_key=key, actor_id=user.id))
        row.dispatched_at = utcnow()
        row.order.status = "PARTIALLY_DISPATCHED"
    if target == "DELIVERED":
        row.delivered_at = utcnow()
        active = db.scalars(select(m.Dispatch).where(m.Dispatch.order_id == row.order_id, m.Dispatch.status != "CANCELLED")).all()
        order_items = db.scalars(select(m.OrderItem).where(m.OrderItem.order_id == row.order_id)).all()
        sent = {x.id: Decimal("0") for x in order_items}
        for d in active:
            for line in db.scalars(select(m.DispatchItem).where(m.DispatchItem.dispatch_id == d.id)).all():
                sent[line.order_item_id] = sent.get(line.order_item_id, Decimal("0")) + Decimal(line.quantity)
        row.order.status = "DELIVERED" if all(sent[x.id] >= Decimal(x.qty) for x in order_items) else "PARTIALLY_DISPATCHED"
    audit(db, user.id, "dispatch.status_changed", "dispatch", row.id, {"from": old, "to": target})
    db.commit()
    return dispatch_json(db, row)


class RMAIn(BaseModel):
    customer_id: str
    project_id: str | None = None
    order_id: str | None = None
    invoice_id: str | None = None
    product_id: str
    serial_number: str | None = None
    quantity: Decimal = Field(gt=0)
    reason: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=5, max_length=5000)


def rma_json(row: m.RMARequest) -> dict:
    return {key: getattr(row, key) for key in ("id", "number", "customer_id", "project_id", "order_id",
        "invoice_id", "product_id", "serial_number", "quantity", "reason", "description", "status",
        "resolution", "assigned_to", "requested_by", "created_at", "updated_at")}


@router.get("/rmas")
def list_rmas(db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_or(user, "rma.view")
    stmt = select(m.RMARequest)
    if user.role not in ADMIN_ROLES:
        allowed = select(m.ProjectUser.project_id).where(m.ProjectUser.user_id == user.id, m.ProjectUser.status == "ACTIVE")
        stmt = stmt.where((m.RMARequest.requested_by == user.id) | (m.RMARequest.project_id.in_(allowed)))
    return [rma_json(x) for x in db.scalars(stmt.order_by(desc(m.RMARequest.created_at))).all()]


@router.post("/rmas", dependencies=[Depends(require_csrf)])
def create_rma(body: RMAIn, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_or(user, "rma.create")
    project_access(db, user, body.project_id)
    if not db.get(m.Customer, body.customer_id) or not db.get(m.Product, body.product_id):
        raise HTTPException(404, "Customer or product not found")
    if body.project_id:
        project = db.get(m.Project, body.project_id)
        if not project or project.customer_id != body.customer_id: raise HTTPException(422, "Customer/project mismatch")
    if body.order_id:
        order = db.get(m.Order, body.order_id)
        if not order or order.customer_id != body.customer_id or (body.project_id and order.project_id != body.project_id):
            raise HTTPException(422, "Order does not belong to the selected customer/project")
        delivered = db.scalar(select(func.coalesce(func.sum(m.DispatchItem.quantity), 0)).join(
            m.Dispatch, m.Dispatch.id == m.DispatchItem.dispatch_id).join(
            m.OrderItem, m.OrderItem.id == m.DispatchItem.order_item_id).where(
            m.Dispatch.order_id == order.id, m.Dispatch.status == "DELIVERED",
            m.OrderItem.product_id == body.product_id)) or 0
        previous = db.scalar(select(func.coalesce(func.sum(m.RMARequest.quantity), 0)).where(
            m.RMARequest.order_id == order.id, m.RMARequest.product_id == body.product_id,
            m.RMARequest.status.not_in({"REJECTED", "CLOSED"}))) or 0
        if Decimal(previous) + body.quantity > Decimal(delivered):
            raise HTTPException(409, "RMA quantity exceeds the delivered quantity")
    if body.invoice_id:
        invoice = db.get(m.Invoice, body.invoice_id)
        if not invoice or invoice.customer_id != body.customer_id or (body.order_id and invoice.order_id != body.order_id):
            raise HTTPException(422, "Invoice does not belong to the selected customer/order")
    if body.serial_number:
        serial = db.get(m.SerialUnit, body.serial_number)
        if not serial or serial.product_id != body.product_id: raise HTTPException(422, "Serial number does not match product")
        duplicate = db.scalar(select(m.RMARequest).where(m.RMARequest.serial_number == body.serial_number,
            m.RMARequest.status.not_in({"REJECTED", "CLOSED"})))
        if duplicate: raise HTTPException(409, "This serial already has an active RMA")
    row = m.RMARequest(number=next_number(db, "rma", "RMA"), **body.model_dump(), requested_by=user.id)
    db.add(row); db.flush()
    db.add(m.RMAHistory(rma_id=row.id, from_status=None, to_status="REQUESTED", actor_id=user.id))
    audit(db, user.id, "rma.created", "rma", row.id)
    db.commit()
    return rma_json(row)


@router.post("/rmas/{rma_id}/status", dependencies=[Depends(require_csrf)])
def transition_rma(rma_id: str, body: StatusBody, db: Session = Depends(get_db),
                   user: m.User = Depends(require_permission("rma.manage"))):
    row = db.scalar(select(m.RMARequest).where(m.RMARequest.id == rma_id).with_for_update())
    if not row: raise HTTPException(404, "RMA not found")
    project_access(db, user, row.project_id)
    target = body.status.upper()
    allowed = {"REQUESTED": {"APPROVED", "REJECTED"}, "APPROVED": {"PICKUP_SCHEDULED", "RECEIVED"},
               "PICKUP_SCHEDULED": {"RECEIVED"}, "RECEIVED": {"INSPECTING"}, "INSPECTING": {"REPAIR", "REPLACE", "REFUND", "REJECTED"},
               "REPAIR": {"RESOLVED"}, "REPLACE": {"RESOLVED"}, "REFUND": {"RESOLVED"}, "RESOLVED": {"CLOSED"},
               "REJECTED": {"CLOSED"}, "CLOSED": set()}
    if target not in allowed.get(row.status, set()): raise HTTPException(409, f"Invalid RMA transition {row.status} -> {target}")
    old = row.status; row.status = target
    if target in {"REPAIR", "REPLACE", "REFUND"}: row.resolution = target
    db.add(m.RMAHistory(rma_id=row.id, from_status=old, to_status=target, notes=body.notes, actor_id=user.id))
    audit(db, user.id, "rma.status_changed", "rma", row.id, {"from": old, "to": target})
    db.commit()
    return rma_json(row)


class AnnouncementIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    content: str = Field(min_length=2, max_length=10000)
    audience: dict = Field(default_factory=dict)
    priority: str = "NORMAL"
    status: str = "DRAFT"
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    link_url: str | None = None

    @field_validator("link_url")
    @classmethod
    def valid_link(cls, value: str | None):
        return safe_external_url(value) if value else None


@router.get("/announcements")
def announcements(db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    now = utcnow()
    stmt = select(m.Announcement)
    if user.role not in ADMIN_ROLES:
        stmt = stmt.where(m.Announcement.status == "PUBLISHED",
                          (m.Announcement.starts_at.is_(None)) | (m.Announcement.starts_at <= now),
                          (m.Announcement.ends_at.is_(None)) | (m.Announcement.ends_at >= now))
    return [{"id": x.id, "title": x.title, "content": x.content, "priority": x.priority, "status": x.status,
             "audience": x.audience, "link_url": x.link_url, "starts_at": x.starts_at, "ends_at": x.ends_at}
            for x in db.scalars(stmt.order_by(desc(m.Announcement.created_at))).all()]


@router.post("/announcements", dependencies=[Depends(require_csrf)])
def create_announcement(body: AnnouncementIn, db: Session = Depends(get_db),
                        user: m.User = Depends(get_current_user)):
    admin_or(user, "announcements.manage")
    if body.ends_at and body.starts_at and body.ends_at <= body.starts_at: raise HTTPException(422, "End must be after start")
    data = body.model_dump(); data.update(priority=body.priority.upper(), status=body.status.upper())
    row = m.Announcement(**data, created_by=user.id)
    db.add(row); db.flush(); audit(db, user.id, "announcement.created", "announcement", row.id); db.commit()
    return {"id": row.id, "status": row.status}


@router.get("/notifications")
def notifications(unread_only: bool = False, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    stmt = select(m.Notification).where(m.Notification.user_id == user.id)
    if unread_only: stmt = stmt.where(m.Notification.read_at.is_(None))
    rows = db.scalars(stmt.order_by(desc(m.Notification.created_at)).limit(100)).all()
    return [{"id": x.id, "type": x.notification_type, "title": x.title, "message": x.message,
             "deep_link": x.deep_link, "read_at": x.read_at, "created_at": x.created_at} for x in rows]


@router.post("/notifications/{notification_id}/read", dependencies=[Depends(require_csrf)])
def read_notification(notification_id: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    row = db.scalar(select(m.Notification).where(m.Notification.id == notification_id, m.Notification.user_id == user.id))
    if not row: raise HTTPException(404, "Notification not found")
    row.read_at = row.read_at or utcnow(); db.commit()
    return {"id": row.id, "read_at": row.read_at}


class TicketIn(BaseModel):
    project_id: str | None = None
    category: str = Field(min_length=2, max_length=80)
    subject: str = Field(min_length=2, max_length=180)
    description: str = Field(min_length=5, max_length=5000)
    priority: str = "NORMAL"


@router.get("/tickets")
def tickets(db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    stmt = select(m.SupportTicket)
    if user.role not in ADMIN_ROLES and not has_permission(user, "tickets.manage"):
        stmt = stmt.where(m.SupportTicket.created_by == user.id)
    return [{"id": x.id, "number": x.number, "project_id": x.project_id, "category": x.category,
             "subject": x.subject, "description": x.description, "priority": x.priority,
             "status": x.status, "resolution": x.resolution, "created_at": x.created_at}
            for x in db.scalars(stmt.order_by(desc(m.SupportTicket.created_at))).all()]


@router.post("/tickets", dependencies=[Depends(require_csrf)])
def create_ticket(body: TicketIn, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    project_access(db, user, body.project_id)
    data = body.model_dump(); data["priority"] = body.priority.upper()
    row = m.SupportTicket(number=next_number(db, "ticket", "TKT"), **data, created_by=user.id)
    db.add(row); db.flush(); audit(db, user.id, "ticket.created", "ticket", row.id); db.commit()
    return {"id": row.id, "number": row.number, "status": row.status}


class ResourceIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    resource_type: str = Field(min_length=2, max_length=50)
    workspace: str | None = None
    audience: dict = Field(default_factory=dict)
    url: str
    description: str | None = Field(None, max_length=3000)

    @field_validator("url")
    @classmethod
    def valid_url(cls, value: str): return safe_external_url(value)


@router.get("/resources")
def resources(workspace: str | None = None, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    stmt = select(m.ResourceAsset).where(m.ResourceAsset.status == "PUBLISHED")
    if workspace: stmt = stmt.where((m.ResourceAsset.workspace.is_(None)) | (m.ResourceAsset.workspace == workspace.upper()))
    return [{"id": x.id, "title": x.title, "type": x.resource_type, "workspace": x.workspace,
             "url": x.url, "description": x.description} for x in db.scalars(stmt.order_by(m.ResourceAsset.title)).all()]


@router.post("/resources", dependencies=[Depends(require_csrf)])
def create_resource(body: ResourceIn, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_or(user, "resources.manage")
    data = body.model_dump()
    data.update(resource_type=body.resource_type.upper(), workspace=(body.workspace.upper() if body.workspace else None))
    row = m.ResourceAsset(**data, created_by=user.id)
    db.add(row); db.flush(); audit(db, user.id, "resource.created", "resource", row.id); db.commit()
    return {"id": row.id, "title": row.title}


@router.get("/operations/dashboard")
def operations_dashboard(db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_or(user, "reports.view")
    def count(model, *where):
        return int(db.scalar(select(func.count()).select_from(model).where(*where)) or 0)
    return {
        "partners": count(m.Partner, m.Partner.status == "ACTIVE"),
        "pending_approvals": count(m.ApprovalRequest, m.ApprovalRequest.status == "PENDING"),
        "open_dispatches": count(m.Dispatch, m.Dispatch.status.not_in({"DELIVERED", "CANCELLED"})),
        "open_rmas": count(m.RMARequest, m.RMARequest.status.not_in({"CLOSED", "REJECTED"})),
        "open_tickets": count(m.SupportTicket, m.SupportTicket.status.not_in({"RESOLVED", "CLOSED"})),
        "unread_notifications": count(m.Notification, m.Notification.user_id == user.id, m.Notification.read_at.is_(None)),
    }
