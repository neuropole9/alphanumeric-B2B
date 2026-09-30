from __future__ import annotations



from collections import defaultdict

from datetime import datetime, timezone

from decimal import Decimal

from html import escape

from io import BytesIO

from pathlib import Path

import re

from PIL import Image as PILImage, ImageOps



from openpyxl import Workbook

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from reportlab.lib import colors

from reportlab.lib.enums import TA_CENTER, TA_RIGHT

from reportlab.lib.pagesizes import A4

from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

from reportlab.lib.units import mm

from reportlab.platypus import (

    Image,

    KeepTogether,

    PageBreak,

    Paragraph,

    SimpleDocTemplate,

    Spacer,

    Table,

    TableStyle,

)

from sqlalchemy import desc, or_, select

from sqlalchemy.orm import Session, selectinload



from . import models as m

from .config import settings

from .services import commercial_line

from .media_storage import get_media_provider

from .pdf_format import compact_decimal, inr, percent



NAVY = colors.HexColor(settings.brand_primary)

BLUE = colors.HexColor(settings.brand_accent)

PALE = colors.HexColor("#EEF4FB")

LINE = colors.HexColor("#CBD8E7")

TEXT = colors.HexColor("#17324D")

MUTED = colors.HexColor("#5F738A")

CONTENT_WIDTH = 180 * mm  # A4, 12 mm document margins and 6 pt ReportLab frame padding.







def _normalize_pdf_text(value) -> str:
    """Repair legacy lighting-spec characters before ReportLab renders them."""
    if value is None:
        return ""

    text = str(value)

    # Repair common mojibake / malformed degree symbols.
    text = (
        text
        .replace("Â°", "°")
        .replace("ºC", "°C")
        .replace("Â", "")
    )

    # Repair legacy imported values such as:
    # 15?? / 24?? / 36?? / 50??
    # 45-50??C
    text = re.sub(
        r"(?<=\d)\?{2}(?=\s*(?:/|,|C\b|$))",
        "°",
        text,
    )

    return text




def _text(value, fallback: str = "—") -> str:

    if value is None or value == "":

        return fallback

    shown = _normalize_pdf_text(value).strip()

    return shown if shown else fallback





def _money(value) -> str:

    return inr(value)





def _num(value) -> str:

    return compact_decimal(value)





def _line_values(quantity, product: m.Product) -> dict[str, Decimal]:

    quantity = Decimal(quantity or 0)

    subtotal = (quantity * Decimal(product.price or 0)).quantize(Decimal("0.01"))

    tax = (subtotal * Decimal(product.tax_rate or 0) / Decimal("100")).quantize(Decimal("0.01"))

    return {"subtotal": subtotal, "tax": tax, "total": subtotal + tax}





def _p(value, style) -> Paragraph:

    return Paragraph(escape(_text(value)), style)





def _money_p(value, style) -> Paragraph:

    return Paragraph(escape(_money(value)).replace(" ", "&nbsp;"), style)





def _media_path(product: m.Product):

    """Return exactly one real image for a sellable variant.



    Variant media is authoritative. Family media is only a fallback when it is

    truly family-level (product_id is NULL), preventing a sibling variant's

    image from leaking into this product row.

    """

    def ordered(rows):

        return sorted(

            rows,

            key=lambda item: (

                not bool(item.is_primary),

                int(item.sort_order or 0),

                item.created_at or datetime.min.replace(tzinfo=timezone.utc),

                item.id,

            ),

        )



    exact_variant = ordered([item for item in (product.media or []) if item.archived_at is None])

    family_fallback = ordered([

        item for item in (product.family.media if product.family else [])

        if item.product_id is None and item.archived_at is None

    ])

    root = Path(settings.media_root).expanduser().resolve()

    for media in [*exact_variant, *family_fallback]:

        if media.provider_file_id:

            try:

                return get_media_provider(media.storage_provider).open(media.provider_file_id, media.storage_key)

            except Exception:

                continue

        path = (root / media.storage_key).resolve()

        if (

            root in path.parents

            and path.is_file()

            and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}

        ):

            return path

    return None





def _product_image(product, width=43 * mm, height=43 * mm):

    """Return the selected variant's real image, preserving aspect ratio and orientation."""

    source = _media_path(product)

    if source is None:

        return None

    try:

        with PILImage.open(source) as opened:

            raster = ImageOps.exif_transpose(opened)

            if "A" in raster.getbands():

                alpha = raster.getchannel("A").point(lambda value: 255 if value > 8 else 0)

                bounds = alpha.getbbox()

                if bounds:

                    margin = max(4, int(max(bounds[2] - bounds[0], bounds[3] - bounds[1]) * 0.06))

                    raster = raster.crop((max(0, bounds[0] - margin), max(0, bounds[1] - margin),

                                          min(raster.width, bounds[2] + margin),

                                          min(raster.height, bounds[3] + margin)))

            if raster.mode not in ("RGB", "L"):

                # Flatten transparency onto white for print; do not substitute art.

                rgba = raster.convert("RGBA")

                white = PILImage.new("RGB", rgba.size, "white")

                white.paste(rgba, mask=rgba.getchannel("A"))

                raster = white

            data = BytesIO()

            raster.save(data, format="PNG")

            data.seek(0)

        return Image(data, width=width, height=height, kind="proportional", hAlign="CENTER")

    except (OSError, ValueError):

        return None





def _project_rooms(db: Session, project_id: str, building_id: str | None = None, workspace: str | None = None):

    building_stmt = select(m.Building).where(m.Building.project_id == project_id)

    if building_id:

        building_stmt = building_stmt.where(m.Building.id == building_id)

    buildings = db.scalars(building_stmt.order_by(m.Building.sort_order, m.Building.name)).all()

    result = []

    for building in buildings:

        floors = db.scalars(

            select(m.Floor).where(m.Floor.building_id == building.id).order_by(m.Floor.sort_order, m.Floor.name)

        ).all()

        floor_rows = []

        for floor in floors:

            rooms = db.scalars(

                select(m.Room).where(m.Room.floor_id == floor.id).order_by(m.Room.sort_order, m.Room.name)

            ).all()

            floor_boards = db.scalars(

                select(m.MainBoard).where(m.MainBoard.floor_id == floor.id).order_by(m.MainBoard.sort_order, m.MainBoard.name)

            ).all()

            room_rows = []

            for room in rooms:

                products_stmt = select(m.RoomProduct).join(m.Product).options(

                    selectinload(m.RoomProduct.product).selectinload(m.Product.category),

                    selectinload(m.RoomProduct.product).selectinload(m.Product.family).selectinload(m.ProductFamily.media),

                    selectinload(m.RoomProduct.product).selectinload(m.Product.media),

                ).where(m.RoomProduct.room_id == room.id)

                if workspace:

                    products_stmt = products_stmt.where(m.Product.workspace == workspace)

                products = db.scalars(products_stmt.order_by(m.RoomProduct.created_at)).unique().all()

                items = []

                if products:

                    for row in products:

                        items.append({"id": row.id, "product": row.product, "quantity": Decimal(row.quantity),

                                      "unit": row.unit, "notes": row.notes,

                                      "status": row.approval_status, "source": row.source})

                else:

                    legacy_stmt = select(m.RoomRequirement).join(m.Inquiry).join(m.Product).options(

                        selectinload(m.RoomRequirement.product).selectinload(m.Product.category),

                        selectinload(m.RoomRequirement.product).selectinload(m.Product.family).selectinload(m.ProductFamily.media),

                        selectinload(m.RoomRequirement.product).selectinload(m.Product.media),

                    ).where(m.RoomRequirement.room_id == room.id, m.Inquiry.project_id == project_id)

                    if workspace:

                        legacy_stmt = legacy_stmt.where(m.Inquiry.workspace == workspace, m.Product.workspace == workspace)

                    legacy = db.scalars(legacy_stmt.order_by(desc(m.Inquiry.updated_at), desc(m.RoomRequirement.id))).unique().all()

                    seen: set[str] = set()

                    for row in legacy:

                        if row.product_id in seen:

                            continue

                        seen.add(row.product_id)

                        items.append({"id": row.id, "product": row.product, "quantity": Decimal(row.quantity),

                                      "unit": row.unit, "notes": row.notes, "status": "ADDED", "source": "INQUIRY"})

                room_boards = [board for board in floor_boards if board.room_id == room.id]

                room_rows.append({"room": room, "products": items, "boards": room_boards})

            floor_rows.append({"floor": floor, "rooms": room_rows, "boards": floor_boards})

        boards = db.scalars(

            select(m.MainBoard).where(m.MainBoard.building_id == building.id).order_by(

                m.MainBoard.floor_id, m.MainBoard.sort_order, m.MainBoard.name

            )

        ).all()

        result.append({"building": building, "floors": floor_rows, "boards": boards})

    return result





def _boq(structure) -> list[dict]:

    grouped: dict[str, dict] = {}

    for building_row in structure:

        for floor_row in building_row["floors"]:

            for room_row in floor_row["rooms"]:

                for item in room_row["products"]:

                    product = item["product"]

                    row = grouped.setdefault(product.id, {

                        "product": product, "quantity": Decimal("0"), "unit": item["unit"], "breakdown": []

                    })

                    row["quantity"] += item["quantity"]

                    row["breakdown"].append({"building": building_row["building"].name,

                                             "floor": floor_row["floor"].name,

                                             "room": room_row["room"].name,

                                             "quantity": item["quantity"]})

    return sorted(grouped.values(), key=lambda row: (row["product"].family.name if row["product"].family else row["product"].name,

                                                      row["product"].sku))





def _ordered_specs(db: Session, product: m.Product, visibility: str = "show_in_project_book") -> list[tuple[str, str]]:

    definitions = db.scalars(select(m.ProductSpecDefinition).where(

        m.ProductSpecDefinition.workspace == product.workspace,

        m.ProductSpecDefinition.category_id == product.category_id,

        m.ProductSpecDefinition.status == "ACTIVE",

    ).order_by(m.ProductSpecDefinition.sort_order, m.ProductSpecDefinition.label)).all()

    definitions = [row for row in definitions if row.product_family_id in {None, product.family_id} and getattr(row, visibility, False)]

    values = {row.definition_id: row.value for row in db.scalars(select(m.ProductSpecValue).where(m.ProductSpecValue.product_id == product.id)).all()}

    result: list[tuple[str, str]] = []

    for definition in definitions:

        raw = values.get(definition.id, {}).get("value", (product.specs or {}).get(definition.spec_key))

        if raw in (None, "", []): continue

        if isinstance(raw, list): shown = " / ".join(str(x) for x in raw)

        elif isinstance(raw, dict): shown = " ".join(str(raw.get(x, "")) for x in ("amount", "unit") if raw.get(x) not in (None, ""))

        elif isinstance(raw, bool): shown = "Yes" if raw else "No"

        else: shown = str(raw)

        if definition.unit and definition.unit not in shown: shown = f"{shown} {definition.unit}"

        result.append((definition.label, shown))

    if not definitions:

        result.extend((str(key).replace("_", " ").title(), str(value)) for key, value in (product.specs or {}).items() if value not in (None, "", []))

    return result





# Client-facing technical sheet. The labels and order intentionally mirror the
# approved project-book reference layout.
TECHNICAL_CARD_FIELDS = (
    ("Wattage", ("wattage", "power", "power consumption")),
    ("Input Voltage", ("input voltage", "voltage", "input voltage range")),
    ("CCT", ("cct", "color temperature", "colour temperature")),
    ("CRI", ("cri", "color rendering index")),
    ("Beam Angle", ("beam angle", "beam angles")),
    ("Reflector Colour", ("reflector colour", "reflector color")),
    ("Body Colour", ("body colour", "body color")),
    ("Dimensions", ("dimensions", "dimension", "size")),
    ("Cut-out", ("cut out", "cutout", "cutout size")),
    ("LED Make", ("led make",)),
    ("LED Source", ("led source",)),
    ("Operating Temperature", ("operating temperature", "working temperature")),
    ("Rated Life", ("rated life", "burning hours", "life span", "lifespan")),
    ("IP Rating", ("ip rating", "ip protection")),
    ("Driver", ("driver", "driver make")),
    ("Control Protocols", ("control protocols", "control protocol", "dimming protocol")),
    ("Warranty", ("warranty",)),
    ("Body Material", ("body material", "body materials", "material")),
)

# Kept for the rest of the report renderer, which uses these values in room and
# BOQ summaries.
TECHNICAL_FIELDS = tuple(
    (label, aliases) for label, aliases in TECHNICAL_CARD_FIELDS
    if label not in {"Warranty"}
)


def _spec_key(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()


def _visible_spec_map(db: Session, product: m.Product) -> dict[str, object]:
    visible = {_spec_key(label): value for label, value in _ordered_specs(db, product)}
    for key, value in (product.specs or {}).items():
        if value not in (None, "", []):
            visible.setdefault(_spec_key(key), value)
    return visible


def _technical_details(db: Session, product: m.Product, quantity, unit):
    # Preserve the existing data contract used elsewhere in this module.
    visible = _visible_spec_map(db, product)
    result = [
        ("Product Details", product.family.name if product.family else product.name),
        ("Model", product.model_number or product.variant_name or product.sku),
        ("Quantity", f"{_num(quantity)} {_text(unit, '')}".strip()),
        ("Warranty", product.warranty),
    ]
    for label, aliases in TECHNICAL_FIELDS:
        value = next((visible[_spec_key(alias)] for alias in aliases if _spec_key(alias) in visible), None)
        result.append((label, value))
    return result


def _technical_spec_rows(db: Session, product: m.Product) -> list[tuple[str, object]]:
    """Return the exact right-hand specification rows used by the reference sheet."""
    visible = _visible_spec_map(db, product)
    rows: list[tuple[str, object]] = []
    for label, aliases in TECHNICAL_CARD_FIELDS:
        if label == "Warranty":
            value = product.warranty
            if value in (None, "", "—"):
                value = next((visible[_spec_key(alias)] for alias in aliases if _spec_key(alias) in visible), None)
        else:
            value = next((visible[_spec_key(alias)] for alias in aliases if _spec_key(alias) in visible), None)
        rows.append((label, value if value not in (None, "") else "—"))
    return rows


def _placement_panel(allocations, quantity, unit, styles):
    """Build the PROJECT PLACEMENT block shown under the product identity."""
    rows = []
    for allocation in allocations or []:
        room = _text(allocation.get("room"), "Room")
        qty = allocation.get("quantity", 0)
        allocation_unit = allocation.get("unit") or unit
        rows.append([
            _p(room, styles["placement_room"]),
            _p(f"{_num(qty)} {_text(allocation_unit, '')}".strip(), styles["placement_qty"]),
        ])

    if not rows:
        rows.append([_p("Project", styles["placement_room"]),
                     _p(f"{_num(quantity)} {_text(unit, '')}".strip(), styles["placement_qty"])])

    rows.append([_p("Total", styles["placement_room"]),
                 _p(f"{_num(quantity)} {_text(unit, '')}".strip(), styles["placement_qty"])])

    table = Table(rows, colWidths=[27 * mm, 17 * mm], hAlign="CENTER")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2.0 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
    ]))

    body = Table([
        [_p("PROJECT PLACEMENT", styles["placement_heading"])],
        [table],
    ], colWidths=[44 * mm])
    body.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EEF5FC")),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 0), (-1, 0), 3 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 1 * mm),
        ("TOPPADDING", (0, 1), (-1, 1), 0),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 2 * mm),
    ]))
    return body


def _technical_card(db, product, quantity, unit, styles, allocations=None):
    """Render one product exactly in the approved image-2 technical-sheet layout.

    Left: product image, series/product title, model/SKU and project placement.
    Right: fixed ordered specification table with pale-blue labels and ruled rows.
    """
    family = product.family.name if product.family else product.name
    model = product.model_number or product.variant_name or product.sku

    picture = _product_image(product, 39 * mm, 39 * mm)
    if picture is None:
        picture = _p("Product image not available", styles["missing_image"])

    image_box = Table([[picture]], colWidths=[44 * mm], rowHeights=[45 * mm])
    image_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    placement = _placement_panel(allocations, quantity, unit, styles)
    left_panel = Table([
        [image_box],
        [_p(family, styles["tech_product_name"])],
        [_p(model, styles["tech_model"])],
        [Spacer(1, 9 * mm)],
        [placement],
    ], colWidths=[50 * mm])
    left_panel.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFD")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
        ("TOPPADDING", (0, 1), (-1, 2), 3 * mm),
        ("BOTTOMPADDING", (0, 1), (-1, 2), 0),
        ("TOPPADDING", (0, 3), (-1, 3), 0),
        ("BOTTOMPADDING", (0, 3), (-1, 3), 0),
        ("TOPPADDING", (0, 4), (-1, 4), 0),
    ]))

    spec_rows = _technical_spec_rows(db, product)
    spec_table = Table(
        [[_p(label, styles["tech_label"]), _p(value, styles["tech_value"])] for label, value in spec_rows],
        colWidths=[35 * mm, 95 * mm],
        hAlign="LEFT",
    )
    spec_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF5FC")),
        ("BACKGROUND", (1, 0), (1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.55, NAVY),
        ("INNERGRID", (0, 0), (-1, -1), 0.32, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2.5 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2.5 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 2.0 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.0 * mm),
    ]))

    card = Table([[left_panel, spec_table]], colWidths=[50 * mm, 130 * mm], hAlign="LEFT")
    card.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.55, NAVY),
        ("LINEAFTER", (0, 0), (0, 0), 0.45, LINE),
        ("VALIGN", (0, 0), (0, 0), "TOP"),
        ("VALIGN", (1, 0), (1, 0), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return KeepTogether([card, Spacer(1, 5 * mm)])


def _wide_table(data, widths, **kwargs):

    """Scale a table's columns to the shared 180 mm content edge."""

    total = sum(widths)

    return Table(data, colWidths=[width * CONTENT_WIDTH / total for width in widths], **kwargs)





def _styles():

    base = getSampleStyleSheet()

    return {

        "title": ParagraphStyle("book-title", parent=base["Title"], fontName="Helvetica-Bold",

                                fontSize=27, leading=32, textColor=colors.white, alignment=TA_CENTER,

                                spaceAfter=5 * mm),

        "cover_sub": ParagraphStyle("cover-sub", parent=base["Normal"], fontSize=11, leading=16,

                                    textColor=colors.HexColor("#DCE9F8"), alignment=TA_CENTER),

        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=18,

                             leading=22, textColor=NAVY, spaceAfter=4 * mm),

        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12,

                             leading=15, textColor=colors.white, backColor=NAVY,

                             borderPadding=(3 * mm, 0, 3 * mm, 0), spaceBefore=3 * mm, spaceAfter=3 * mm),

        "h3": ParagraphStyle("h3", parent=base["Heading3"], fontName="Helvetica-Bold", fontSize=10,

                             leading=13, textColor=NAVY, spaceBefore=2 * mm, spaceAfter=2 * mm),

        "body": ParagraphStyle("body", parent=base["BodyText"], fontSize=8.2, leading=11, textColor=TEXT),

        "small": ParagraphStyle("small", parent=base["BodyText"], fontSize=7, leading=9, textColor=MUTED),

        "cell": ParagraphStyle("cell", parent=base["BodyText"], fontSize=6.7, leading=8.5, textColor=TEXT),

        "cell_right": ParagraphStyle("cell-right", parent=base["BodyText"], fontSize=6.7, leading=8.5,

                                     textColor=TEXT, alignment=TA_RIGHT),

        "header_cell": ParagraphStyle("header-cell", parent=base["BodyText"], fontName="Helvetica-Bold",

                                      fontSize=6.7, leading=8.2, textColor=colors.white),

        "product_name": ParagraphStyle(

            "product-name",

            parent=base["BodyText"],

            fontName="Helvetica-Bold",

            fontSize=9.2,

            leading=11.2,

            textColor=NAVY,

        ),

        "product_meta": ParagraphStyle(

            "product-meta",

            parent=base["BodyText"],

            fontSize=6.8,

            leading=8.4,

            textColor=MUTED,

        ),

        "product_spec": ParagraphStyle(

            "product-spec",

            parent=base["BodyText"],

            fontSize=7.1,

            leading=9.0,

            textColor=TEXT,

        ),

        "tech_title": ParagraphStyle("tech-title", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=10, leading=12, textColor=NAVY),

        "tech_meta": ParagraphStyle("tech-meta", parent=base["BodyText"], fontSize=7.2, leading=9, textColor=MUTED),

        "tech_product_name": ParagraphStyle("tech-product-name", parent=base["BodyText"],
                                             fontName="Helvetica-Bold", fontSize=12.6, leading=15,
                                             textColor=NAVY, alignment=TA_CENTER),

        "tech_model": ParagraphStyle("tech-model", parent=base["BodyText"], fontSize=7.8, leading=10,
                                      textColor=MUTED, alignment=TA_CENTER),

        "tech_label": ParagraphStyle("tech-label", parent=base["BodyText"], fontSize=7.7, leading=9.6,
                                      textColor=colors.HexColor("#6780A0")),

        "tech_value": ParagraphStyle("tech-value", parent=base["BodyText"], fontSize=8.2, leading=10.2, textColor=TEXT),

        "placement_heading": ParagraphStyle("placement-heading", parent=base["BodyText"],
                                             fontName="Helvetica-Bold", fontSize=7.4, leading=9, textColor=NAVY),

        "placement_room": ParagraphStyle("placement-room", parent=base["BodyText"], fontSize=7.2, leading=9, textColor=TEXT),

        "placement_qty": ParagraphStyle("placement-qty", parent=base["BodyText"], fontSize=7.2, leading=9,
                                         textColor=TEXT, alignment=TA_RIGHT),

        "missing_image": ParagraphStyle("missing-image", parent=base["BodyText"], fontSize=5.8, leading=7,

                                         textColor=MUTED, alignment=TA_CENTER),

        "kpi": ParagraphStyle("kpi", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=16,

                              leading=18, textColor=NAVY, alignment=TA_CENTER),

        "kpi_label": ParagraphStyle("kpi-label", parent=base["BodyText"], fontSize=6.8, leading=8,

                                    textColor=MUTED, alignment=TA_CENTER),

    }





def _page_frame(canvas, doc, project_name: str):

    width, height = A4

    canvas.saveState()

    if doc.page == 1:

        canvas.restoreState()

        return

    canvas.setFillColor(NAVY)

    canvas.rect(12 * mm, height - 19 * mm, width - 24 * mm, 9 * mm, stroke=0, fill=1)

    canvas.setStrokeColor(LINE)

    canvas.setLineWidth(0.4)

    canvas.line(12 * mm, 16 * mm, width - 12 * mm, 16 * mm)

    canvas.setFillColor(colors.white)

    canvas.setFont("Helvetica-Bold", 8)

    canvas.drawString(15 * mm, height - 16 * mm, settings.company_name)

    canvas.setFont("Helvetica", 6.8)

    canvas.drawRightString(width - 15 * mm, height - 16 * mm, project_name[:60])

    generated = datetime.now(timezone.utc).strftime("Generated %d %b %Y")

    canvas.setFillColor(MUTED)

    canvas.drawString(15 * mm, 11.5 * mm, generated)

    canvas.drawRightString(width - 15 * mm, 11.5 * mm, f"Page {doc.page}")

    canvas.restoreState()





def _info_table(rows: list[tuple[str, object]], styles, widths=(47 * mm, 133 * mm)):

    data = [[_p(label, styles["small"]), _p(value, styles["body"])] for label, value in rows]

    table = _wide_table(data, list(widths), hAlign="LEFT")

    table.setStyle(TableStyle([

        ("VALIGN", (0, 0), (-1, -1), "TOP"),

        ("LEFTPADDING", (0, 0), (-1, -1), 3),

        ("RIGHTPADDING", (0, 0), (-1, -1), 3),

        ("TOPPADDING", (0, 0), (-1, -1), 2),

        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),

    ]))

    return table





def _render_project_book_pdf(db: Session, project: m.Project, include_prices: bool, building_id: str | None = None, workspace: str | None = None) -> bytes:

    structure = _project_rooms(db, project.id, building_id, workspace)

    if building_id and not structure:

        raise ValueError("Building not found in this project")

    styles = _styles()

    selected_building = structure[0]["building"] if building_id and len(structure) == 1 else None

    label = selected_building.name if selected_building else project.name

    buffer = BytesIO()

    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=12 * mm, leftMargin=12 * mm,

                            topMargin=24 * mm, bottomMargin=21 * mm,

                            title=f"{label} {'Building' if selected_building else 'Project'} Book",

                            author=settings.company_name)

    story = []



    # Cover page.

    story.append(Spacer(1, 34 * mm))

    cover_box = []

    logo = Path(settings.company_logo_path).expanduser() if settings.company_logo_path else None

    if logo and logo.is_file():

        cover_box.append(Image(str(logo), width=42 * mm, height=18 * mm, kind="proportional"))

        cover_box.append(Spacer(1, 7 * mm))

    cover_box.extend([

        Paragraph(escape(settings.company_name), styles["title"]),

        Paragraph("PROJECT CONFIGURATION BOOK", styles["cover_sub"]),

        Spacer(1, 18 * mm),

        Paragraph(escape(label), styles["title"]),

        Paragraph(f"Prepared for: <b>{escape(project.customer.company_name)}</b><br/>"

                  f"{escape(_text(selected_building.address if selected_building and selected_building.address else project.address))}<br/>"

                  f"{escape(', '.join(x for x in [project.city, project.state] if x) or 'Location not provided')}", styles["cover_sub"]),

        Spacer(1, 18 * mm),

        Paragraph(f"Generated: {datetime.now(timezone.utc).strftime('%d %B %Y')}", styles["cover_sub"]),

    ])

    cover = Table([[cover_box]], colWidths=[CONTENT_WIDTH], rowHeights=[212 * mm])

    cover.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY),

                               ("LINEBELOW", (0, 0), (-1, -1), 1, BLUE),

                               ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

                               ("ALIGN", (0, 0), (-1, -1), "CENTER"),

                               ("LEFTPADDING", (0, 0), (-1, -1), 15 * mm),

                               ("RIGHTPADDING", (0, 0), (-1, -1), 15 * mm)]))

    story.extend([cover, PageBreak()])



    inquiry_stmt = select(m.Inquiry).where(m.Inquiry.project_id == project.id)

    if workspace:

        inquiry_stmt = inquiry_stmt.where(m.Inquiry.workspace == workspace)

    if selected_building:

        inquiry_stmt = inquiry_stmt.where(or_(m.Inquiry.building_id == selected_building.id, m.Inquiry.is_project_wide.is_(True)))

    inquiries = db.scalars(inquiry_stmt.order_by(desc(m.Inquiry.created_at))).all()

    primary_inquiry = inquiries[0] if inquiries else None

    story.append(Paragraph("Inquiry, Customer & Partner Information", styles["h1"]))

    story.append(Paragraph("Inquiry Information", styles["h2"]))

    story.append(_info_table([

        ("Project name", project.name),

        ("Building / tower", selected_building.name if selected_building else "Project-wide / multiple buildings"),

        ("Customer / client", project.customer.company_name),

        ("Contact person", project.customer.contact_person),

        ("Phone", project.customer.phone),

        ("Email", project.customer.email),

        ("Inquiry number", primary_inquiry.number if primary_inquiry else "No inquiry recorded"),

        ("Site location", ", ".join(x for x in [project.address, project.city, project.state] if x)),

        ("Internal owner", project.owner.name if project.owner else "Not assigned"),

        ("Status", project.status),

        ("Application", workspace or "All authorized applications"),

    ], styles))

    story.append(Paragraph("Partner Information", styles["h2"]))

    if project.partner:

        story.append(_info_table([

            ("Business name", project.partner.business_name),

            ("Mobile", project.partner.mobile),

            ("Email", project.partner.email),

            ("Address", project.partner.address),

        ], styles))

    else:

        story.append(_info_table([("Partner", "No Partner Assigned")], styles))

    documents_stmt = select(m.ProjectDocument).where(

        m.ProjectDocument.project_id == project.id, m.ProjectDocument.status == "ACTIVE"

    )

    if selected_building:

        documents_stmt = documents_stmt.where(or_(

            m.ProjectDocument.building_id == selected_building.id,

            m.ProjectDocument.building_id.is_(None),

        ))

    documents = db.scalars(documents_stmt.order_by(m.ProjectDocument.document_type, m.ProjectDocument.title)).all()

    building_names = {row["building"].id: row["building"].name for row in structure}

    floor_names = {floor_row["floor"].id: floor_row["floor"].name for row in structure for floor_row in row["floors"]}

    room_names = {room_row["room"].id: room_row["room"].name for row in structure for floor_row in row["floors"] for room_row in floor_row["rooms"]}

    story.append(Paragraph("Plan & Document Register", styles["h2"]))

    document_rows = [["Type", "Title", "Revision", "Scope", "File"]]

    for item in documents:

        scope = room_names.get(item.room_id) or floor_names.get(item.floor_id) or building_names.get(item.building_id) or "Project"

        document_rows.append([item.document_type, item.title, item.revision, scope, item.file_name])

    if len(document_rows) == 1:

        story.append(Paragraph("No plans or documents uploaded.", styles["body"]))

    else:

        document_data = [[_p(cell, styles["header_cell"]) for cell in document_rows[0]]]

        document_data += [[_p(cell, styles["cell"]) for cell in row] for row in document_rows[1:]]

        document_table = _wide_table(document_data,

                               widths=[28 * mm, 50 * mm, 18 * mm, 35 * mm, 40 * mm], repeatRows=1)

        document_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY),

                                            ("VALIGN", (0, 0), (-1, -1), "TOP")]))

        story.append(document_table)

    root = Path(settings.media_root).expanduser().resolve()

    for item in documents:

        if item.mime_type not in {"image/png", "image/jpeg"}:

            continue

        path = (root / item.storage_key).resolve()

        if root in path.parents and path.is_file():

            story.extend([Spacer(1, 4 * mm), Paragraph(escape(f"{item.document_type} · {item.title} · Rev {item.revision}"), styles["h2"]),

                          Image(str(path), width=160 * mm, height=100 * mm, kind="proportional")])

    story.append(PageBreak())



    boq = _boq(structure)

    floors_count = sum(len(row["floors"]) for row in structure)

    rooms_count = sum(len(floor["rooms"]) for row in structure for floor in row["floors"])

    board_count = sum(sum(board.quantity for board in row["boards"]) for row in structure)

    quantity = sum((row["quantity"] for row in boq), Decimal("0"))

    story.append(Paragraph("Project / System Summary", styles["h1"]))

    kpi_table = _wide_table([

        [_p(_num(value), styles["kpi"]) for value, _ in [(len(structure), ""), (floors_count, ""), (rooms_count, ""), (board_count, ""), (len(boq), ""), (quantity, "")]],

        [_p(label, styles["kpi_label"]) for label in ["Buildings", "Floors", "Rooms", "Main Boards", "Unique Products", "Total Quantity"]],

    ], widths=[28.3 * mm] * 6)

    kpi_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE),

                                   ("LINEBELOW", (0, 0), (-1, -1), 0.35, LINE),

                                   ("LINEBELOW", (0, 0), (-1, -1), 0.25, LINE),

                                   ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))

    story.extend([kpi_table, Spacer(1, 4 * mm), Paragraph("System Scope", styles["h2"]),

                  _info_table([("Workspaces / systems", " · ".join(project.workspace_scope or ["Not provided"])),

                               ("Project / building", label), ("Last updated", _text(project.updated_at or project.created_at))], styles),

                  Paragraph("Main Board Details", styles["h2"])])

    board_rows = [["Building", "Floor", "Room / Scope", "Main Board", "Code", "Type / Model / Description", "System", "Qty"]]

    for building_row in structure:

        floor_names = {floor_row["floor"].id: floor_row["floor"].name for floor_row in building_row["floors"]}

        room_names = {room_row["room"].id: room_row["room"].name for floor_row in building_row["floors"] for room_row in floor_row["rooms"]}

        for board in building_row["boards"]:

            type_description = board.board_type

            if board.notes:

                type_description = f"{type_description} · {board.notes}"

            board_rows.append([

                building_row["building"].name,

                floor_names.get(board.floor_id, "—"),

                room_names.get(board.room_id, "Floor / shared scope"),

                board.name,

                _text(board.code),

                type_description,

                board.system,

                board.quantity,

            ])

    if len(board_rows) == 1:

        story.append(Paragraph("No main boards configured for this project.", styles["body"]))

    else:

        board_data = [[_p(cell, styles["header_cell"]) for cell in board_rows[0]]]

        board_data += [[_p(cell, styles["cell"]) for cell in row] for row in board_rows[1:]]

        board_table = _wide_table(

            board_data, widths=[22 * mm, 20 * mm, 22 * mm, 24 * mm, 17 * mm, 31 * mm, 18 * mm, 10 * mm], repeatRows=1)

        board_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY),

                                         ("VALIGN", (0, 0), (-1, -1), "TOP"),

                                         ("TOPPADDING", (0, 0), (-1, -1), 4),

                                         ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))

        story.append(board_table)

    story.append(PageBreak())



    # Complete floor overviews followed by one room section per room.

    for building_row in structure:

        building = building_row["building"]

        for floor_row in building_row["floors"]:

            floor = floor_row["floor"]

            rooms = floor_row["rooms"]

            story.append(Paragraph(f"{escape(building.name)} · {escape(floor.name)} — Complete Floor View", styles["h1"]))

            floor_qty = sum((sum((item["quantity"] for item in room["products"]), Decimal("0")) for room in rooms), Decimal("0"))

            story.append(_info_table([("Building", building.name), ("Floor", floor.name),

                                      ("Total rooms", len(rooms)),

                                      ("Product quantity", _num(floor_qty)),

                                      ("Main boards", sum(board.quantity for board in floor_row["boards"]))], styles))

            story.append(Spacer(1, 3 * mm))

            rows = [["#", "Room", "Products", "Qty", "Main Boards", "Status"]]

            for index, room_row in enumerate(rooms, 1):

                room = room_row["room"]

                room_qty = sum((item["quantity"] for item in room_row["products"]), Decimal("0"))

                rows.append([index, room.name, len(room_row["products"]), _num(room_qty),

                             sum(board.quantity for board in room_row["boards"]),

                             "Configured" if room_row["products"] else "Not configured"])

            floor_data = [[_p(cell, styles["header_cell"]) for cell in rows[0]]]

            floor_data += [[_p(cell, styles["cell"]) for cell in row] for row in rows[1:]]

            floor_table = _wide_table(floor_data,

                                widths=[10 * mm, 68 * mm, 25 * mm, 20 * mm, 27 * mm, 30 * mm], repeatRows=1)

            floor_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),

                                             ("VALIGN", (0, 0), (-1, -1), "TOP"),

                                             ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),

                                             ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))

            story.extend([floor_table, PageBreak()])



            for room_row in rooms:

                room = room_row["room"]

                story.append(Paragraph(f"{escape(building.name)} / {escape(floor.name)} / {escape(room.name)}", styles["h1"]))

                story.append(Paragraph("Room Product Schedule", styles["h2"]))

                if not room_row["products"]:

                    story.append(Paragraph("No products configured for this room.", styles["body"]))

                else:

                    for item_index, item in enumerate(room_row["products"]):

                        if item_index:
                            story.append(PageBreak())

                            story.append(Paragraph(
                                f"{escape(building.name)} / {escape(floor.name)} / {escape(room.name)}",
                                styles["h1"],
                            ))

                            story.append(Paragraph("Room Product Schedule", styles["h2"]))

                        room_allocation = [{
                            "room": room.name,
                            "quantity": item["quantity"],
                            "unit": item["unit"],
                        }]

                        story.append(_technical_card(
                            db, item["product"], item["quantity"], item["unit"], styles,
                            allocations=room_allocation,
                        ))

                story.append(PageBreak())



    story.append(Paragraph("Aggregated Bill of Quantities", styles["h1"]))

    if include_prices:

        story.append(Paragraph("BOQ rates use current catalogue pricing. Saved quotations at the end contain the agreed commercial snapshots.", styles["small"]))

    headers = ["Product Details", "Model Number", "Voltage", "Quantity", "Unit", "Rate", "Total"] if include_prices else [

        "Product Details", "Model Number", "Voltage", "Quantity", "Unit"]

    widths = [54 * mm, 28 * mm, 27 * mm, 16 * mm, 15 * mm, 21 * mm, 19 * mm] if include_prices else [

        69 * mm, 38 * mm, 34 * mm, 21 * mm, 18 * mm]

    rows = [[_p(value, styles["header_cell"]) for value in headers]]

    subtotal = Decimal("0")

    tax_total = Decimal("0")

    for item in boq:

        product = item["product"]

        spec_values = {_spec_key(label): value for label, value in _ordered_specs(db, product)}

        for key, value in (product.specs or {}).items():

            if value not in (None, "", []):

                spec_values.setdefault(_spec_key(key), value)

        voltage = next((spec_values[_spec_key(key)] for key in ("input voltage", "voltage", "input voltage range")

                        if _spec_key(key) in spec_values), None)

        row = [_p(product.family.name if product.family else product.name, styles["cell"]),

               _p(product.model_number or product.variant_name or product.sku, styles["cell"]),

               _p(voltage, styles["cell"]), _p(_num(item["quantity"]), styles["cell_right"]),

               _p(item["unit"], styles["cell"])]

        if include_prices:

            calculated = _line_values(item["quantity"], product)

            subtotal += calculated["subtotal"]

            tax_total += calculated["tax"]

            row += [_money_p(product.price, styles["cell_right"]),

                    _money_p(calculated["subtotal"], styles["cell_right"])]

        rows.append(row)

    if len(rows) == 1:

        rows.append([_p("No products configured", styles["cell"])] + [_p("—", styles["cell"])] * (len(headers) - 1))

    boq_table = _wide_table(rows, widths, repeatRows=1)

    boq_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),

                                   ("LINEBELOW", (0, 0), (-1, -1), 0.35, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),

                                   ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),

                                   ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))

    story.append(boq_table)

    if include_prices:

        financial = [("Subtotal Before Tax", _money(subtotal)), ("Discount", _money(0)),

                     ("Taxable Value", _money(subtotal))]

        financial.append(("Indicative Tax", _money(tax_total)))

        grand_total = subtotal + tax_total

        rounded = grand_total.quantize(Decimal("1"))

        financial.extend([("Round Off", _money(rounded - grand_total)), ("Grand Total", _money(rounded))])

        story.extend([Spacer(1, 3 * mm), Paragraph("BOQ Financial Summary", styles["h2"]), _info_table(financial, styles)])

        if boq and all(Decimal(item["product"].price or 0) == 0 for item in boq):

            story.append(Paragraph("Pricing is pending; review rates before sharing this book with a client.", styles["small"]))

    story.append(PageBreak())



    if boq:

        story.append(Paragraph("Product Technical Specifications", styles["h1"]))

        for product_index, item in enumerate(boq):

            if product_index:

                story.append(PageBreak())

                story.append(Paragraph("Product Technical Specifications", styles["h1"]))

            allocations = [
                {
                    "room": allocation["room"],
                    "quantity": allocation["quantity"],
                    "unit": item["unit"],
                }
                for allocation in item.get("breakdown", [])
            ]

            story.append(_technical_card(
                db, item["product"], item["quantity"], item["unit"], styles,
                allocations=allocations,
            ))

        story.append(PageBreak())



    # Actual quotation snapshots follow the product book. Never recalculate a

    # saved quotation from today's catalogue prices: revisions may differ.

    quote_stmt = select(m.Quotation).where(m.Quotation.inquiry_id.in_([row.id for row in inquiries]))

    if workspace:

        quote_stmt = quote_stmt.where(m.Quotation.workspace == workspace)

    if selected_building:

        quote_stmt = quote_stmt.where(or_(m.Quotation.building_id == selected_building.id,

                                         m.Quotation.building_id.is_(None)))

    quotes = db.scalars(quote_stmt.order_by(m.Quotation.quotation_date, m.Quotation.number)).all() if inquiries else []

    orders = db.scalars(select(m.Order).where(m.Order.quotation_id.in_([row.id for row in quotes])).order_by(m.Order.order_date)).all() if quotes else []

    invoices = db.scalars(select(m.Invoice).where(m.Invoice.order_id.in_([row.id for row in orders])).order_by(m.Invoice.invoice_date)).all() if orders else []

    story.append(Paragraph("Commercial Documents", styles["h1"]))

    if orders or invoices:

        story.append(Paragraph("Orders and invoices", styles["h2"]))

        for kind, entries, date_field in (("Order", orders, "order_date"), ("Invoice", invoices, "invoice_date")):

            for entry in entries:

                info = f"{kind} {entry.number}  /  {getattr(entry, date_field)}  /  {entry.status}"

                if include_prices:

                    info += f"  /  {_money(entry.grand_total)}"

                story.append(Paragraph(escape(info), styles["body"]))

        story.append(Spacer(1, 5 * mm))

    if not quotes:

        story.append(Paragraph("No quotation has been recorded for this scope.", styles["body"]))

    for index, quote in enumerate(quotes):

        if index:

            story.append(PageBreak())

        story.append(Paragraph(f"Quotation {escape(_text(quote.number))}  /  Revision {quote.revision}", styles["h1"]))

        if quote.status == "DRAFT":

            story.append(Paragraph("DRAFT quotation - review and approve before sending to the client.", styles["body"]))

        story.append(_info_table([

            ("Date", quote.quotation_date), ("Status", quote.status),

            ("Valid until", quote.valid_until),

            ("Customer", project.customer.company_name),

            ("Inquiry", quote.inquiry.number if quote.inquiry else ""),

        ], styles))

        story.append(Spacer(1, 4 * mm))

        quote_items = db.scalars(select(m.QuotationItem).where(m.QuotationItem.quotation_id == quote.id)

                                 .order_by(m.QuotationItem.id)).all()

        if quote_items:

            cols = ["Product Details", "Model / SKU", "Quantity"]

            widths = [75, 53, 22]

            if include_prices:

                cols += ["Rate", "Amount"]

                widths += [24, 26]

            data = [[_p(label, styles["header_cell"]) for label in cols]]

            for line in quote_items:

                line_cells = [_p(line.description, styles["cell"]), _p(line.sku, styles["cell"]),

                              _p(_num(line.qty), styles["cell_right"])]

                if include_prices:

                    line_cells += [_money_p(line.rate, styles["cell_right"]),

                                   _money_p(line.amount, styles["cell_right"])]

                data.append(line_cells)

            quotation_table = _wide_table(data, widths, repeatRows=1)

            quotation_table.setStyle(TableStyle([

                ("BACKGROUND", (0, 0), (-1, 0), NAVY),

                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),

                ("VALIGN", (0, 0), (-1, -1), "TOP"),

                ("TOPPADDING", (0, 0), (-1, -1), 5),

                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),

            ]))

            story.append(quotation_table)

        else:

            story.append(Paragraph("No line items in this quotation.", styles["body"]))

        if include_prices:

            story.extend([Spacer(1, 3 * mm), Paragraph("Quotation Totals", styles["h2"]),

                          _info_table([("Subtotal", _money(quote.subtotal)),

                                       ("Discount", _money(quote.discount_amount)),

                                       ("Tax", _money(quote.tax_total)),

                                       ("Grand Total", _money(quote.grand_total))], styles)])

        terms = [("Payment terms", quote.payment_terms), ("Delivery terms", quote.delivery_terms),

                 ("Warranty terms", quote.warranty_terms), ("Notes", quote.notes)]

        terms = [(key, value) for key, value in terms if value]

        if terms:

            story.extend([Spacer(1, 3 * mm), Paragraph("Terms", styles["h2"]), _info_table(terms, styles)])

    doc.build(story, onFirstPage=lambda canvas, document: _page_frame(canvas, document, project.name),

              onLaterPages=lambda canvas, document: _page_frame(canvas, document, project.name))

    return buffer.getvalue()







def project_book_pdf(

    db: Session,

    project: m.Project,

    include_prices: bool,

    building_id: str | None = None,

    workspace: str | None = None,

) -> bytes:

    """Download renderer. Uses the exact reference Project Book layout."""

    return _render_project_book_pdf(

        db,

        project,

        include_prices,

        building_id=building_id,

        workspace=workspace,

    )





def project_book_preview_pdf(

    db: Session,

    project: m.Project,

    include_prices: bool,

    building_id: str | None = None,

    workspace: str | None = None,

) -> bytes:

    """Preview renderer. Byte-identical to the downloaded PDF."""

    return _render_project_book_pdf(

        db,

        project,

        include_prices,

        building_id=building_id,

        workspace=workspace,

    )





def room_sheet_pdf(db: Session, room: m.Room, include_prices: bool, workspace: str | None = None) -> bytes:

    project = room.floor.building.project

    # The complete book generator already produces rigorously paginated room sections.

    # A room sheet uses a small temporary structure by reusing the same source records.

    structure = _project_rooms(db, project.id, room.floor.building_id, workspace)

    styles = _styles()

    room_row = next((rr for br in structure for fr in br["floors"] for rr in fr["rooms"] if rr["room"].id == room.id), None)

    if not room_row:

        raise ValueError("Room not found")

    buffer = BytesIO()

    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=12 * mm, leftMargin=12 * mm,

                            topMargin=24 * mm, bottomMargin=21 * mm,

                            title=f"{room.name} Room Sheet", author=settings.company_name)

    story = [Paragraph(f"Room Configuration Sheet · {escape(room.name)}", styles["h1"]),

             _info_table([("Customer", project.customer.company_name), ("Project", project.name),

                          ("Building", room.floor.building.name), ("Floor", room.floor.name),

                          ("Room type", room.room_type), ("Area", room.area),

                          ("Occupancy", room.occupancy), ("Notes", room.notes)], styles),

             Paragraph("Main Boards", styles["h2"])]

    boards = room_row["boards"]

    story.append(_info_table([("Boards", ", ".join(f"{b.name} ({b.board_type}) × {b.quantity}" for b in boards) if boards else "No main boards configured")], styles))

    story.append(Paragraph("Complete Product List", styles["h2"]))

    headers = ["Image", "Product / exact model", "Model No.", "SKU", "Key specifications", "Qty", "Unit", "Placement / notes"]

    widths = [15 * mm, 30 * mm, 22 * mm, 23 * mm, 38 * mm, 11 * mm, 12 * mm, 19 * mm]

    if include_prices:

        headers += ["Rate", "Tax", "Line total"]

        widths = [12 * mm, 24 * mm, 18 * mm, 20 * mm, 27 * mm, 9 * mm, 9 * mm, 14 * mm, 15 * mm, 8 * mm, 20 * mm]

    rows = [[_p(value, styles["header_cell"]) for value in headers]]

    for item in room_row["products"]:

        product = item["product"]

        media = _media_path(product)

        image = Image(media, width=11 * mm, height=11 * mm, kind="proportional") if media else _p("Unavailable", styles["missing_image"])

        family_name = product.family.name if product.family else product.name

        exact_model = " / ".join(filter(None, [product.variant_name or product.name, product.model_number]))

        key_specs = "; ".join(f"{label}: {_text(value)}" for label, value in _technical_details(db, product, item["quantity"], item["unit"])[4:7])

        row = [image, _p(family_name, styles["cell"]), _p(product.model_number or exact_model, styles["cell"]),

               _p(product.sku, styles["cell"]), _p(key_specs, styles["cell"]),

               _p(_num(item["quantity"]), styles["cell_right"]), _p(item["unit"], styles["cell"]),

               _p(item.get("notes") or "—", styles["cell"])]

        if include_prices:

            calculated = commercial_line(item["quantity"], product.price, product.tax_rate)

            row += [_p(_money(product.price), styles["cell_right"]), _p(f"{_num(product.tax_rate)}%", styles["cell_right"]),

                    _p(_money(calculated["total"]), styles["cell_right"])]

        rows.append(row)

    if len(rows) == 1:

        rows.append([_p("No products configured", styles["cell"])] + [_p("—", styles["cell"])] * (len(headers) - 1))

    table = _wide_table(rows, widths, repeatRows=1)

    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),

                               ("LINEBELOW", (0, 0), (-1, -1), 0.35, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),

                               ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))

    story.append(table)

    if room_row["products"]:

        story.extend([PageBreak(), Paragraph("Product Technical Specifications", styles["h1"])])

    for item_index, item in enumerate(room_row["products"]):

        if item_index:

            story.append(PageBreak())

            story.append(Paragraph("Product Technical Specifications", styles["h1"]))

        story.append(_technical_card(
            db, item["product"], item["quantity"], item["unit"], styles,
            allocations=[{
                "room": room.name,
                "quantity": item["quantity"],
                "unit": item["unit"],
            }],
        ))

    doc.build(story, onFirstPage=lambda canvas, document: _page_frame(canvas, document, project.name),

              onLaterPages=lambda canvas, document: _page_frame(canvas, document, project.name))

    return buffer.getvalue()





def floor_sheet_pdf(db: Session, floor: m.Floor, include_prices: bool, workspace: str | None = None) -> bytes:

    project = floor.building.project

    structure = _project_rooms(db, project.id, floor.building_id, workspace)

    floor_row = next((fr for br in structure for fr in br["floors"] if fr["floor"].id == floor.id), None)

    if not floor_row:

        raise ValueError("Floor not found")

    styles = _styles(); buffer = BytesIO()

    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=12 * mm, leftMargin=12 * mm,

                            topMargin=24 * mm, bottomMargin=21 * mm,

                            title=f"{floor.name} Floor Sheet", author=settings.company_name)

    rooms = floor_row["rooms"]

    story = [Paragraph(f"Floor Configuration Sheet · {escape(floor.name)}", styles["h1"]),

             _info_table([("Customer", project.customer.company_name), ("Project", project.name),

                          ("Building", floor.building.name), ("Floor", floor.name),

                          ("Rooms", len(rooms)),

                          ("Configured products", sum(len(room["products"]) for room in rooms))], styles),

             Paragraph("Room Schedule", styles["h2"])]

    rows = [["Room", "Type", "Boards", "Products", "Quantity", "Status"]]

    for room_row in rooms:

        room = room_row["room"]; products = room_row["products"]

        rows.append([room.name, room.room_type or "—", sum(board.quantity for board in room_row["boards"]),

                     len(products), _num(sum((item["quantity"] for item in products), Decimal("0"))),

                     "CONFIGURED" if products else "NOT CONFIGURED"])

    if len(rows) == 1:

        rows.append(["No active rooms", "—", "—", "—", "—", "—"])

    table_data = [[_p(cell, styles["header_cell"]) for cell in rows[0]]]

    table_data += [[_p(cell, styles["cell"]) for cell in row] for row in rows[1:]]

    table = _wide_table(table_data,

                  widths=[40 * mm, 38 * mm, 24 * mm, 24 * mm, 24 * mm, 30 * mm], repeatRows=1)

    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),

                               ("LINEBELOW", (0, 0), (-1, -1), 0.35, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),

                               ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))

    story.append(table)

    doc.build(story, onFirstPage=lambda canvas, document: _page_frame(canvas, document, project.name),

              onLaterPages=lambda canvas, document: _page_frame(canvas, document, project.name))

    return buffer.getvalue()





def building_boq_xlsx(db: Session, project: m.Project, building_id: str | None, include_prices: bool, workspace: str | None = None) -> bytes:

    structure = _project_rooms(db, project.id, building_id, workspace)

    if not structure:

        raise ValueError("No configured buildings were found in this project")

    building = structure[0]["building"] if building_id else None

    scope_name = building.name if building else "All Buildings"

    rows = _boq(structure)

    workbook = Workbook()

    sheet = workbook.active

    sheet.title = "Building BOQ" if building else "Project BOQ"

    sheet.sheet_view.showGridLines = False

    sheet.append([])

    sheet.append(["Building Bill of Quantities" if building else "Project Bill of Quantities"])

    sheet["A2"].font = Font(name="Arial", size=16, bold=True, color=settings.brand_primary.replace("#", ""))

    sheet.append(["Customer", project.customer.company_name, "Project", project.name, "Scope", scope_name])

    sheet.append(["Generated", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")])

    total_quantity = sum((item["quantity"] for item in rows), Decimal("0"))

    summary = ["Unique Variants", len(rows), "Total Quantity", float(total_quantity)]

    if include_prices:

        material_value = sum((commercial_line(item["quantity"], item["product"].price, item["product"].tax_rate)["subtotal"] for item in rows), Decimal("0"))

        grand_total = sum((commercial_line(item["quantity"], item["product"].price, item["product"].tax_rate)["total"] for item in rows), Decimal("0"))

        summary += ["Material Value", float(material_value), "Grand Total", float(grand_total)]

    sheet.append(summary)

    if include_prices:

        sheet.cell(sheet.max_row, 6).number_format = '"INR" #,##0.00'

    sheet.append([])

    headers = ["Product Family", "Variant", "SKU", "Category", "System", "Quantity", "Unit"]

    if include_prices:

        headers += ["Rate", "Tax %", "Line Total"]

    sheet.append(headers)

    header_row = sheet.max_row

    for cell in sheet[header_row]:

        cell.fill = PatternFill("solid", fgColor=settings.brand_primary.replace("#", ""))

        cell.font = Font(name="Arial", color="FFFFFF", bold=True, size=10)

        cell.alignment = Alignment(horizontal="center", vertical="center")

    sheet.row_dimensions[header_row].height = 24

    thin = Side(style="thin", color="D9E3EE")

    for item in rows:

        product = item["product"]

        values = [product.family.name if product.family else product.name,

                  product.variant_name or product.name, product.sku,

                  product.category.name if product.category else "—", product.workspace,

                  float(item["quantity"]), item["unit"]]

        if include_prices:

            calculated = commercial_line(item["quantity"], product.price, product.tax_rate)

            values += [float(product.price), float(product.tax_rate), float(calculated["total"])]

        sheet.append(values)

        for cell in sheet[sheet.max_row]:

            cell.font = Font(name="Arial", size=10, color="17324D")

            cell.alignment = Alignment(vertical="center")

            cell.border = Border(bottom=thin)

        sheet.cell(sheet.max_row, 6).number_format = '#,##0'

        if include_prices:

            sheet.cell(sheet.max_row, 8).number_format = '"INR" #,##0.00'

            sheet.cell(sheet.max_row, 9).number_format = '0.##"%"'

            sheet.cell(sheet.max_row, 10).number_format = '"INR" #,##0.00'

    for column, width in {"A": 32, "B": 28, "C": 20, "D": 24, "E": 16, "F": 14, "G": 12,

                          "H": 16, "I": 12, "J": 18}.items():

        sheet.column_dimensions[column].width = width

    sheet.freeze_panes = f"A{header_row + 1}"

    sheet.auto_filter.ref = f"A{header_row}:{chr(64 + len(headers))}{sheet.max_row}"

    sheet.print_title_rows = f"{header_row}:{header_row}"

    sheet.print_options.horizontalCentered = True

    sheet.page_setup.orientation = "landscape"

    sheet.page_setup.fitToWidth = 1



    breakdown = workbook.create_sheet("Room Breakdown")

    breakdown.sheet_view.showGridLines = False

    breakdown.append([])

    breakdown.append(["Room Allocation Detail"])

    breakdown["A2"].font = Font(name="Arial", size=16, bold=True, color=settings.brand_primary.replace("#", ""))

    breakdown.append(["Customer", project.customer.company_name, "Project", project.name, "Scope", scope_name])

    breakdown.append([])

    breakdown_headers = ["Product Family", "Variant", "SKU", "Building", "Floor", "Room", "Quantity", "Unit"]

    breakdown.append(breakdown_headers)

    breakdown_header_row = breakdown.max_row

    for cell in breakdown[breakdown_header_row]:

        cell.fill = PatternFill("solid", fgColor=settings.brand_primary.replace("#", ""))

        cell.font = Font(name="Arial", color="FFFFFF", bold=True, size=10)

        cell.alignment = Alignment(horizontal="center", vertical="center")

    for item in rows:

        product = item["product"]

        for allocation in item["breakdown"]:

            breakdown.append([product.family.name if product.family else product.name,

                              product.variant_name or product.name, product.sku,

                              allocation["building"], allocation["floor"], allocation["room"],

                              float(allocation["quantity"]), item["unit"]])

            for cell in breakdown[breakdown.max_row]:

                cell.font = Font(name="Arial", size=10, color="17324D")

                cell.border = Border(bottom=thin)

            breakdown.cell(breakdown.max_row, 7).number_format = '#,##0'

    for column, width in {"A": 32, "B": 28, "C": 20, "D": 22, "E": 20, "F": 24, "G": 14, "H": 12}.items():

        breakdown.column_dimensions[column].width = width

    breakdown.freeze_panes = f"A{breakdown_header_row + 1}"

    breakdown.auto_filter.ref = f"A{breakdown_header_row}:H{breakdown.max_row}"

    breakdown.print_title_rows = f"{breakdown_header_row}:{breakdown_header_row}"

    breakdown.page_setup.orientation = "landscape"

    breakdown.page_setup.fitToWidth = 1

    buffer = BytesIO(); workbook.save(buffer); return buffer.getvalue()
