from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from email.message import EmailMessage
from io import BytesIO
from pathlib import Path
from html import escape
import smtplib

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from . import models as m
from .config import settings
from .reports_TableFormat import _page_frame, _wide_table

CENT = Decimal("0.01")


def money(value: object) -> Decimal:
    return Decimal(value or 0).quantize(CENT, rounding=ROUND_HALF_UP)


def resolve_price(db: Session, product: m.Product, quantity: Decimal, *, customer_id: str | None = None,
                  partner_id: str | None = None, zone: str | None = None, as_of: date | None = None) -> dict:
    """Resolve a price predictably and return the complete decision explanation."""
    day, qty = as_of or date.today(), Decimal(quantity)
    rules = db.scalars(select(m.PricingRule).where(
        m.PricingRule.status == "ACTIVE", m.PricingRule.valid_from <= day,
        or_(m.PricingRule.valid_until.is_(None), m.PricingRule.valid_until >= day),
        m.PricingRule.min_quantity <= qty,
        or_(m.PricingRule.max_quantity.is_(None), m.PricingRule.max_quantity >= qty),
    )).all()
    eligible: list[tuple[int, m.PricingRule]] = []
    considered: list[dict] = []
    for rule in rules:
        matches = ((rule.product_id is None or rule.product_id == product.id) and
                   (rule.category_id is None or rule.category_id == product.category_id) and
                   (rule.customer_id is None or rule.customer_id == customer_id) and
                   (rule.partner_id is None or rule.partner_id == partner_id) and
                   (rule.zone is None or (zone or "").casefold() == rule.zone.casefold()))
        specificity = sum(v is not None for v in (rule.product_id, rule.category_id, rule.customer_id, rule.partner_id, rule.zone))
        considered.append({"id": rule.id, "name": rule.name, "matched": matches, "priority": rule.priority,
                           "specificity": specificity})
        if matches: eligible.append((specificity, rule))
    eligible.sort(key=lambda pair: (-pair[1].priority, -pair[0], pair[1].created_at, pair[1].id))
    base, winner = money(product.price), eligible[0][1] if eligible else None
    final = base
    if winner:
        value = Decimal(winner.adjustment_value)
        if winner.adjustment_type == "FIXED_PRICE": final = money(value)
        elif winner.adjustment_type == "PERCENT_DISCOUNT": final = money(base * (Decimal(100) - value) / Decimal(100))
        elif winner.adjustment_type == "FIXED_DISCOUNT": final = money(max(Decimal(0), base - value))
        elif winner.adjustment_type == "PERCENT_MARKUP": final = money(base * (Decimal(100) + value) / Decimal(100))
    return {"base_price": base, "final_price": final, "quantity": qty,
            "winning_rule": None if not winner else {"id": winner.id, "name": winner.name,
            "adjustment_type": winner.adjustment_type, "adjustment_value": winner.adjustment_value,
            "priority": winner.priority}, "considered_rules": considered,
            "precedence": "priority DESC, specificity DESC, created_at ASC, id ASC"}


def recalc_financial_document(db: Session, document: m.FinancialDocument) -> None:
    items = db.scalars(select(m.FinancialDocumentItem).where(m.FinancialDocumentItem.document_id == document.id)).all()
    subtotal = Decimal(0)
    for item in items:
        item.line_subtotal = money(Decimal(item.quantity) * Decimal(item.unit_price))
        item.line_tax = money(item.line_subtotal * Decimal(item.tax_rate) / Decimal(100))
        item.line_total = money(item.line_subtotal + item.line_tax); subtotal += item.line_subtotal
    document.subtotal = money(subtotal)
    document.discount_amount = money(document.subtotal * Decimal(document.discount_percent or 0) / Decimal(100))
    factor = (Decimal(100) - Decimal(document.discount_percent or 0)) / Decimal(100)
    document.tax_total = money(sum((money(i.line_tax * factor) for i in items), Decimal(0)))
    document.grand_total = money(document.subtotal - document.discount_amount + Decimal(document.freight or 0) +
                                 Decimal(document.additional_charges or 0) + document.tax_total)


def financial_document_pdf(db: Session, document: m.FinancialDocument) -> bytes:
    customer, project = db.get(m.Customer, document.customer_id), db.get(m.Project, document.project_id)
    items = db.scalars(select(m.FinancialDocumentItem).where(m.FinancialDocumentItem.document_id == document.id)).all()
    out = BytesIO(); styles = getSampleStyleSheet()
    pdf = SimpleDocTemplate(out, pagesize=A4, leftMargin=12*mm, rightMargin=12*mm, topMargin=24*mm, bottomMargin=21*mm)
    story = [Paragraph(settings.company_name, styles["Title"]), Paragraph(document.document_type.replace("_", " ").title(), styles["Heading2"]),
             Paragraph(f"Document: {document.number} &nbsp;&nbsp; Status: {document.status}", styles["BodyText"]),
             Paragraph(f"Customer: {customer.company_name if customer else '—'}", styles["BodyText"]),
             Paragraph(f"Project: {project.name if project else '—'}", styles["BodyText"]), Spacer(1, 5*mm)]
    data = [["SKU", "Description", "Qty", "Rate", "Tax %", "Total"]]
    data += [[Paragraph(escape(i.sku or "—"), styles["BodyText"]),
              Paragraph(escape(i.description or "—"), styles["BodyText"]),
              str(i.quantity), f"{i.unit_price:.2f}", str(i.tax_rate), f"{i.line_total:.2f}"] for i in items]
    table = _wide_table(data, [25*mm, 65*mm, 18*mm, 25*mm, 18*mm, 28*mm], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0B2E59")), ("TEXTCOLOR", (0,0), (-1,0), colors.white),
                               ("LINEBELOW", (0,0), (-1,-1), .4, colors.grey), ("VALIGN", (0,0), (-1,-1), "TOP"),
                               ("ALIGN", (2,1), (-1,-1), "RIGHT")]))
    story += [table, Spacer(1, 4*mm), Paragraph(f"Grand total: {document.grand_total:.2f}", styles["Heading2"])]
    if document.reason: story.append(Paragraph(f"Reason: {document.reason}", styles["BodyText"]))
    page = lambda canvas, current: _page_frame(canvas, current, f"{document.document_type} {document.number}")
    pdf.build(story, onFirstPage=page, onLaterPages=page); return out.getvalue()


def rma_service_pdf(db: Session, row: m.RMARequest) -> bytes:
    product, customer = db.get(m.Product, row.product_id), db.get(m.Customer, row.customer_id)
    parts = db.scalars(select(m.RMAPart).where(m.RMAPart.rma_id == row.id)).all()
    out = BytesIO(); styles = getSampleStyleSheet(); pdf = SimpleDocTemplate(
        out, pagesize=A4, leftMargin=12*mm, rightMargin=12*mm, topMargin=24*mm, bottomMargin=21*mm)
    story = [Paragraph(settings.company_name, styles["Title"]), Paragraph("RMA Service Report", styles["Heading2"]),
             Paragraph(f"RMA: {row.number} &nbsp;&nbsp; Status: {row.status}", styles["BodyText"]),
             Paragraph(f"Customer: {customer.company_name if customer else '—'}", styles["BodyText"]),
             Paragraph(f"Product: {product.name if product else '—'} &nbsp;&nbsp; Serial: {row.serial_number or '—'}", styles["BodyText"]),
             Spacer(1, 4*mm), Paragraph(f"Issue: {row.description}", styles["BodyText"]),
             Paragraph(f"Inspection: {row.inspection_notes or '—'}", styles["BodyText"]),
             Paragraph(f"Diagnosis: {row.diagnosis or '—'}", styles["BodyText"]),
             Paragraph(f"Warranty: {'Eligible' if row.warranty_eligible else 'Not eligible' if row.warranty_eligible is False else 'Pending'} — {row.warranty_reason or '—'}", styles["BodyText"]),
             Paragraph(f"Resolution: {row.resolution or 'Pending'}", styles["BodyText"]), Spacer(1, 4*mm)]
    data=[["Part","Quantity","Unit cost"]]+[[db.get(m.Product,p.product_id).name,str(p.quantity),f"{p.unit_cost:.2f}"] for p in parts]
    table=_wide_table(data,[100*mm,40*mm,40*mm],repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#0B2E59")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("LINEBELOW",(0,0),(-1,-1),.4,colors.grey)]))
    story += [table, Spacer(1, 4*mm), Paragraph(f"Labour cost: {money(row.labour_cost):.2f}", styles["Heading3"])]
    page = lambda canvas, current: _page_frame(canvas, current, f"RMA {row.number}")
    pdf.build(story, onFirstPage=page, onLaterPages=page); return out.getvalue()


def deliver_email(row: m.EmailDelivery) -> None:
    """Send through the configured adapter. Never logs credentials or message bodies."""
    row.attempts = int(row.attempts or 0) + 1
    try:
        if settings.email_backend == "file":
            root = Path(settings.email_file_dir).resolve(); root.mkdir(parents=True, exist_ok=True)
            (root / f"{row.id}.eml").write_text(f"To: {row.recipient}\nSubject: {row.subject}\n\n{row.text_body}", encoding="utf-8")
        elif settings.email_backend == "smtp":
            if not settings.smtp_host: raise RuntimeError("SMTP_HOST is not configured")
            msg = EmailMessage(); msg["From"] = settings.smtp_from; msg["To"] = row.recipient; msg["Subject"] = row.subject
            msg.set_content(row.text_body); msg.add_alternative(row.html_body, subtype="html")
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as client:
                if settings.smtp_use_tls: client.starttls()
                if settings.smtp_username: client.login(settings.smtp_username, settings.smtp_password or "")
                client.send_message(msg)
        row.status, row.error_message, row.sent_at = "SENT", None, datetime.now(timezone.utc)
    except Exception as exc:
        row.status, row.error_message = "FAILED", str(exc)[:1000]
