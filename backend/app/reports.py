from __future__ import annotations

from collections import defaultdict

from datetime import datetime, timezone

from decimal import Decimal
from functools import lru_cache

from html import escape, unescape

from io import BytesIO
from base64 import b64decode

from pathlib import Path

import re

from PIL import Image as PILImage, ImageChops, ImageOps

from openpyxl import Workbook

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from reportlab.lib import colors

from reportlab.lib.enums import TA_CENTER, TA_RIGHT

from reportlab.lib.pagesizes import A4

from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

from reportlab.lib.units import mm

from reportlab.platypus import (

    Image,
    Flowable,
    KeepTogether,
    HRFlowable,

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

PAGE_W, PAGE_H = A4
PAGE_MARGIN_X = 10 * mm
CONTENT_LEFT = PAGE_MARGIN_X
CONTENT_RIGHT = PAGE_W - PAGE_MARGIN_X
CONTENT_WIDTH = CONTENT_RIGHT - CONTENT_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_FONT_DIRS = (Path("/usr/share/fonts/truetype/dejavu"),
              Path("/usr/local/share/fonts"), Path(__file__).resolve().parent / "assets" / "fonts")
FONT_REGULAR, FONT_BOLD, FONT_SERIF = "Helvetica", "Helvetica-Bold", "Times-Bold"
for _font_dir in _FONT_DIRS:
    if all((_font_dir / name).is_file() for name in
           ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSerif-Bold.ttf")):
        pdfmetrics.registerFont(TTFont("BookSans", str(_font_dir / "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("BookSansBold", str(_font_dir / "DejaVuSans-Bold.ttf")))
        pdfmetrics.registerFont(TTFont("BookSerifBold", str(_font_dir / "DejaVuSerif-Bold.ttf")))
        FONT_REGULAR, FONT_BOLD, FONT_SERIF = "BookSans", "BookSansBold", "BookSerifBold"
        break
if FONT_REGULAR == "Helvetica":
    import reportlab
    _bundled_fonts = Path(reportlab.__file__).resolve().parent / "fonts"
    pdfmetrics.registerFont(TTFont("BookSans", str(_bundled_fonts / "Vera.ttf")))
    pdfmetrics.registerFont(TTFont("BookSansBold", str(_bundled_fonts / "VeraBd.ttf")))
    FONT_REGULAR, FONT_BOLD, FONT_SERIF = "BookSans", "BookSansBold", "BookSansBold"

GOLD = colors.HexColor("#F8B817")
GOLD_LIGHT = colors.HexColor("#FFD45A")
DEEP_NAVY = colors.HexColor("#001B38")
PALE = colors.HexColor("#EEF6FC")
LINE = colors.HexColor("#B8D4EA")


def _normalize_pdf_text(value) -> str:

    """Repair legacy lighting-spec characters before ReportLab renders them."""

    if value is None:

        return ""

    text = str(value)

    text = text.replace("Â°", "°").replace("ºC", "°C").replace("Â", "")

    # Legacy imported values such as 15?? / 24?? and 45-50??C.

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

    """Return the selected variant's real image within the requested bounds."""

    source = _media_path(product)

    if source is None:

        return None

    try:
        # Local media is a Path; a remote provider may return bytes or a stream.
        if isinstance(source, (bytes, bytearray, memoryview)):
            source = BytesIO(source)
        elif hasattr(source, "seek"):
            source.seek(0)
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

            # Trim empty white catalogue margins only when every corner is white.
            rgb = raster.convert("RGB")
            corners = [rgb.getpixel((x,y)) for x in (0,rgb.width-1)
                       for y in (0,rgb.height-1)]
            if all(min(pixel) >= 242 for pixel in corners):
                difference = ImageChops.difference(rgb, PILImage.new("RGB",rgb.size,"white"))
                red, green, blue = difference.split()
                contrast = ImageChops.lighter(red, ImageChops.lighter(green, blue))
                bounds = contrast.point(lambda value: 255 if value>20 else 0).getbbox()
                if bounds and (bounds[2]-bounds[0])*(bounds[3]-bounds[1]) < .85*rgb.width*rgb.height:
                    margin = max(4,int(max(bounds[2]-bounds[0],bounds[3]-bounds[1])*.07))
                    raster = raster.crop((max(0,bounds[0]-margin),max(0,bounds[1]-margin),
                                          min(rgb.width,bounds[2]+margin),min(rgb.height,bounds[3]+margin)))

            scale = min(width / raster.width, height / raster.height)
            draw_width = raster.width * scale
            draw_height = raster.height * scale

            data = BytesIO()

            raster.save(data, format="PNG")

            data.seek(0)

        return Image(data, width=draw_width, height=draw_height, hAlign="CENTER")

    except (OSError, ValueError, TypeError, AttributeError):

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
    """Return compact client-facing technical rows for the product card.

    Empty values are omitted so the card remains compact enough for multiple
    products per A4 page while preserving the approved field order.
    """
    visible = _visible_spec_map(db, product)
    rows: list[tuple[str, object]] = []

    for label, aliases in TECHNICAL_CARD_FIELDS:
        if label == "Warranty":
            value = product.warranty
            if value in (None, "", "—"):
                value = next(
                    (
                        visible[_spec_key(alias)]
                        for alias in aliases
                        if _spec_key(alias) in visible
                    ),
                    None,
                )
        else:
            value = next(
                (
                    visible[_spec_key(alias)]
                    for alias in aliases
                    if _spec_key(alias) in visible
                ),
                None,
            )

        if value not in (None, "", "—", []):
            rows.append((label, value))

    # Keep the table valid even for products with no configured specifications.
    if not rows:
        rows.append(("Technical Specifications", "Not configured"))

    return rows

def _placement_panel(allocations, quantity, unit, styles):
    """Compact PROJECT PLACEMENT block sized for three product cards per A4 page."""
    allocations = list(allocations or [])
    rows = []

    # Keep the placement area compact. For aggregated project cards, show the
    # first two room allocations and combine the remaining rooms into one row.
    visible_allocations = allocations[:3]
    remaining_allocations = allocations[3:]

    for allocation in visible_allocations:
        room = _text(allocation.get("room"), "Room")
        qty = allocation.get("quantity", 0)
        allocation_unit = allocation.get("unit") or unit
        rows.append([
            _p(room, styles["placement_room"]),
            _p(f"{_num(qty)} {_text(allocation_unit, '')}".strip(), styles["placement_qty"]),
        ])

    if remaining_allocations:
        other_qty = sum((Decimal(str(row.get("quantity") or 0)) for row in remaining_allocations), Decimal("0"))
        rows.append([
            _p(f"Other rooms ({len(remaining_allocations)})", styles["placement_room"]),
            _p(f"{_num(other_qty)} {_text(unit, '')}".strip(), styles["placement_qty"]),
        ])

    if not rows:
        rows.append([
            _p("Project", styles["placement_room"]),
            _p(f"{_num(quantity)} {_text(unit, '')}".strip(), styles["placement_qty"]),
        ])

    rows.append([
        _p("Total", styles["placement_room"]),
        _p(f"{_num(quantity)} {_text(unit, '')}".strip(), styles["placement_qty"]),
    ])

    table = Table(rows, colWidths=[23 * mm, 13 * mm], hAlign="CENTER")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0.55 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0.55 * mm),
    ]))

    body = Table([
        [_p("PROJECT PLACEMENT", styles["placement_heading"])],
        [table],
    ], colWidths=[40 * mm])
    body.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EEF5FC")),
        ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
        ("TOPPADDING", (0, 0), (-1, 0), 1.3 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 0.4 * mm),
        ("TOPPADDING", (0, 1), (-1, 1), 0),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 1.0 * mm),
    ]))
    return body

def _spec_table(rows, styles, width, compact=False):
    if not rows:
        rows = [("Specifications", "Not configured")]
    label_width = (width * .39 if compact else width * .38)
    label_style = styles["tech_label_compact"] if compact else styles["tech_label"]
    value_style = styles["tech_value_compact"] if compact else styles["tech_value"]
    table = Table([[_p(k, label_style), _p(v, value_style)] for k,v in rows],
                  colWidths=[label_width,width-label_width], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#E6F2FB")),
        ("INNERGRID",(0,0),(-1,-1),.25,LINE),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),(.8 if compact else 1.15)*mm),
        ("RIGHTPADDING",(0,0),(-1,-1),(.8 if compact else 1.15)*mm),
        ("TOPPADDING",(0,0),(-1,-1),.12*mm if compact else .55*mm),
        ("BOTTOMPADDING",(0,0),(-1,-1),.12*mm if compact else .55*mm),
    ]))
    return table

def _product_identity(product):
    """Use variant-specific fields before broad catalogue classifications."""
    family = _text(getattr(getattr(product, "family", None), "name", None),
                   _text(getattr(product, "name", None), "Product"))
    model = _text(getattr(product, "model_number", None)
                  or getattr(product, "variant_name", None)
                  or getattr(product, "sku", None), "Model not specified")
    subtype = getattr(getattr(product, "subcategory", None), "name", None)
    candidate_names = (getattr(product, "product_type", None),
                       getattr(product, "type", None), subtype,
                       getattr(getattr(product, "family", None), "product_type", None),
                       getattr(getattr(product, "category", None), "name", None),
                       getattr(product, "name", None),
                       getattr(product, "variant_name", None))
    kind = next((str(value).strip() for value in candidate_names
                 if value and str(value).strip().casefold()
                 not in {family.casefold(), model.casefold(), "lighting", "electrical",
                         "products", "product", "luminaires"}), "")
    return family, model, kind

def _product_description(product):
    description = getattr(product, "description", None)
    if not description:
        description = getattr(product, "short_description", None)
    if not description:
        description = getattr(product, "product_description", None)
    if not description:
        description = getattr(getattr(product, "family", None), "description", None)
    shown = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ",
                   unescape(_text(description, "")))).strip()
    family, model, kind = _product_identity(product)
    return shown if shown and shown.casefold() not in {
        family.casefold(), model.casefold(), kind.casefold()
    } else ""

def _product_card(product, header, body, styles, width, room_note=None, compact=False):
    rows = [[header]]
    description = _product_description(product)
    rows.append([body])
    if description:
        rows.append([_p(description, styles["tech_description"] if compact else styles["product_description"])])
    if room_note:
        rows.append([_p(f"Room note: {_text(room_note)}", styles["product_description"])])
    card = Table(rows, colWidths=[width], hAlign="LEFT",
                 cornerRadii=[2*mm, 2*mm, 2*mm, 2*mm])
    commands = [("BOX",(0,0),(-1,-1),.45,LINE),
                ("VALIGN",(0,0),(-1,-1),"TOP"),
                ("LEFTPADDING",(0,0),(-1,-1),0),
                ("RIGHTPADDING",(0,0),(-1,-1),0),
                ("TOPPADDING",(0,0),(-1,-1),0),
                ("BOTTOMPADDING",(0,0),(-1,-1),0)]
    if description:
        commands += [("BACKGROUND",(0,2),(0,2),colors.HexColor("#F8FBFF")),
                     ("LEFTPADDING",(0,2),(0,2),2*mm),
                     ("RIGHTPADDING",(0,2),(0,2),2*mm),
                     ("TOPPADDING",(0,2),(0,2),(.35 if compact else 1)*mm),
                     ("BOTTOMPADDING",(0,2),(0,2),(.35 if compact else 1)*mm),
                     ("LINEABOVE",(0,2),(0,2),.25,LINE)]
    if room_note:
        note_row = len(rows)-1
        commands += [("BACKGROUND",(0,note_row),(0,note_row),PALE),
                     ("LEFTPADDING",(0,note_row),(0,note_row),2*mm),
                     ("RIGHTPADDING",(0,note_row),(0,note_row),2*mm),
                     ("TOPPADDING",(0,note_row),(0,note_row),.8*mm),
                     ("BOTTOMPADDING",(0,note_row),(0,note_row),.8*mm)]
    card.setStyle(TableStyle(commands))
    return card

def _product_header(product, index, styles, width, compact=False):
    family, model, kind = _product_identity(product)
    badge = _p(f"{index:02d}", styles["badge"])
    middle = Paragraph(f"<b>{escape(_text(family))}</b><br/>{escape(_text(model))}",styles["card_heading"])
    row=Table([[badge,middle,_p(kind,styles["card_kind"])]],
              colWidths=[11*mm,width-42*mm,31*mm],cornerRadii=[2*mm,2*mm,0,0])
    row.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),NAVY),
        ("BACKGROUND",(0,0),(0,0),colors.HexColor("#DCEFFD")),
        ("BOX",(0,0),(0,0),.4,LINE),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),2*mm),
        ("RIGHTPADDING",(0,0),(-1,-1),2*mm),
        ("TOPPADDING",(0,0),(-1,-1),(1 if compact else 1.5)*mm),
        ("BOTTOMPADDING",(0,0),(-1,-1),(1 if compact else 1.5)*mm),
    ]))
    return row

def _picture_panel(product, allocations, quantity, unit, styles, width, compact=False):
    size = 27*mm if compact else 32*mm
    picture=_product_image(product,size,size)
    if picture is None: picture=_p("Product image not available",styles["missing_image"])
    box=Table([[picture]],colWidths=[width-2*mm],rowHeights=[30*mm if compact else 34*mm])
    box.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                             ("ALIGN",(0,0),(-1,-1),"CENTER"),
                             ("BACKGROUND",(0,0),(-1,-1),colors.white),
                             ("LEFTPADDING",(0,0),(-1,-1),0),
                             ("RIGHTPADDING",(0,0),(-1,-1),0),
                             ("TOPPADDING",(0,0),(-1,-1),0),
                             ("BOTTOMPADDING",(0,0),(-1,-1),0)]))
    placement=_placement_panel(allocations,quantity,unit,styles)
    panel=Table([[box],[placement]],colWidths=[width])
    panel.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),
                              ("LEFTPADDING",(0,0),(-1,-1),.5*mm),
                              ("RIGHTPADDING",(0,0),(-1,-1),.5*mm),
                              ("TOPPADDING",(0,0),(-1,-1),1*mm),
                              ("BOTTOMPADDING",(0,0),(-1,-1),1*mm)]))
    return panel

def _technical_card(db, product, quantity, unit, styles, allocations=None, index=1):
    """Full-width card: image/placement and two independently wrapping spec columns."""
    all_rows=_technical_spec_rows(db,product)
    left_keys={label for label,_ in TECHNICAL_CARD_FIELDS[:9]}
    left_rows=[row for row in all_rows if row[0] in left_keys]
    right_rows=[row for row in all_rows if row[0] not in left_keys]
    side=43*mm; gutter=1.5*mm; spec_width=(CONTENT_WIDTH-side-2*gutter)/2
    body=Table([[_picture_panel(product,allocations,quantity,unit,styles,side,compact=True),
                 "",
                 _spec_table(left_rows,styles,spec_width,compact=True),
                 "",
                 _spec_table(right_rows,styles,spec_width,compact=True)]],
               colWidths=[side,gutter,spec_width,gutter,spec_width])
    body.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),
                              ("LEFTPADDING",(0,0),(-1,-1),0),
                              ("RIGHTPADDING",(0,0),(-1,-1),0),
                              ("TOPPADDING",(0,0),(-1,-1),.5*mm),
                              ("BOTTOMPADDING",(0,0),(-1,-1),.5*mm),
                              ("LINEAFTER",(0,0),(0,0),.4,LINE)]))
    return _product_card(product,_product_header(product,index,styles,CONTENT_WIDTH,compact=True),
                         body,styles,CONTENT_WIDTH,compact=True)

def _room_product_card(db, item, room_name, styles, index, width):
    product=item["product"]
    spec=_technical_spec_rows(db,product)
    left=36*mm; gutter=1*mm; right=width-left-gutter
    allocation=[{"room":room_name,"quantity":item["quantity"],"unit":item["unit"]}]
    # Use a compact placement panel that retains the exact room quantity.
    pic=_product_image(product,32*mm,38*mm) or _p("Product image not available",styles["missing_image"])
    picbox=Table([[pic]],colWidths=[left-2*mm],rowHeights=[40*mm],
                 cornerRadii=[1.5*mm]*4)
    picbox.setStyle(TableStyle([("ALIGN",(0,0),(-1,-1),"CENTER"),
                               ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                               ("LEFTPADDING",(0,0),(-1,-1),0),
                               ("RIGHTPADDING",(0,0),(-1,-1),0)]))
    qty=f"{_num(item['quantity'])} {_text(item['unit'],'')}".strip()
    placement=Table([[_p("Project Placement",styles["placement_heading"]),""],
                     [_p(room_name,styles["placement_room"]),_p(qty,styles["placement_qty"])],
                     [_p("Total",styles["placement_heading"]),_p(qty,styles["placement_qty"])]],
                    colWidths=[left*.57,left*.43],cornerRadii=[1.5*mm]*4)
    placement.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),PALE),
                                   ("VALIGN",(0,0),(-1,-1),"TOP"),
                                   ("LEFTPADDING",(0,0),(-1,-1),1*mm),
                                   ("RIGHTPADDING",(0,0),(-1,-1),1*mm),
                                   ("TOPPADDING",(0,0),(-1,-1),.65*mm),
                                   ("BOTTOMPADDING",(0,0),(-1,-1),.65*mm)]))
    image_side=Table([[picbox],[placement]],colWidths=[left])
    image_side.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),
                                    ("LEFTPADDING",(0,0),(-1,-1),0),
                                    ("RIGHTPADDING",(0,0),(-1,-1),0),
                                    ("TOPPADDING",(0,0),(-1,-1),1*mm),
                                    ("BOTTOMPADDING",(0,0),(-1,-1),1*mm)]))
    body=Table([[image_side,"",_spec_table(spec,styles,right,compact=True)]],
               colWidths=[left,gutter,right])
    body.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),
                              ("LEFTPADDING",(0,0),(-1,-1),0),
                              ("RIGHTPADDING",(0,0),(-1,-1),0),
                              ("TOPPADDING",(0,0),(-1,-1),1*mm),
                              ("BOTTOMPADDING",(0,0),(-1,-1),1*mm)]))
    return _product_card(product,_product_header(product,index,styles,width),
                         body,styles,width,room_note=item.get("notes"))

def _room_summary_card(room_row,index,styles,width):
    products=room_row["products"]
    room=room_row["room"]
    total=sum((item["quantity"] for item in products),Decimal("0"))
    status="Configured" if products else "Not configured"
    header=Table([[_p(f"{index:02d}",styles["badge"]),_p(room.name,styles["card_heading"]),
                   _p(status,styles["status_ok"] if products else styles["status_muted"])]],
                 colWidths=[11*mm,width-42*mm,31*mm],cornerRadii=[2*mm,2*mm,0,0])
    header.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),NAVY),
                                ("BACKGROUND",(0,0),(0,0),colors.HexColor("#DCEFFD")),
                                ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                                ("LEFTPADDING",(0,0),(-1,-1),2*mm),
                                ("RIGHTPADDING",(0,0),(-1,-1),2*mm),
                                ("TOPPADDING",(0,0),(-1,-1),2*mm),
                                ("BOTTOMPADDING",(0,0),(-1,-1),2*mm)]))
    metrics=[("Products",len(products)),("Quantity",_num(total)),
             ("Main Boards",sum(board.quantity for board in room_row["boards"]))]
    body_width=width-4*mm
    body=Table([[_KpiIcon(i) for i in (4,1,5)],
                [_p(k,styles["kpi_label"]) for k,v in metrics],
                [_p(v,styles["card_metric"]) for k,v in metrics]],
               colWidths=[body_width/3]*3,cornerRadii=[1.5*mm]*4)
    body.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),PALE),
                              ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                              ("LINEAFTER",(0,0),(1,-1),.3,LINE),
                              ("ALIGN",(0,0),(-1,0),"CENTER"),
                              ("TOPPADDING",(0,0),(-1,-1),1.1*mm),
                              ("BOTTOMPADDING",(0,0),(-1,-1),1.1*mm)]))
    card=Table([[header],[body]],colWidths=[width],cornerRadii=[2*mm]*4)
    card.setStyle(TableStyle([("BOX",(0,0),(-1,-1),.45,LINE),
                              ("LEFTPADDING",(0,0),(0,0),0),
                              ("RIGHTPADDING",(0,0),(0,0),0),
                              ("LEFTPADDING",(0,1),(0,1),2*mm),
                              ("RIGHTPADDING",(0,1),(0,1),2*mm),
                              ("TOPPADDING",(0,0),(-1,-1),0),
                              ("BOTTOMPADDING",(0,0),(-1,-1),0),
                              ("TOPPADDING",(0,1),(0,1),2*mm),
                              ("BOTTOMPADDING",(0,1),(0,1),2*mm)]))
    return card

def _match_card_heights(cards, width):
    """Keep paired cards on the same top and bottom baselines."""
    measured = [card.wrap(width, PAGE_H)[1] for card in cards]
    target = max(measured, default=0)
    for card, height in zip(cards, measured):
        if target - height > .1:
            # Give the flexible body row the extra height, keeping the heading
            # at the top and the description/footer against the bottom edge.
            card._argH[1] = card._rowHeights[1] + target - height
    return cards


def _wide_table(data, widths, **kwargs):

    """Scale a table's columns to the universal content edges."""

    total = sum(widths)

    kwargs.setdefault("hAlign", "LEFT")
    return Table(data, colWidths=[width * CONTENT_WIDTH / total for width in widths], **kwargs)

def _styles():

    base = getSampleStyleSheet()
    base["BodyText"].fontName = FONT_REGULAR
    base["Normal"].fontName = FONT_REGULAR

    return {

        "title": ParagraphStyle("book-title", parent=base["Title"], fontName=FONT_BOLD,

                                fontSize=27, leading=32, textColor=colors.white, alignment=TA_CENTER,

                                spaceAfter=5 * mm),

        "cover_sub": ParagraphStyle("cover-sub", parent=base["Normal"], fontSize=11, leading=16,

                                    textColor=colors.HexColor("#DCE9F8"), alignment=TA_CENTER),

        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName=FONT_BOLD, fontSize=21,

                             leading=26, textColor=NAVY, spaceAfter=2 * mm),

        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName=FONT_BOLD,
            fontSize=12,
            leading=15,
            textColor=colors.white,
            backColor=NAVY,

            borderPadding=(
                2.5 * mm,   # top
                4 * mm,     # right
                2.5 * mm,   # bottom
                4 * mm,     # left
            ),

            spaceBefore=3 * mm,
            spaceAfter=3 * mm,
        ),

        "header_cell_right": ParagraphStyle(
            "header-cell-right",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=6.7,
            leading=8.2,
            textColor=colors.white,
            alignment=TA_RIGHT,
        ),

        "section_bar": ParagraphStyle(
            "section-bar",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=12,
            leading=15,
            textColor=colors.white,
        ),

        "h3": ParagraphStyle("h3", parent=base["Heading3"], fontName=FONT_BOLD, fontSize=10,

                             leading=13, textColor=NAVY, spaceBefore=2 * mm, spaceAfter=2 * mm),

        "body": ParagraphStyle("body", parent=base["BodyText"], fontSize=8.2, leading=11, textColor=TEXT),

        "small": ParagraphStyle("small", parent=base["BodyText"], fontSize=7, leading=9, textColor=MUTED),

        "cell": ParagraphStyle("cell", parent=base["BodyText"], fontSize=7.5, leading=9.5, textColor=TEXT),

        "cell_right": ParagraphStyle("cell-right", parent=base["BodyText"], fontSize=6.7, leading=8.5,

                                     textColor=TEXT, alignment=TA_RIGHT),

        "header_cell": ParagraphStyle("header-cell", parent=base["BodyText"], fontName=FONT_BOLD,

                                      fontSize=6.7, leading=8.2, textColor=colors.white),

        "product_name": ParagraphStyle(

            "product-name",

            parent=base["BodyText"],

            fontName=FONT_BOLD,

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

        "tech_title": ParagraphStyle("tech-title", parent=base["BodyText"], fontName=FONT_BOLD, fontSize=10, leading=12, textColor=NAVY),

        "tech_meta": ParagraphStyle("tech-meta", parent=base["BodyText"], fontSize=7.2, leading=9, textColor=MUTED),

        "tech_product_name": ParagraphStyle("tech-product-name", parent=base["BodyText"],
                                             fontName=FONT_BOLD, fontSize=8.4, leading=9.6,
                                             textColor=NAVY, alignment=TA_CENTER),

        "tech_model": ParagraphStyle("tech-model", parent=base["BodyText"], fontSize=5.7, leading=6.8,
                                      textColor=MUTED, alignment=TA_CENTER),

        "tech_label": ParagraphStyle("tech-label", parent=base["BodyText"], fontSize=6.5, leading=8,
                                      textColor=colors.HexColor("#6780A0")),

        "tech_value": ParagraphStyle("tech-value", parent=base["BodyText"], fontSize=6.7, leading=8.2, textColor=TEXT),

        "tech_label_compact": ParagraphStyle("tech-label-compact", parent=base["BodyText"],
                                              fontSize=6.3, leading=6.9,
                                              textColor=colors.HexColor("#6780A0")),

        "tech_value_compact": ParagraphStyle("tech-value-compact", parent=base["BodyText"],
                                              fontSize=6.5, leading=7.0, textColor=TEXT),

        "tech_description": ParagraphStyle("tech-description", parent=base["BodyText"],
                                             fontSize=6.8, leading=8, textColor=TEXT),

        "placement_heading": ParagraphStyle("placement-heading", parent=base["BodyText"],
                                             fontName=FONT_BOLD, fontSize=5.6, leading=6.6, textColor=NAVY),

        "placement_room": ParagraphStyle("placement-room", parent=base["BodyText"], fontSize=6.3, leading=7.8, textColor=TEXT),

        "placement_qty": ParagraphStyle("placement-qty", parent=base["BodyText"], fontSize=5.4, leading=6.4,
                                         textColor=TEXT, alignment=TA_RIGHT),

        "missing_image": ParagraphStyle("missing-image", parent=base["BodyText"], fontSize=5.8, leading=7,

                                         textColor=MUTED, alignment=TA_CENTER),

        "kpi": ParagraphStyle("kpi", parent=base["BodyText"], fontName=FONT_BOLD, fontSize=16,

                              leading=18, textColor=NAVY, alignment=TA_CENTER),

        "kpi_label": ParagraphStyle("kpi-label", parent=base["BodyText"], fontSize=6.8, leading=8,

                                    textColor=MUTED, alignment=TA_CENTER),
        "section_accent": ParagraphStyle("section-accent",parent=base["BodyText"],fontName=FONT_BOLD,
                                         fontSize=19,leading=18,textColor=GOLD_LIGHT,alignment=TA_CENTER),
        "badge": ParagraphStyle("badge",parent=base["BodyText"],fontName=FONT_BOLD,
                                fontSize=11,leading=13,textColor=NAVY,alignment=TA_CENTER),
        "card_heading": ParagraphStyle("card-heading",parent=base["BodyText"],fontName=FONT_BOLD,
                                       fontSize=8.8,leading=10.5,textColor=colors.white),
        "card_kind": ParagraphStyle("card-kind",parent=base["BodyText"],fontSize=7.4,leading=9,
                                    textColor=colors.white,alignment=TA_RIGHT),
        "product_description": ParagraphStyle("product-description",parent=base["BodyText"],
                                               fontSize=7,leading=9,textColor=TEXT),
        "status_ok": ParagraphStyle("status-ok",parent=base["BodyText"],fontName=FONT_BOLD,
                                     fontSize=7,leading=8.5,textColor=colors.HexColor("#6FE6B8"),alignment=TA_RIGHT),
        "status_muted": ParagraphStyle("status-muted",parent=base["BodyText"],fontSize=6.8,leading=8,
                                       textColor=colors.HexColor("#CBD6E4"),alignment=TA_RIGHT),
        "card_metric": ParagraphStyle("card-metric",parent=base["BodyText"],fontName=FONT_BOLD,
                                      fontSize=11,leading=14,textColor=NAVY,alignment=TA_CENTER),
        "info_label": ParagraphStyle(
            "info-label",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=8.5,
            leading=10.5,
            textColor=colors.HexColor("#587392"),
        ),

        "info_value": ParagraphStyle(
            "info-value",
            parent=base["BodyText"],
            fontSize=8.5,
            leading=11,
            textColor=TEXT,
        ),

    }

# The logo crop comes from the supplied visual reference.
_BRAND_LOGO_PNG = "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"

# Architectural crop from the supplied visual reference. No example text is included.
_ARCHITECTURE_JPEG = "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"

@lru_cache(maxsize=1)
def _architecture_reader():
    from reportlab.lib.utils import ImageReader
    return ImageReader(BytesIO(b64decode(_ARCHITECTURE_JPEG)))

@lru_cache(maxsize=1)
def _cover_architecture_reader():
    from reportlab.lib.utils import ImageReader
    with PILImage.open(BytesIO(b64decode(_ARCHITECTURE_JPEG))) as opened:
        art = opened.convert("RGBA")
        alpha = PILImage.new("L", art.size, 255)
        fade = min(95, art.height // 3)
        for y in range(fade):
            alpha.paste(int(255*y/fade), (0, y, art.width, y+1))
        art.putalpha(alpha)
        stream = BytesIO(); art.save(stream, format="PNG"); stream.seek(0)
        return ImageReader(stream)

@lru_cache(maxsize=1)
def _watermark_reader():
    from reportlab.lib.utils import ImageReader
    from PIL import ImageFilter
    with PILImage.open(BytesIO(b64decode(_ARCHITECTURE_JPEG))) as opened:
        edges = opened.convert("L").filter(ImageFilter.FIND_EDGES)
        edges = edges.point(lambda value: min(24, max(0, (value-28)//5)))
        art = PILImage.new("RGBA", opened.size, (85, 142, 189, 0))
        art.putalpha(edges)
        stream = BytesIO(); art.save(stream,format="PNG"); stream.seek(0)
        return ImageReader(stream)

def _date(value, cover=False):
    if not isinstance(value, (datetime,)):
        return _text(value, "Not recorded") if value else "Not recorded"
    return value.strftime("%d %B %Y" if cover else "%d %b %Y, %I:%M %p").replace(" 0", " ")

def _cover_lines(value, font=FONT_SERIF, size=30, max_width=CONTENT_WIDTH-22*mm):
    from reportlab.pdfbase.pdfmetrics import stringWidth
    words = _text(value, "Untitled Project").split()
    lines = []; current = ""
    for word in words:
        trial = (current + " " + word).strip()
        if current and stringWidth(trial, font, size) > max_width:
            lines.append(current); current = word
        else: current = trial
    if current: lines.append(current)
    return lines

def _amount_in_words(value):
    n=int(Decimal(value).quantize(Decimal("1")))
    if n<0:return "Minus " + _amount_in_words(-n)
    ones=("Zero One Two Three Four Five Six Seven Eight Nine Ten Eleven Twelve Thirteen "
          "Fourteen Fifteen Sixteen Seventeen Eighteen Nineteen").split()
    tens=("", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety")
    def below_thousand(v):
        parts=[]
        if v>=100:parts.extend([ones[v//100],"Hundred"]);v%=100
        if v>=20:parts.append(tens[v//10]);v%=10
        if v:parts.append(ones[v])
        return " ".join(parts)
    if n==0:return "Indian Rupees Zero Only"
    parts=[]
    for scale,name in ((10000000,"Crore"),(100000,"Lakh"),(1000,"Thousand"),(1,"")):
        chunk=n//scale;n%=scale
        if chunk:parts.append(" ".join(x for x in (below_thousand(chunk),name) if x))
    return "Indian Rupees " + " ".join(parts) + " Only"

def _draw_logo(canvas, x, y, width, height, dark=True):
    logo = Path(settings.company_logo_path).expanduser() if settings.company_logo_path else None
    if logo and logo.is_file():
        try:
            from reportlab.lib.utils import ImageReader
            img = ImageReader(str(logo)); iw, ih = img.getSize()
            scale = min(width/iw, height/ih)
            canvas.drawImage(img, x+(width-iw*scale)/2, y+(height-ih*scale)/2,
                             width=iw*scale, height=ih*scale, mask='auto')
            return
        except (OSError, ValueError): pass
    from reportlab.lib.utils import ImageReader
    logo_image=ImageReader(BytesIO(b64decode(_BRAND_LOGO_PNG)))
    iw,ih=logo_image.getSize();scale=min(width/iw,height/ih)
    canvas.drawImage(logo_image,x+(width-iw*scale)/2,y+(height-ih*scale)/2,
                     width=iw*scale,height=ih*scale,mask="auto")

def _draw_cover_page(canvas, doc, project_name, customer, address, location):
    canvas.saveState()
    canvas.setFillColor(DEEP_NAVY); canvas.rect(0,0,PAGE_W,PAGE_H,fill=1,stroke=0)
    canvas.setFillColor(colors.HexColor("#062E59"))
    path=canvas.beginPath(); path.moveTo(0,0); path.lineTo(PAGE_W,0)
    path.lineTo(PAGE_W,PAGE_H*.67); path.lineTo(0,PAGE_H*.52)
    path.close(); canvas.drawPath(path,fill=1,stroke=0)
    canvas.drawImage(_cover_architecture_reader(), 0, 0, width=PAGE_W, height=156*mm,
                     preserveAspectRatio=False, mask="auto")
    for inset, weight in ((6*mm,1.25),(8*mm,.45)):
        canvas.setStrokeColor(GOLD); canvas.setLineWidth(weight)
        canvas.rect(inset,inset,PAGE_W-2*inset,PAGE_H-2*inset,fill=0,stroke=1)
    _draw_logo(canvas, PAGE_W/2-62*mm, PAGE_H-91*mm, 124*mm, 34*mm)
    canvas.setFillColor(GOLD_LIGHT); canvas.setFont(FONT_REGULAR,12)
    canvas.drawCentredString(PAGE_W/2,PAGE_H-104*mm,"P R O J E C T   C O N F I G U R A T I O N   B O O K")
    lines=_cover_lines(project_name,size=40)
    font_size=40 if len(lines)==1 else 28
    canvas.setFont(FONT_SERIF,font_size)
    for i,line in enumerate(lines[:3]):
        canvas.drawCentredString(PAGE_W/2,PAGE_H-(127+i*12)*mm,line)
    canvas.setStrokeColor(GOLD); canvas.setLineWidth(.65)
    canvas.line(PAGE_W/2-32*mm,PAGE_H-(137+12*(len(lines)-1))*mm,
                PAGE_W/2+32*mm,PAGE_H-(137+12*(len(lines)-1))*mm)
    canvas.setFillColor(colors.white); canvas.setFont(FONT_REGULAR,13)
    detail_lines=_cover_lines("Prepared for: " + _text(customer,"Client"),FONT_REGULAR,13,155*mm)[:2]
    for value in (address, location):
        if value: detail_lines.extend(_cover_lines(value,FONT_REGULAR,11,155*mm)[:2])
    for i,line in enumerate(detail_lines[:6]):
        canvas.setFont(FONT_REGULAR,13 if i==0 else 11)
        canvas.drawCentredString(PAGE_W/2,PAGE_H-(157+i*7)*mm,line)
    canvas.setFillColor(colors.white); canvas.setFont(FONT_REGULAR,10)
    canvas.drawCentredString(PAGE_W/2,25*mm,"Generated: " + datetime.now().strftime("%d %B %Y"))
    canvas.setStrokeColor(GOLD); canvas.line(55*mm,26*mm,72*mm,26*mm)
    canvas.line(PAGE_W-72*mm,26*mm,PAGE_W-55*mm,26*mm)
    canvas.restoreState()

def _draw_content_page_background(canvas):
    canvas.setFillColor(colors.white); canvas.rect(0,0,PAGE_W,PAGE_H,fill=1,stroke=0)
    canvas.drawImage(_watermark_reader(),PAGE_W-116*mm,15*mm,116*mm,95*mm,
                     preserveAspectRatio=False,mask="auto")
    canvas.setFillColor(colors.HexColor("#FFF6DC"))
    path=canvas.beginPath(); path.moveTo(105*mm,16*mm);path.lineTo(145*mm,16*mm)
    path.lineTo(167*mm,37*mm);path.close();canvas.drawPath(path,fill=1,stroke=0)

def _draw_header(canvas, project_name):
    h=25*mm; y=PAGE_H-h
    canvas.setFillColor(DEEP_NAVY); canvas.rect(0,y,PAGE_W,h,fill=1,stroke=0)
    canvas.saveState()
    if hasattr(canvas,"setFillAlpha"): canvas.setFillAlpha(.37)
    canvas.drawImage(_architecture_reader(),PAGE_W-77*mm,y,77*mm,h,preserveAspectRatio=False)
    canvas.restoreState()
    _draw_logo(canvas, CONTENT_LEFT+2*mm,y+2*mm,56*mm,21*mm)
    canvas.setFillColor(colors.white); canvas.setFont(FONT_BOLD,9)
    name=_text(project_name,"Project")
    from reportlab.pdfbase.pdfmetrics import stringWidth
    while stringWidth(name,FONT_BOLD,9)>67*mm and len(name)>4:name=name[:-2]
    if name!=_text(project_name,"Project"):name=name.rstrip()+"…"
    canvas.drawRightString(CONTENT_RIGHT-5*mm,y+10*mm,name)
    canvas.setFillColor(GOLD);canvas.rect(CONTENT_RIGHT-2*mm,y+8*mm,1*mm,7*mm,fill=1,stroke=0)
    canvas.rect(0,y-1.2*mm,PAGE_W,1.2*mm,fill=1,stroke=0)

def _draw_footer(canvas, page):
    canvas.setStrokeColor(colors.HexColor("#9BB8D4"));canvas.setLineWidth(.5)
    canvas.line(CONTENT_LEFT,16*mm,CONTENT_RIGHT,16*mm)
    canvas.setFillColor(NAVY);canvas.setFont(FONT_REGULAR,7)
    canvas.drawString(CONTENT_LEFT,11*mm,"Generated: "+datetime.now().strftime("%d %b %Y"))
    canvas.setFillColor(GOLD);canvas.rect(CONTENT_RIGHT-18*mm,10.8*mm,.8*mm,4*mm,fill=1,stroke=0)
    canvas.setFillColor(NAVY);canvas.drawRightString(CONTENT_RIGHT,11*mm,f"Page {page}")

def _page_title(title, styles):
    bar=Table([["" ]],colWidths=[18*mm],rowHeights=[1*mm],hAlign="LEFT")
    bar.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),GOLD),("LEFTPADDING",(0,0),(-1,-1),0),
                            ("RIGHTPADDING",(0,0),(-1,-1),0)]))
    title = _text(title)
    title_style = styles["h1"]
    # A full-width heading must finish at the same right content edge as the
    # tables. Shrink only long titles rather than letting them wrap unexpectedly.
    if pdfmetrics.stringWidth(title, FONT_BOLD, title_style.fontSize) > CONTENT_WIDTH:
        size = max(14, min(title_style.fontSize,
                           title_style.fontSize * CONTENT_WIDTH /
                           pdfmetrics.stringWidth(title, FONT_BOLD, title_style.fontSize)))
        title_style = ParagraphStyle("fitted-page-title", parent=title_style,
                                     fontSize=size, leading=size*1.25)
    return [Paragraph(escape(title),title_style),bar,Spacer(1,5*mm)]

def _technical_page_title(styles):
    title = _page_title("Product Technical Specifications", styles)
    title[0].style = ParagraphStyle("compact-technical-title", parent=title[0].style,
                                     spaceAfter=.5*mm)
    return [*title[:-1], Spacer(1, 1*mm)]

class _KpiIcon(Flowable):
    def __init__(self, kind):
        super().__init__(); self.kind=kind; self.width=18; self.height=18
    def draw(self):
        c=self.canv;c.setStrokeColor(BLUE);c.setLineWidth(1.1)
        c.circle(9,9,8,stroke=1,fill=0)
        if self.kind in (0,2,3):
            c.rect(5,4,8,10,stroke=1,fill=0)
            if self.kind==0:
                for yy in (7,10,13):c.line(7,yy,11,yy)
            elif self.kind==2:c.circle(11,8,.5,stroke=1,fill=0)
            else:
                c.circle(8,10,1,stroke=1,fill=0);c.line(6,6,12,6)
        elif self.kind==1:
            for yy in (5,9,13):c.line(5,yy,13,yy)
        elif self.kind==4:
            c.rect(5,5,8,8,stroke=1,fill=0);c.line(5,13,9,15);c.line(13,13,9,15)
        else:
            c.rect(6,4,7,10,stroke=1,fill=0)
            for yy in (7,10,12):c.line(8,yy,11,yy)

def _page_frame(canvas, doc, project_name: str, first_is_cover: bool = True):
    if first_is_cover and doc.page==1: return
    canvas.saveState();_draw_content_page_background(canvas);_draw_header(canvas,project_name)
    _draw_footer(canvas,doc.page);canvas.restoreState()

def _section_bar(title: str, styles):
    """Render a full-width navy section header aligned exactly to CONTENT_WIDTH."""
    bar = Table(
        [[_p(title, styles["section_bar"]), _p("/", styles["section_accent"])]],
        colWidths=[CONTENT_WIDTH-11*mm, 11*mm],
        hAlign="LEFT",
        cornerRadii=[2*mm, 2*mm, 0, 0],
    )
    bar.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#073867")),
                ("BOX", (0, 0), (-1, -1), 0.45, NAVY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
            ]
        )
    )
    return bar

def _info_table(
    rows: list[tuple[str, object]],
    styles,
    widths=None,
    round_top=False,
):
    """
    Client-facing two-column information table.

    Left column  : field/label
    Right column : value

    Uses the same navy / pale-blue visual language as the
    Product Technical Specification tables.
    """

    data = [
        [
            _p(label, styles["info_label"]),
            _p(value, styles["info_value"]),
        ]
        for label, value in rows
    ]

    widths = widths if widths is not None else (54*mm, CONTENT_WIDTH-54*mm)
    table = Table(data, colWidths=list(widths), hAlign="LEFT",
                  cornerRadii=[2*mm if round_top else 0,
                               2*mm if round_top else 0,2*mm,2*mm])

    table.setStyle(
        TableStyle(
            [
                # Overall table
                ("BOX", (0, 0), (-1, -1), 0.4, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.30, LINE),

                # Left label column
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor("#EEF5FC"),
                ),

                # Right value column
                (
                    "BACKGROUND",
                    (1, 0),
                    (1, -1),
                    colors.white,
                ),

                # Vertical alignment
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

                # Cell spacing
                ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 2.2 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2 * mm),
            ]
        )
    )

    return table

def _render_project_book_pdf(db: Session, project: m.Project, include_prices: bool, building_id: str | None = None, workspace: str | None = None) -> bytes:

    structure = _project_rooms(db, project.id, building_id, workspace)

    if building_id and not structure:

        raise ValueError("Building not found in this project")

    styles = _styles()

    selected_building = structure[0]["building"] if building_id and len(structure) == 1 else None

    book_title = selected_building.name if selected_building else project.name

    buffer = BytesIO()

    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=PAGE_MARGIN_X+6, leftMargin=PAGE_MARGIN_X-6,

                            topMargin=38 * mm, bottomMargin=22 * mm,
                            allowSplitting=1,

                            title=f"{book_title} {'Building' if selected_building else 'Project'} Book",

                            author=settings.company_name)

    story = []

    # Cover artwork is drawn on the first-page canvas callback.
    story.extend([Spacer(1, 1*mm), PageBreak()])

    inquiry_stmt = select(m.Inquiry).where(m.Inquiry.project_id == project.id)

    if workspace:

        inquiry_stmt = inquiry_stmt.where(m.Inquiry.workspace == workspace)

    if selected_building:

        inquiry_stmt = inquiry_stmt.where(or_(m.Inquiry.building_id == selected_building.id, m.Inquiry.is_project_wide.is_(True)))

    inquiries = db.scalars(inquiry_stmt.order_by(desc(m.Inquiry.created_at))).all()

    primary_inquiry = inquiries[0] if inquiries else None

    story.extend(_page_title("Inquiry, Customer & Partner Information", styles))

    story.append(_section_bar("Inquiry Information", styles))

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

    story.extend([Spacer(1, 5*mm), _section_bar("Partner Information", styles)])

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

    story.extend([Spacer(1, 5*mm), _section_bar("Plan & Document Register", styles)])

    document_rows = [["Type", "Title", "Revision", "Scope", "File"]]

    for item in documents:

        scope = room_names.get(item.room_id) or floor_names.get(item.floor_id) or building_names.get(item.building_id) or "Project"

        document_rows.append([item.document_type, item.title, item.revision, scope, item.file_name])

    if len(document_rows) == 1:
        story.append(
            _info_table(
                [
                    (
                        "Documents",
                        "No plans or documents uploaded.",
                    )
                ],
                styles,
            )
        )

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

            story.extend([Spacer(1, 4 * mm), _section_bar(f"{item.document_type} · {item.title} · Rev {item.revision}", styles),

                          Image(str(path), width=CONTENT_WIDTH, height=95 * mm, kind="proportional")])

    story.append(PageBreak())

    boq = _boq(structure)

    floors_count = sum(len(row["floors"]) for row in structure)

    rooms_count = sum(len(floor["rooms"]) for row in structure for floor in row["floors"])

    board_count = sum(sum(board.quantity for board in row["boards"]) for row in structure)

    quantity = sum((row["quantity"] for row in boq), Decimal("0"))

    story.extend(_page_title("Project / System Summary", styles))

    kpi_table = _wide_table([

        [_KpiIcon(i) for i in range(6)],

        [_p(_num(value), styles["kpi"]) for value, _ in [(len(structure), ""), (floors_count, ""), (rooms_count, ""), (board_count, ""), (len(boq), ""), (quantity, "")]],

        [_p(label, styles["kpi_label"]) for label in ["Buildings", "Floors", "Rooms", "Main Boards", "Unique Products", "Total Quantity"]],

    ], widths=[28.3 * mm] * 6)

    kpi_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE),

                                   ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                                   ("TOPPADDING", (0, 0), (-1, 0), 3*mm),
                                   ("BOTTOMPADDING", (0, 0), (-1, 0), 1*mm),

                                   ("LINEBELOW", (0, 0), (-1, -1), 0.35, LINE),

                                   ("LINEBELOW", (0, 0), (-1, -1), 0.25, LINE),

                                   ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))

    story.extend([kpi_table, Spacer(1, 4 * mm), _section_bar("System Scope", styles),

                  _info_table([("Workspaces / systems", " · ".join(project.workspace_scope or ["Not provided"])),

                               ("Project / building", book_title), ("Last updated", _date(project.updated_at or project.created_at))], styles),

                  Spacer(1, 5*mm), _section_bar("Main Board Details", styles)])

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

        story.append(_info_table([("Main boards", "No main boards configured for this project.")], styles))

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

            story.extend(_page_title(f"{building.name} · {floor.name} — Complete Floor View", styles))

            floor_qty = sum((sum((item["quantity"] for item in room["products"]), Decimal("0")) for room in rooms), Decimal("0"))

            story.append(_info_table([("Building", building.name), ("Floor", floor.name),

                                      ("Total rooms", len(rooms)),

                                      ("Product quantity", _num(floor_qty)),

                                      ("Main boards", sum(board.quantity for board in floor_row["boards"]))],
                                     styles, round_top=True))

            story.append(Spacer(1, 3 * mm))

            if not rooms:
                story.append(_info_table([("Rooms", "No rooms configured for this floor.")],styles))
            else:
                gap=4*mm;card_width=(CONTENT_WIDTH-gap)/2
                for start in range(0,len(rooms),2):
                    cells=[_room_summary_card(rooms[pos],pos+1,styles,card_width)
                           for pos in range(start,min(start+2,len(rooms)))]
                    _match_card_heights(cells,card_width)
                    if len(cells)<2:cells.append("")
                    grid=Table([cells],colWidths=[card_width+gap,card_width],hAlign="LEFT")
                    grid.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),
                                              ("LEFTPADDING",(0,0),(0,0),0),
                                              ("RIGHTPADDING",(0,0),(0,0),gap),
                                              ("LEFTPADDING",(1,0),(1,0),0),
                                              ("RIGHTPADDING",(1,0),(1,0),0),
                                              ("TOPPADDING",(0,0),(-1,-1),0),
                                              ("BOTTOMPADDING",(0,0),(-1,-1),0)]))
                    story.extend([grid,Spacer(1,4*mm)])
            story.append(PageBreak())

            for room_row in rooms:

                room = room_row["room"]

                story.extend(_page_title(f"{building.name} / {floor.name} / {room.name}", styles))

                # story.append(_section_bar("Room Product Schedule", styles))
                story.append(Spacer(1, 2*mm))

                if not room_row["products"]:

                    story.append(Paragraph("No products configured for this room.", styles["body"]))

                else:

                    items=room_row["products"]
                    gap=3*mm;card_width=(CONTENT_WIDTH-gap)/2
                    rows_on_page=0; used_height=27*mm
                    page_budget=PAGE_H-38*mm-22*mm-12
                    for start in range(0,len(items),2):
                        cards=[_room_product_card(db,items[pos],room.name,styles,pos+1,card_width)
                               for pos in range(start,min(start+2,len(items)))]
                        _match_card_heights(cards,card_width)
                        if len(cards)<2:
                            cards.append("")
                        grid=Table([cards],colWidths=[card_width+gap,card_width],hAlign="LEFT")
                        grid.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),
                                                  ("LEFTPADDING",(0,0),(0,0),0),
                                                  ("RIGHTPADDING",(0,0),(0,0),gap),
                                                  ("LEFTPADDING",(1,0),(1,0),0),
                                                  ("RIGHTPADDING",(1,0),(1,0),0),
                                                  ("TOPPADDING",(0,0),(-1,-1),0),
                                                  ("BOTTOMPADDING",(0,0),(-1,-1),0)]))
                        row_height=grid.wrap(CONTENT_WIDTH,PAGE_H)[1]
                        if rows_on_page and (rows_on_page>=2 or used_height+row_height+3*mm>page_budget):
                            story.append(PageBreak())
                            story.extend(_page_title(f"{building.name} / {floor.name} / {room.name}",styles))
                            # story.append(_section_bar("Room Product Schedule",styles))
                            story.append(Spacer(1,2*mm))
                            rows_on_page=0;used_height=27*mm
                        story.extend([KeepTogether([grid]),Spacer(1,3*mm)])
                        rows_on_page+=1;used_height+=row_height+3*mm
                story.append(PageBreak())

    story.extend(_page_title("Aggregated Bill of Quantities", styles))

    headers=["#","Product Details","Model Number","Voltage","Quantity","Unit"]
    weights=[5,19,14,15,11,9]
    if include_prices:headers += ["Rate (INR)","Total (INR)"]; weights += [13,14]
    else: weights=[6,29,19,19,15,12]
    data=[[_p(value,styles["header_cell_right"] if value in {"Rate (INR)","Total (INR)"}
              else styles["header_cell"]) for value in headers]]
    subtotal=Decimal("0");tax_total=Decimal("0");tax_groups=defaultdict(lambda:Decimal("0"))
    for index,item in enumerate(boq,1):
        product=item["product"]
        spec_values=_visible_spec_map(db,product)
        voltage=next((spec_values[_spec_key(key)] for key in ("input voltage","voltage","input voltage range")
                      if _spec_key(key) in spec_values),None)
        family, model, kind = _product_identity(product)
        details = family + (f" ({kind})" if kind else "")
        cells=[_p(f"{index:02d}",styles["cell"]),_p(details,styles["cell"]),
               _p(model,styles["cell"]),
               _p(voltage,styles["cell"]),_p(_num(item["quantity"]),styles["cell_right"]),
               _p(item["unit"],styles["cell"])]
        if include_prices:
            calculated=_line_values(item["quantity"],product)
            subtotal+=calculated["subtotal"];tax_total+=calculated["tax"]
            tax_groups[Decimal(product.tax_rate or 0)]+=calculated["tax"]
            cells.extend([_money_p(product.price,styles["cell_right"]),
                          _money_p(calculated["subtotal"],styles["cell_right"])])
        data.append(cells)
    if not boq:
        data.append([_p("No products configured",styles["cell"])] + [""]*(len(headers)-1))
    table=_wide_table(data,weights,repeatRows=1,hAlign="LEFT")
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY),
                               ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,PALE]),
                               ("INNERGRID",(0,0),(-1,-1),.3,LINE),
                               ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                               ("LEFTPADDING",(0,0),(-1,-1),2*mm),
                               ("RIGHTPADDING",(0,0),(-1,-1),2*mm),
                               ("TOPPADDING",(0,0),(-1,-1),2.6*mm),
                               ("BOTTOMPADDING",(0,0),(-1,-1),2.6*mm)]))
    story.append(table)
    total_qty=sum((item["quantity"] for item in boq),Decimal("0"))
    summary_row=[_p("Total Quantity",styles["info_label"]),"","","",
                 _p(_num(total_qty),styles["cell_right"]),""]
    if include_prices: summary_row.extend([_p("Subtotal",styles["info_label"]),
                                            _money_p(subtotal,styles["cell_right"])])
    total_table=_wide_table([summary_row],weights,hAlign="LEFT")
    total_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#DDEFFD")),
                                    ("SPAN",(0,0),(3,0)),
                                    ("INNERGRID",(0,0),(-1,-1),.3,LINE),
                                    ("TOPPADDING",(0,0),(-1,-1),2.2*mm),
                                    ("BOTTOMPADDING",(0,0),(-1,-1),2.2*mm)]))
    story.append(total_table)
    if include_prices:
        story.extend([Spacer(1,4*mm),_section_bar("BOQ Financial Summary",styles)])
        grand=subtotal+tax_total;rounded=grand.quantize(Decimal("1"))
        fin=[("Subtotal (Before Tax)",_money(subtotal)),
             ("Taxable Value",_money(subtotal))]
        fin += [(f"GST @ {_num(rate)}%",_money(amount)) for rate,amount in sorted(tax_groups.items()) if amount]
        fin += [("Total GST",_money(tax_total)),
                ("Round Off",_money(rounded-grand)),
                ("Grand Total (Including GST)",_money(rounded))]
        left_width=105*mm;right_width=CONTENT_WIDTH-left_width-3*mm
        left=_info_table(fin,styles,widths=(left_width*.54,left_width*.46))
        tax_rows=[[_p("Tax Component",styles["header_cell"]),
                   _p("Rate",styles["header_cell"]),
                   _p("Amount (INR)",styles["header_cell_right"])]]
        for rate,amount in sorted(tax_groups.items()):
            if amount:tax_rows.append([_p("GST",styles["cell"]),_p(f"{_num(rate)}%",styles["cell"]),
                                      _money_p(amount,styles["cell_right"])])
        if len(tax_rows)==1:tax_rows.append([_p("GST",styles["cell"]),"",_money_p(0,styles["cell_right"])])
        tax_rows.append([_p("Total GST",styles["info_label"]),"",_money_p(tax_total,styles["cell_right"])])
        tax_table=Table(tax_rows,colWidths=[right_width*.39,right_width*.17,right_width*.44],hAlign="LEFT")
        tax_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY),
                                       ("BACKGROUND",(0,-1),(-1,-1),PALE),
                                       ("INNERGRID",(0,0),(-1,-1),.3,LINE),
                                       ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                                       ("LEFTPADDING",(0,0),(-1,-1),1.5*mm),
                                       ("RIGHTPADDING",(0,0),(-1,-1),1.5*mm),
                                       ("TOPPADDING",(0,0),(-1,-1),1.5*mm),
                                       ("BOTTOMPADDING",(0,0),(-1,-1),1.5*mm)]))
        word_box=_info_table([("Amount in Words",_amount_in_words(rounded))],styles,
                             widths=(right_width*.37,right_width*.63))
        right=Table([[_p("GST Breakup",styles["info_label"])],[tax_table],
                     [Spacer(1,2*mm)],[word_box]],colWidths=[right_width])
        right.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),
                                   ("LEFTPADDING",(0,0),(-1,-1),0),
                                   ("RIGHTPADDING",(0,0),(-1,-1),0),
                                   ("TOPPADDING",(0,0),(-1,-1),0),
                                   ("BOTTOMPADDING",(0,0),(-1,-1),0)]))
        pair=Table([[left,"",right]],colWidths=[left_width,3*mm,right_width],hAlign="LEFT")
        pair.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),
                                  ("LEFTPADDING",(0,0),(-1,-1),0),
                                  ("RIGHTPADDING",(0,0),(-1,-1),0),
                                  ("TOPPADDING",(0,0),(-1,-1),0),
                                  ("BOTTOMPADDING",(0,0),(-1,-1),0)]))
        story.append(pair)
        notes=["BOQ rates use current catalogue pricing; saved quotations contain the agreed commercial snapshots.",
               "Taxes use the rates configured for each product."]
        if boq and all(Decimal(item["product"].price or 0)==0 for item in boq):
            notes.append("Pricing is pending; review rates before sharing this book with a client.")
        story.extend([Spacer(1,4*mm),_section_bar("Notes",styles),
                      _info_table([("Notes"," ".join(notes))],styles)])
    story.append(PageBreak())

    if boq:

        technical_cards = []
        title_height = 12.5 * mm
        preferred_gap = 3.5 * mm
        minimum_gap = 1.5 * mm
        # Measure the cards before pagination so three cards can share a page
        # with the largest gap that fits without clipping their contents.
        page_budget = PAGE_H - 38*mm - 22*mm - 12

        for product_index, item in enumerate(boq):
            repeated_rooms = {
                entry["room"] for entry in item.get("breakdown", [])
                if sum(other["room"] == entry["room"] for other in item.get("breakdown", [])) > 1
            }
            allocations = [
                {
                    "room": (f"{allocation['building']} / {allocation['floor']} / {allocation['room']}"
                             if allocation["room"] in repeated_rooms else allocation["room"]),
                    "quantity": allocation["quantity"],
                    "unit": item["unit"],
                }
                for allocation in item.get("breakdown", [])
            ]

            card = _technical_card(
                db, item["product"], item["quantity"], item["unit"], styles,
                allocations=allocations, index=product_index+1,
            )
            card_height = card.wrap(CONTENT_WIDTH, PAGE_H)[1]
            technical_cards.append((card, card_height))

        position = 0
        while position < len(technical_cards):
            count = min(3, len(technical_cards) - position)
            while count > 1 and (
                title_height
                + sum(height for _, height in technical_cards[position:position+count])
                + (count - 1) * minimum_gap > page_budget
            ):
                count -= 1

            if position:
                story.append(PageBreak())
            story.extend(_technical_page_title(styles))
            page_cards = technical_cards[position:position+count]
            if count > 1:
                remaining = page_budget - title_height - sum(height for _, height in page_cards)
                gap = min(preferred_gap, remaining / (count - 1))
            for card_index, (card, _) in enumerate(page_cards):
                if card_index:
                    story.append(Spacer(1, gap))
                story.append(KeepTogether([card]))
            position += count

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

    story.extend(_page_title("Commercial Documents", styles))

    if orders or invoices:

        story.append(_section_bar("Orders and invoices", styles))

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

            numeric_headers = {"Quantity", "Rate", "Amount"}

            header_row = []

            for label in cols:
                if label in numeric_headers:
                    header_row.append(
                        _p(label, styles["header_cell_right"])
                    )
                else:
                    header_row.append(
                        _p(label, styles["header_cell"])
                    )

            data = [header_row]

            for line in quote_items:

                line_cells = [_p(line.description, styles["cell"]), _p(line.sku, styles["cell"]),

                              _p(_num(line.qty), styles["cell_right"])]

                if include_prices:

                    line_cells += [_money_p(line.rate, styles["cell_right"]),

                                   _money_p(line.amount, styles["cell_right"])]

                data.append(line_cells)

            quotation_table = _wide_table(data, widths, repeatRows=1, hAlign="LEFT")

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

            story.extend([Spacer(1, 3 * mm), _section_bar("Quotation Totals", styles),

                          _info_table([("Subtotal", _money(quote.subtotal)),

                                       ("Discount", _money(quote.discount_amount)),

                                       ("Tax", _money(quote.tax_total)),

                                       ("Grand Total", _money(quote.grand_total))], styles)])

        terms = [("Payment terms", quote.payment_terms), ("Delivery terms", quote.delivery_terms),

                 ("Warranty terms", quote.warranty_terms), ("Notes", quote.notes)]

        terms = [(key, value) for key, value in terms if value]

        if terms:

            story.extend([Spacer(1, 3 * mm), _section_bar("Terms", styles), _info_table(terms, styles)])

    doc.build(story, onFirstPage=lambda canvas, document: _draw_cover_page(
        canvas, document, book_title, project.customer.company_name,
        selected_building.address if selected_building and selected_building.address else project.address,
        ", ".join(x for x in [project.city, project.state] if x)),
        onLaterPages=lambda canvas, document: _page_frame(canvas, document, book_title))

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

    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=PAGE_MARGIN_X+6, leftMargin=PAGE_MARGIN_X-6,

                             topMargin=38 * mm, bottomMargin=21 * mm,

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

    numeric_headers = {"Quantity", "Rate", "Total"}

    header_row = []

    for value in headers:
        if value in numeric_headers:
            header_row.append(
                _p(value, styles["header_cell_right"])
            )
        else:
            header_row.append(
                _p(value, styles["header_cell"])
            )

    rows = [header_row]

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

    doc.build(story, onFirstPage=lambda canvas, document: _page_frame(canvas, document, project.name, first_is_cover=False),

              onLaterPages=lambda canvas, document: _page_frame(canvas, document, project.name))

    return buffer.getvalue()

def floor_sheet_pdf(db: Session, floor: m.Floor, include_prices: bool, workspace: str | None = None) -> bytes:

    project = floor.building.project

    structure = _project_rooms(db, project.id, floor.building_id, workspace)

    floor_row = next((fr for br in structure for fr in br["floors"] if fr["floor"].id == floor.id), None)

    if not floor_row:

        raise ValueError("Floor not found")

    styles = _styles(); buffer = BytesIO()

    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=PAGE_MARGIN_X+6, leftMargin=PAGE_MARGIN_X-6,

                             topMargin=38 * mm, bottomMargin=21 * mm,

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

    doc.build(story, onFirstPage=lambda canvas, document: _page_frame(canvas, document, project.name, first_is_cover=False),

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
