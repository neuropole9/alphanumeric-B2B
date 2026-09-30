from __future__ import annotations
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import models as m
from .config import settings

TWOPLACES = Decimal("0.01")


def money(v) -> Decimal:
    return Decimal(v or 0).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def invoice_tax_split(tax_total, customer_state: str | None, company_address: str | None) -> dict[str, Decimal]:
    """Snapshot mutually exclusive GST components from the configured jurisdictions."""
    total = money(tax_total)
    intra_state = bool(customer_state and customer_state.casefold() in (company_address or "").casefold())
    if intra_state:
        cgst = money(total / 2)
        return {"cgst": cgst, "sgst": total - cgst, "igst": Decimal("0.00")}
    return {"cgst": Decimal("0.00"), "sgst": Decimal("0.00"), "igst": total}




def commercial_line(quantity, rate, tax_rate) -> dict[str, Decimal]:
    """Return the authoritative rounded commercial values for one line."""
    qty = Decimal(quantity or 0)
    unit_rate = Decimal(rate or 0)
    tax = Decimal(tax_rate or 0)
    subtotal = money(qty * unit_rate)
    tax_amount = money(subtotal * tax / Decimal("100"))
    return {
        "subtotal": subtotal,
        "tax_amount": tax_amount,
        "total": money(subtotal + tax_amount),
    }


def next_number(db: Session, key: str, prefix: str | None = None) -> str:
    """Return the next document number using a database row lock where supported.

    Inquiry numbers intentionally use the immutable ANIPL0001 format. Other documents
    retain the existing PREFIX-YYYY-0001 format. The sequence row is persisted in the
    same transaction as the document that consumes it.
    """
    seq = db.scalar(select(m.DocumentSequence).where(m.DocumentSequence.key == key).with_for_update())
    if not seq:
        seq = m.DocumentSequence(key=key, next_value=1)
        db.add(seq)
        db.flush()
    value = int(seq.next_value)
    seq.next_value = value + 1
    if key in {"inquiry", "inquiry_anipl"}:
        return f"ANIPL{value:04d}"
    prefix = prefix or key.upper()
    return f"{prefix}-{date.today().year}-{value:04d}"


def audit(db: Session, actor_id: str | None, action: str, entity_type: str, entity_id: str | None, metadata: dict | None = None):
    db.add(m.AuditLog(actor_id=actor_id, action=action, entity_type=entity_type, entity_id=entity_id, metadata_json=metadata or {}))


def stock_status(product: m.Product) -> str:
    available = Decimal(product.on_hand or 0) - Decimal(product.reserved or 0)
    if available <= 0:
        return "OUT_OF_STOCK"
    if available <= Decimal(product.reorder_level or 0):
        return "LOW_STOCK"
    return "IN_STOCK"


def boq_rows(db: Session, inquiry_id: str) -> list[dict]:
    inquiry = db.get(m.Inquiry, inquiry_id)
    project = db.get(m.Project, inquiry.project_id) if inquiry and inquiry.project_id else None
    reqs = db.scalars(select(m.RoomRequirement).where(m.RoomRequirement.inquiry_id == inquiry_id)).all()
    grouped: dict[str, dict] = {}
    for r in reqs:
        p = r.product
        if p.id not in grouped:
            grouped[p.id] = {
                "product_id": p.id, "sku": p.sku, "name": p.name,
                "category": p.category.name if p.category else "", "workspace": p.workspace,
                "unit": r.unit or p.unit, "quantity": Decimal("0"), "rate": money(p.price),
                "tax_rate": money(p.tax_rate), "specs": p.specs or {}, "breakdown": []
            }
        grouped[p.id]["quantity"] += Decimal(r.quantity)
        room = r.room
        floor = room.floor if room else None
        building = floor.building if floor else None
        grouped[p.id]["breakdown"].append({
            "building": building.name if building else "",
            "floor": floor.name if floor else "",
            "room": room.name if room else "",
            "quantity": float(r.quantity),
            "notes": r.notes,
        })
    rows = list(grouped.values())
    for row in rows:
        from .advanced_services import resolve_price
        product = db.get(m.Product, row["product_id"])
        decision = resolve_price(db, product, row["quantity"], customer_id=(inquiry.customer_id if inquiry else None),
                                 partner_id=(project.partner_id if project else None),
                                 zone=(project.partner.zone if project and project.partner else None))
        row["rate"] = decision["final_price"]
        row["pricing_explanation"] = decision
        calc = commercial_line(row["quantity"], row["rate"], row["tax_rate"])
        row.update({
            "line_subtotal": calc["subtotal"],
            "tax_amount": calc["tax_amount"],
            "line_total": calc["total"],
        })
    return rows


def estimate_inquiry(db: Session, inquiry: m.Inquiry) -> Decimal:
    total = sum((Decimal(row["line_total"]) for row in boq_rows(db, inquiry.id)), Decimal("0"))
    inquiry.estimated_value = money(total)
    return inquiry.estimated_value


def recalc_quotation(db: Session, quotation: m.Quotation):
    items = db.scalars(select(m.QuotationItem).where(m.QuotationItem.quotation_id == quotation.id)).all()
    line_subtotals = [commercial_line(i.qty, i.rate, i.tax_rate)["subtotal"] for i in items]
    subtotal = sum(line_subtotals, Decimal("0"))
    discount_percent = Decimal(quotation.discount_percent or 0)
    discount = money(subtotal * discount_percent / Decimal("100"))
    discount_factor = (Decimal("100") - discount_percent) / Decimal("100")
    tax_total = sum((
        money(line_subtotal * discount_factor * Decimal(item.tax_rate or 0) / Decimal("100"))
        for line_subtotal, item in zip(line_subtotals, items)
    ), Decimal("0"))
    quotation.subtotal = money(subtotal)
    quotation.discount_amount = discount
    quotation.tax_total = money(tax_total)
    quotation.grand_total = money(quotation.subtotal - discount + quotation.tax_total)


def replace_draft_quotation_items(db: Session, quotation: m.Quotation, inquiry: m.Inquiry, actor_id: str) -> m.Quotation:
    if quotation.status != "DRAFT":
        raise ValueError("Only a DRAFT quotation can be updated from the latest BOQ")
    for item in db.scalars(select(m.QuotationItem).where(m.QuotationItem.quotation_id == quotation.id)).all():
        db.delete(item)
    db.flush()
    for row in boq_rows(db, inquiry.id):
        if row["workspace"] != inquiry.workspace:
            raise ValueError("Quotation blocked: inquiry contains a product from another application")
        amount = commercial_line(row["quantity"], row["rate"], row["tax_rate"])["subtotal"]
        db.add(m.QuotationItem(
            quotation_id=quotation.id, product_id=row["product_id"], description=row["name"], sku=row["sku"],
            qty=row["quantity"], rate=row["rate"], tax_rate=row["tax_rate"], amount=amount
        ))
    db.flush()
    recalc_quotation(db, quotation)
    inquiry.estimated_value = quotation.grand_total
    audit(db, actor_id, "quotation.updated_from_latest_boq", "quotation", quotation.id, {"inquiry_id": inquiry.id})
    return quotation


def _populate_quotation_from_boq(db: Session, quotation: m.Quotation, inquiry: m.Inquiry) -> None:
    rows = boq_rows(db, inquiry.id)
    if not rows:
        raise ValueError("Add at least one persisted room product before generating a quotation")
    for row in rows:
        if row["workspace"] != inquiry.workspace:
            raise ValueError("Quotation blocked: inquiry contains a product from another application")
        amount = commercial_line(row["quantity"], row["rate"], row["tax_rate"])["subtotal"]
        db.add(m.QuotationItem(
            quotation_id=quotation.id, product_id=row["product_id"], description=row["name"], sku=row["sku"],
            qty=row["quantity"], rate=row["rate"], tax_rate=row["tax_rate"], amount=amount
        ))
    db.flush()
    recalc_quotation(db, quotation)


def create_quotation_from_inquiry(db: Session, inquiry: m.Inquiry, actor_id: str) -> m.Quotation:
    """Create or return the current DRAFT quotation for an inquiry.

    SENT/ACCEPTED commercial snapshots are never mutated or silently reused as the
    editable draft. Use create_quotation_revision for an explicit new revision.
    """
    existing = db.scalar(select(m.Quotation).where(
        m.Quotation.inquiry_id == inquiry.id,
        m.Quotation.status == "DRAFT",
    ).order_by(m.Quotation.revision.desc(), m.Quotation.quotation_date.desc()))
    if existing:
        return existing
    latest = db.scalar(select(m.Quotation).where(
        m.Quotation.inquiry_id == inquiry.id
    ).order_by(m.Quotation.revision.desc(), m.Quotation.quotation_date.desc()).limit(1))
    if latest and latest.status in {"SENT", "ACCEPTED"}:
        return latest
    q = m.Quotation(
        number=next_number(db, "quotation", "QT"), inquiry_id=inquiry.id,
        customer_id=inquiry.customer_id, project_id=inquiry.project_id,
        building_id=inquiry.building_id, workspace=inquiry.workspace, status="DRAFT",
        revision=(latest.revision + 1 if latest else 1),
        supersedes_id=(latest.id if latest else None),
        valid_until=date.today()+timedelta(days=30)
    )
    db.add(q)
    db.flush()
    _populate_quotation_from_boq(db, q, inquiry)
    # Keep the submitted inquiry IN_PROCESS while the automatically-created quotation is only DRAFT.
    # The inquiry becomes QUOTED when the quotation is actually sent to the customer.
    inquiry.estimated_value = q.grand_total
    audit(db, actor_id, "quotation.created_from_inquiry", "quotation", q.id, {"inquiry_id": inquiry.id, "revision": q.revision})
    return q


def create_quotation_revision(db: Session, inquiry: m.Inquiry, actor_id: str) -> m.Quotation:
    """Create an explicit DRAFT revision from the current persisted BOQ."""
    current_draft = db.scalar(select(m.Quotation).where(
        m.Quotation.inquiry_id == inquiry.id, m.Quotation.status == "DRAFT"
    ).order_by(m.Quotation.revision.desc()).limit(1))
    if current_draft:
        return current_draft
    latest = db.scalar(select(m.Quotation).where(
        m.Quotation.inquiry_id == inquiry.id
    ).order_by(m.Quotation.revision.desc(), m.Quotation.quotation_date.desc()).limit(1))
    if latest and latest.status not in {"SENT", "ACCEPTED", "REJECTED", "EXPIRED", "SUPERSEDED"}:
        raise ValueError("A new revision can only be created after the previous quotation leaves DRAFT")
    q = m.Quotation(
        number=next_number(db, "quotation", "QT"), inquiry_id=inquiry.id,
        customer_id=inquiry.customer_id, project_id=inquiry.project_id,
        building_id=inquiry.building_id, workspace=inquiry.workspace, status="DRAFT",
        revision=(int(latest.revision or 1) + 1 if latest else 1),
        supersedes_id=(latest.id if latest else None),
        valid_until=date.today()+timedelta(days=30)
    )
    db.add(q)
    db.flush()
    _populate_quotation_from_boq(db, q, inquiry)
    if latest and latest.status in {"SENT", "REJECTED", "EXPIRED"}:
        latest.status = "SUPERSEDED"
    # Creating a DRAFT revision must not advance the inquiry lifecycle.
    inquiry.estimated_value = q.grand_total
    audit(db, actor_id, "quotation.revision_created", "quotation", q.id, {
        "inquiry_id": inquiry.id, "revision": q.revision, "supersedes_id": q.supersedes_id
    })
    return q


def convert_quotation_to_order(db: Session, quotation: m.Quotation, actor_id: str) -> m.Order:
    existing = db.scalar(select(m.Order).where(m.Order.quotation_id == quotation.id))
    if existing:
        return existing
    if quotation.status != "ACCEPTED":
        raise ValueError("Quotation must be accepted before conversion")
    qitems = db.scalars(select(m.QuotationItem).where(m.QuotationItem.quotation_id == quotation.id)).all()
    locked_products: dict[str, m.Product] = {}
    for item in qitems:
        product = db.scalar(select(m.Product).where(m.Product.id == item.product_id).with_for_update())
        if not product:
            raise ValueError(f"Product {item.sku} no longer exists")
        available = Decimal(product.on_hand or 0) - Decimal(product.reserved or 0)
        if available < Decimal(item.qty):
            raise ValueError(f"Insufficient available stock for {product.name}; available {available}")
        locked_products[product.id] = product
    order = m.Order(
        number=next_number(db, "order", "ORD"), quotation_id=quotation.id, customer_id=quotation.customer_id,
        project_id=quotation.project_id, building_id=quotation.building_id,
        workspace=quotation.workspace, status="CONFIRMED",
        delivery_date=date.today()+timedelta(days=14), subtotal=quotation.subtotal,
        tax_total=quotation.tax_total, grand_total=quotation.grand_total
    )
    db.add(order)
    db.flush()
    for qi in qitems:
        db.add(m.OrderItem(order_id=order.id, product_id=qi.product_id, description=qi.description, sku=qi.sku,
                           qty=qi.qty, rate=qi.rate, tax_rate=qi.tax_rate, amount=qi.amount))
        product = locked_products[qi.product_id]
        product.reserved = Decimal(product.reserved or 0) + Decimal(qi.qty)
        db.add(m.InventoryMovement(product_id=product.id, movement_type="RESERVE", quantity=qi.qty,
                                   reference_type="ORDER", reference_id=order.id, reason="Confirmed order reservation", created_by=actor_id))
    quotation.inquiry.status = "COMPLETED"
    audit(db, actor_id, "order.created_from_quotation", "order", order.id, {"quotation_id": quotation.id})
    return order


def update_order_status(db: Session, order: m.Order, new_status: str, actor_id: str):
    allowed = {
        "CONFIRMED": {"AWAITING_ADVANCE", "PROCESSING", "ON_HOLD", "CANCELLED"},
        "AWAITING_ADVANCE": {"PARTIALLY_PAID", "PAID", "ON_HOLD", "CANCELLED"},
        "PARTIALLY_PAID": {"PAID", "PROCESSING", "ON_HOLD", "CANCELLED"},
        "PAID": {"PROCESSING", "ON_HOLD"},
        "PROCESSING": {"READY", "ON_HOLD", "CANCELLED"},
        "READY": {"DISPATCHED", "PARTIALLY_DISPATCHED", "ON_HOLD", "CANCELLED"},
        "PARTIALLY_DISPATCHED": {"DISPATCHED", "DELIVERED"},
        "DISPATCHED": {"DELIVERED"},
        "DELIVERED": {"COMPLETED"}, "COMPLETED": set(), "ON_HOLD": {"PROCESSING", "CANCELLED"},
        "CANCELLED": set(),
    }
    old = order.status
    if new_status not in allowed.get(old, set()):
        raise ValueError(f"Invalid transition {old} -> {new_status}")
    items = db.scalars(select(m.OrderItem).where(m.OrderItem.order_id == order.id)).all()
    if new_status == "DISPATCHED":
        for item in items:
            p = db.get(m.Product, item.product_id)
            qty = Decimal(item.qty)
            if Decimal(p.on_hand or 0) < qty:
                raise ValueError(f"Insufficient stock for {p.name}")
            p.on_hand = Decimal(p.on_hand or 0) - qty
            p.reserved = max(Decimal("0"), Decimal(p.reserved or 0) - qty)
            db.add(m.InventoryMovement(product_id=p.id, movement_type="DISPATCH", quantity=-qty,
                                       reference_type="ORDER", reference_id=order.id, reason="Order dispatched", created_by=actor_id))
        order.dispatched_at = datetime.now(timezone.utc)
    elif new_status == "CANCELLED":
        for item in items:
            p = db.get(m.Product, item.product_id)
            qty = Decimal(item.qty)
            p.reserved = max(Decimal("0"), Decimal(p.reserved or 0) - qty)
            db.add(m.InventoryMovement(product_id=p.id, movement_type="RESERVATION_RELEASE", quantity=-qty,
                                       reference_type="ORDER", reference_id=order.id, reason="Order cancelled", created_by=actor_id))
    order.status = new_status
    audit(db, actor_id, "order.status_changed", "order", order.id, {"from": old, "to": new_status})


def create_invoice_from_order(db: Session, order: m.Order, actor_id: str) -> m.Invoice:
    existing = db.scalar(select(m.Invoice).where(m.Invoice.order_id == order.id))
    if existing:
        return existing
    if order.quotation.status != "ACCEPTED" or order.status not in {"CONFIRMED", "AWAITING_ADVANCE", "PARTIALLY_PAID", "PAID", "PROCESSING", "READY", "PARTIALLY_DISPATCHED", "DISPATCHED", "DELIVERED", "COMPLETED"}:
        raise ValueError("Invoice requires an accepted quotation and an active confirmed order")
    tax_split = invoice_tax_split(order.tax_total, order.customer.state, settings.company_address)
    inv = m.Invoice(
        number=next_number(db, "invoice", "INV"), order_id=order.id, customer_id=order.customer_id,
        project_id=order.project_id, building_id=order.building_id,
        workspace=order.workspace, status="ISSUED",
        due_date=date.today()+timedelta(days=30), place_of_supply=order.customer.state,
        subtotal=order.subtotal, cgst=tax_split["cgst"], sgst=tax_split["sgst"],
        igst=tax_split["igst"], grand_total=order.grand_total
    )
    db.add(inv)
    db.flush()
    items = db.scalars(select(m.OrderItem).where(m.OrderItem.order_id == order.id)).all()
    for oi in items:
        product = db.get(m.Product, oi.product_id)
        db.add(m.InvoiceItem(invoice_id=inv.id, product_id=oi.product_id, description=oi.description, sku=oi.sku,
                             hsn_sac=product.hsn_sac if product else None, qty=oi.qty, unit=product.unit if product else "Nos",
                             rate=oi.rate, tax_rate=oi.tax_rate, amount=oi.amount))
    audit(db, actor_id, "invoice.created_from_order", "invoice", inv.id, {"order_id": order.id, "project_id": order.project_id})
    return inv
