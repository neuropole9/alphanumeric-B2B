from io import BytesIO
from decimal import Decimal
from html import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import settings
from . import models as m
from .reports_TableFormat import _media_path, _page_frame, _technical_card, _styles, _wide_table
from .pdf_format import compact_decimal, inr, percent


def rupee(v):
    return inr(v)


def safe(value) -> str:
    return escape(str(value or ""))


def money_html(value) -> str:
    return safe(rupee(value)).replace(" ", "&nbsp;")


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


def commercial_page(canvas, doc, label: str, number: str) -> None:
    _page_frame(canvas, doc, f"{label} {number}")


def _base_doc(title: str):
    buf=BytesIO(); doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=12*mm,leftMargin=12*mm,topMargin=24*mm,bottomMargin=21*mm,title=title)
    return buf,doc


def invoice_pdf(db: Session, inv: m.Invoice) -> bytes:
    items = db.scalars(select(m.InvoiceItem).where(m.InvoiceItem.invoice_id == inv.id)).all()
    customer, order = inv.customer, inv.order
    project = inv.project or order.project
    building = db.get(m.Building, inv.building_id) if inv.building_id else None
    payments = db.scalars(select(m.InvoicePayment).where(m.InvoicePayment.invoice_id == inv.id)).all()
    paid = sum((Decimal(row.amount) for row in payments), Decimal("0"))
    discount_percent = Decimal(order.quotation.discount_percent or 0) if order.quotation else Decimal("0")
    discount_amount = (Decimal(inv.subtotal or 0) * discount_percent / Decimal("100")).quantize(Decimal("0.01"))

    buf, doc = _base_doc(f"Tax Invoice {inv.number}")
    styles = getSampleStyleSheet()
    heading = ParagraphStyle("invoice-heading", parent=styles["Heading1"], fontSize=18, leading=21,
                             textColor=colors.HexColor("#0f2f57"))
    small = ParagraphStyle("invoice-small", parent=styles["Normal"], fontSize=7.3, leading=9)
    cell = ParagraphStyle("invoice-cell", parent=styles["Normal"], fontSize=6.6, leading=8)
    right = ParagraphStyle("invoice-right", parent=cell, fontSize=6, leading=7.2, alignment=TA_RIGHT)
    logo = None
    if settings.company_logo_path:
        from pathlib import Path
        logo_path = Path(settings.company_logo_path).expanduser()
        if logo_path.is_file():
            logo = Image(str(logo_path), width=32 * mm, height=14 * mm, kind="proportional")
    company_title = [logo, Paragraph(f"<b>{safe(settings.company_name)}</b>", heading)] if logo else [Paragraph(f"<b>{safe(settings.company_name)}</b>", heading)]
    header = _wide_table([[company_title, Paragraph("<b>TAX INVOICE</b>", heading)]], [108 * mm, 62 * mm], style=[
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.8, colors.HexColor("#0f2f57")),
    ])
    company = Paragraph(
        f"{safe(settings.company_address)}<br/>GSTIN: {safe(settings.company_gstin or '-')} &nbsp; | &nbsp; "
        f"PAN: {safe(settings.company_pan or '-')}<br/>{safe(settings.company_phone)} &nbsp; | &nbsp; {safe(settings.company_email)}",
        small,
    )
    terms = order.quotation.payment_terms if order.quotation else "Net 30 Days"
    meta = [["Invoice No.", inv.number], ["Invoice Date", str(inv.invoice_date)], ["Due Date", str(inv.due_date or "-")],
            ["Order No.", order.number], ["Payment Terms", terms], ["Place of Supply", inv.place_of_supply or customer.state or "-"]]
    meta_table = Table([[Paragraph(f"<b>{safe(k)}</b>", small), Paragraph(safe(v), small)] for k, v in meta],
                       colWidths=[30 * mm, 39 * mm], style=[
                           ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#d7e0eb")),
                           ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f7fb")),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"),
                       ])
    bill = Paragraph(f"<b>Bill To</b><br/><b>{safe(customer.company_name)}</b><br/>{safe(customer.address)}<br/>"
                     f"{safe(customer.city)}, {safe(customer.state)}<br/>GSTIN: {safe(customer.gstin or '-')}", small)
    shipping = order.delivery_address or (building.address if building and building.address else project.address) or customer.address
    ship = Paragraph(f"<b>Ship To / Project</b><br/><b>{safe(project.name)}</b><br/>{safe(building.name) if building else 'Project-wide'}<br/>"
                     f"{safe(shipping)}<br/>{safe(project.city)}, {safe(project.state)}", small)
    details = _wide_table([[bill, ship, meta_table]], [50 * mm, 51 * mm, 69 * mm], style=[
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#d7e0eb")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (1, 0), 6),
        ("RIGHTPADDING", (0, 0), (1, 0), 6), ("TOPPADDING", (0, 0), (1, 0), 6),
    ])

    rows = [[Paragraph(f"<b>{safe(x)}</b>", cell) for x in
             ["#", "Product / Model / SKU", "HSN/SAC", "Qty", "Unit", "Rate", "Discount", "Taxable", "Tax", "Line Total"]]]
    line_tax_total = Decimal("0")
    for index, item in enumerate(items, 1):
        product = db.get(m.Product, item.product_id)
        family = product.family.name if product and product.family else item.description
        model = product.model_number if product else None
        gross = Decimal(item.amount or 0)
        line_discount = (gross * discount_percent / Decimal("100")).quantize(Decimal("0.01"))
        taxable = gross - line_discount
        line_tax = (taxable * Decimal(item.tax_rate or 0) / Decimal("100")).quantize(Decimal("0.01"))
        line_tax_total += line_tax
        description = f"<b>{safe(item.description)}</b><br/>{safe(family)}"
        if model:
            description += f" · {safe(model)}"
        description += f"<br/><b>SKU:</b> {safe(item.sku)}"
        rows.append([
            Paragraph(str(index), cell), Paragraph(description, cell), Paragraph(safe(item.hsn_sac or "-"), cell),
            Paragraph(compact_decimal(item.qty), right), Paragraph(safe(item.unit), cell), Paragraph(money_html(item.rate), right),
            Paragraph(f"{percent(discount_percent)}<br/>{money_html(line_discount)}", right), Paragraph(money_html(taxable), right),
            Paragraph(f"{percent(item.tax_rate)}<br/>{money_html(line_tax)}", right), Paragraph(money_html(taxable + line_tax), right),
        ])
    items_table = _wide_table(rows, [6 * mm, 32 * mm, 16 * mm, 10 * mm, 10 * mm, 19 * mm,
                                     18 * mm, 21 * mm, 21 * mm, 21 * mm], repeatRows=1, splitByRow=1)
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f2f57")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#cfd9e6")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f9fc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    taxable_value = Decimal(inv.subtotal or 0) - discount_amount
    totals = [["Subtotal", rupee(inv.subtotal)]]
    if discount_amount:
        totals.append([f"Discount ({percent(discount_percent)})", f"- {rupee(discount_amount)}"])
    totals.append(["Taxable Value", rupee(taxable_value)])
    if Decimal(inv.igst or 0):
        totals.append(["IGST", rupee(inv.igst)])
    else:
        if Decimal(inv.cgst or 0): totals.append(["CGST", rupee(inv.cgst)])
        if Decimal(inv.sgst or 0): totals.append(["SGST", rupee(inv.sgst)])
    totals.extend([["Round Off", rupee(inv.round_off)], ["Grand Total", rupee(inv.grand_total)]])
    totals_table = Table([[Paragraph(f"<b>{safe(k)}</b>" if k == "Grand Total" else safe(k), small),
                           Paragraph(f"<b>{safe(v)}</b>" if k == "Grand Total" else safe(v), right)] for k, v in totals],
                         colWidths=[39 * mm, 39 * mm], hAlign="RIGHT", style=[
                             ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#cfd9e6")),
                             ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#dcecff")),
                             ("VALIGN", (0, 0), (-1, -1), "TOP"),
                         ])
    amount = Paragraph(f"<b>Amount in Words</b><br/>{safe(amount_in_words(Decimal(inv.grand_total or 0)))}<br/><br/>"
                       f"<b>Payment Status:</b> {safe(inv.status)} &nbsp; | &nbsp; <b>Paid:</b> {safe(rupee(paid))} &nbsp; | &nbsp; "
                       f"<b>Balance:</b> {safe(rupee(Decimal(inv.grand_total or 0) - paid))}", small)
    notes = (order.quotation.notes if order.quotation else None) or "Supply is subject to the accepted commercial terms and applicable warranty."
    footer = Table([[Paragraph(f"<b>Bank / Payment Details</b><br/>{safe(settings.bank_name)}<br/>{safe(settings.bank_account_name)}<br/>"
                              f"A/C: {safe(settings.bank_account_number)}<br/>IFSC: {safe(settings.bank_ifsc)}", small),
                     Paragraph(f"<b>Terms & Notes</b><br/>{safe(terms)}<br/>{safe(notes)}", small),
                     Paragraph(f"<b>Authorized Signatory</b><br/><br/><br/>For {safe(settings.company_name)}", small)]],
                   colWidths=[54 * mm, 70 * mm, 46 * mm], style=[
                       ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#d7e0eb")),
                       ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                       ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                   ])
    story = [header, Spacer(1, 2 * mm), company, Spacer(1, 4 * mm), details, Spacer(1, 4 * mm),
             items_table, Spacer(1, 4 * mm), _wide_table([[amount, totals_table]], [92 * mm, 78 * mm],
                                                    style=[("VALIGN", (0, 0), (-1, -1), "TOP")]),
             Spacer(1, 5 * mm), footer]
    page = lambda canvas, current_doc: commercial_page(canvas, current_doc, "TAX INVOICE", inv.number)
    doc.build(story, onFirstPage=page, onLaterPages=page)
    return buf.getvalue()


def quotation_pdf(db: Session, q: m.Quotation) -> bytes:
    items = db.scalars(select(m.QuotationItem).where(m.QuotationItem.quotation_id == q.id)).all()
    building = db.get(m.Building, q.building_id) if q.building_id else None
    customer, project, inquiry = q.customer, q.project, q.inquiry
    buf, doc = _base_doc(f"Quotation {q.number}")
    styles = getSampleStyleSheet()
    heading = ParagraphStyle("quotation-heading", parent=styles["Heading1"], fontSize=19,
                             leading=22, textColor=colors.HexColor("#0f2f57"), spaceAfter=0)
    small = ParagraphStyle("quotation-small", parent=styles["Normal"], fontSize=8, leading=10)
    body = ParagraphStyle("quotation-body", parent=styles["Normal"], fontSize=8.5, leading=11)
    table_text = ParagraphStyle("quotation-table", parent=styles["Normal"], fontSize=7.2, leading=8.5)

    header = _wide_table([
        [Paragraph(f"<b>{safe(settings.company_name)}</b>", heading), Paragraph("<b>QUOTATION</b>", heading)],
        [Paragraph(
            f"{safe(settings.company_address)}<br/>GSTIN: {safe(settings.company_gstin or '-')} &nbsp; | &nbsp; "
            f"PAN: {safe(settings.company_pan or '-')}<br/>{safe(settings.company_phone)} &nbsp; | &nbsp; "
            f"{safe(settings.company_email)}", small), ""],
    ], [112 * mm, 58 * mm], style=[
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LINEBELOW", (0, 1), (-1, 1), 0.8, colors.HexColor("#0f2f57")),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 7),
    ])

    customer_text = (f"<b>Prepared For</b><br/><b>{safe(customer.company_name)}</b><br/>"
                     f"{safe(customer.contact_person)}<br/>{safe(customer.address)}<br/>"
                     f"{safe(customer.city)}, {safe(customer.state)}<br/>GSTIN: {safe(customer.gstin or '-')}")
    project_text = (f"<b>Project</b><br/><b>{safe(project.name)}</b><br/>"
                    f"{safe(building.name) if building else 'Project-wide scope'}<br/>"
                    f"{safe(project.address)}<br/>{safe(project.city)}, {safe(project.state)}")
    metadata = Table([
        ["Quotation No.", q.number], ["Quotation Date", str(q.quotation_date)],
        ["Valid Until", str(q.valid_until or "-")], ["Revision", str(q.revision or 1)],
        ["Inquiry", inquiry.number if inquiry else "-"], ["Status", q.status],
    ], colWidths=[29 * mm, 34 * mm], style=[
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#cfd9e6")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#edf3f9")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ])
    details = _wide_table([[Paragraph(customer_text, body), Paragraph(project_text, body), metadata]],
                    [55 * mm, 52 * mm, 63 * mm], style=[
                        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#cfd9e6")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ])

    rows = [["#", "Image", "Product / Model", "SKU", "Qty", "Unit", "Rate", "Disc.", "Tax", "Amount"]]
    for index, item in enumerate(items, 1):
        product = item.product
        media = _media_path(product)
        image = Image(media, width=12 * mm, height=12 * mm, kind="proportional") if media else Paragraph("—", table_text)
        product_text = safe(item.description)
        if product.model_number:
            product_text += f"<br/><b>Model:</b> {safe(product.model_number)}"
        rows.append([index, image, Paragraph(product_text, table_text), Paragraph(safe(item.sku), table_text),
                     f"{item.qty:g}", safe(product.unit), rupee(item.rate),
                     f"{Decimal(q.discount_percent or 0):g}%", f"{item.tax_rate:g}%", rupee(item.amount)])
    item_table = _wide_table(rows, [7 * mm, 14 * mm, 35 * mm, 20 * mm, 11 * mm, 10 * mm,
                                       20 * mm, 14 * mm, 17 * mm, 22 * mm],
                       repeatRows=1, style=[
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f2f57")),
                           ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#cfd9e6")),
                           ("FONTSIZE", (0, 0), (-1, -1), 7.2),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("ALIGN", (4, 1), (-1, -1), "RIGHT"),
                           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                       ])

    same_state = bool(customer.state and customer.state.lower() in (settings.company_address or "").lower())
    tax_rows = ([['CGST', rupee(Decimal(q.tax_total or 0) / 2)],
                 ['SGST', rupee(Decimal(q.tax_total or 0) / 2)]] if same_state
                else [['IGST', rupee(q.tax_total)]])
    totals_data = [["Subtotal", rupee(q.subtotal)],
                   [f"Discount ({Decimal(q.discount_percent or 0):g}%)", f"- {rupee(q.discount_amount)}"],
                   *tax_rows, ["Grand Total", rupee(q.grand_total)]]
    totals = Table(totals_data, colWidths=[39 * mm, 35 * mm], hAlign="RIGHT", style=[
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#cfd9e6")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#dcecff")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ])
    amount = Paragraph(f"<b>Amount in Words</b><br/>{safe(amount_in_words(Decimal(q.grand_total or 0)))}", body)
    commercial_terms = _wide_table([
        [Paragraph(f"<b>Payment Terms</b><br/>{safe(q.payment_terms or '-')}", body),
         Paragraph(f"<b>Delivery Terms</b><br/>{safe(q.delivery_terms or 'As mutually agreed and subject to stock availability.')}", body)],
        [Paragraph(f"<b>Warranty</b><br/>{safe(q.warranty_terms or 'As per the applicable product warranty terms.')}", body),
         Paragraph(f"<b>Notes</b><br/>{safe(q.notes or 'Prices and delivery are subject to this quotation validity.')}", body)],
    ], [85 * mm, 85 * mm], style=[
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#cfd9e6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ])
    signatory = _wide_table([[Paragraph("Commercial offer subject to the stated validity and terms.", small),
                        Paragraph(f"<b>Authorized Signatory</b><br/><br/><br/>For {safe(settings.company_name)}", body)]],
                      [105 * mm, 65 * mm], style=[
                          ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                          ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.HexColor("#cfd9e6")),
                          ("TOPPADDING", (0, 0), (-1, -1), 8),
                      ])

    appendix = []
    if items:
        appendix = [PageBreak(), Paragraph("Product Technical Specifications", heading), Spacer(1, 3 * mm)]
        for item in items:
            product = item.product
            appendix.extend(_technical_card(db, product, item.qty, product.unit, _styles()))

    story = [header, Spacer(1, 4 * mm), details, Spacer(1, 5 * mm), item_table, Spacer(1, 4 * mm),
             _wide_table([[amount, totals]], [96 * mm, 74 * mm], style=[("VALIGN", (0, 0), (-1, -1), "TOP")]),
             Spacer(1, 5 * mm), commercial_terms, Spacer(1, 6 * mm), signatory, *appendix]
    page = lambda canvas, current_doc: commercial_page(canvas, current_doc, "QUOTATION", q.number)
    doc.build(story, onFirstPage=page, onLaterPages=page)
    return buf.getvalue()
