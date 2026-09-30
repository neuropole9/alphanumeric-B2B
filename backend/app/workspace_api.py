from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from . import models as m
from .api import (
    admin_required,
    can_view_commercial,
    can_view_prices,
    customer_out,
    ensure_building_access,
    ensure_project_access,
    invoice_out,
    order_out,
    partner_out,
    product_out,
    project_basic,
    project_user_out,
    quote_out,
    require_project_permission,
)
from .db import get_db
from .deps import get_current_user, require_csrf
from .services import audit

router = APIRouter(prefix="/api/v1", tags=["project workspace"])
ADMIN_ROLES = {"ADMIN", "SUPER_ADMIN"}


class CustomerPatch(BaseModel):
    company_name: str | None = Field(default=None, min_length=1, max_length=180)
    contact_person: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=60)
    gstin: str | None = Field(default=None, max_length=32)
    address: str | None = None
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    status: str | None = None


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    address: str | None = None
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    status: str | None = None
    owner_id: str | None = None
    notes: str | None = None


class BuildingIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str | None = Field(default=None, max_length=60)
    building_type: str | None = Field(default=None, max_length=80)
    address: str | None = None
    status: str = "ACTIVE"
    planned_floors: int = Field(default=1, ge=0, le=500)


class BuildingPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    code: str | None = Field(default=None, max_length=60)
    building_type: str | None = Field(default=None, max_length=80)
    address: str | None = None
    status: str | None = None
    planned_floors: int | None = Field(default=None, ge=0, le=500)


class BoardIn(BaseModel):
    floor_id: str
    room_id: str | None = None
    name: str = Field(min_length=1, max_length=140)
    code: str | None = Field(default=None, max_length=80)
    board_type: str = Field(min_length=1, max_length=100)
    system: str = "MIXED"
    quantity: int = Field(default=1, gt=0)
    notes: str | None = None


class RoomProductIn(BaseModel):
    product_id: str
    workspace: str | None = None
    quantity: Decimal = Field(gt=0)
    notes: str | None = None
    linked_inquiry_id: str | None = None


class RoomProductPatch(BaseModel):
    quantity: Decimal | None = Field(default=None, gt=0)
    notes: str | None = None
    approval_status: str | None = None


class ProposalIn(BaseModel):
    product_id: str
    quantity: Decimal = Field(gt=0)
    notes: str | None = None
    recommendation: str | None = None
    send_to_customer: bool = True
    linked_inquiry_id: str | None = None


class ProposalDecision(BaseModel):
    decision: str = Field(pattern="^(APPROVED|REJECTED)$")
    comment: str | None = None


def _iso(value):
    return value.isoformat() if value else None


def _room_scope(db: Session, room_id: str) -> tuple[m.Room, m.Floor, m.Building, m.Project]:
    room = db.scalar(select(m.Room).options(
        selectinload(m.Room.floor).selectinload(m.Floor.building).selectinload(m.Building.project)
    ).where(m.Room.id == room_id))
    if not room:
        raise HTTPException(404, "Room not found")
    floor = room.floor
    building = floor.building
    project = building.project
    return room, floor, building, project


def _board_out(board: m.MainBoard) -> dict:
    return {"id": board.id, "project_id": board.project_id, "building_id": board.building_id,
            "floor_id": board.floor_id, "room_id": board.room_id, "name": board.name,
            "code": board.code, "board_type": board.board_type, "system": board.system,
            "quantity": board.quantity, "notes": board.notes,
            "created_at": _iso(board.created_at), "updated_at": _iso(board.updated_at)}


def _room_product_out(item: m.RoomProduct, user: m.User) -> dict:
    return {"id": item.id, "project_id": item.project_id, "building_id": item.building_id,
            "floor_id": item.floor_id, "room_id": item.room_id,
            "product": product_out(item.product, include_price=user.role in ADMIN_ROLES),
            "quantity": float(item.quantity), "unit": item.unit, "notes": item.notes,
            "approval_status": item.approval_status, "source": item.source,
            "linked_inquiry_id": item.linked_inquiry_id,
            "created_at": _iso(item.created_at), "updated_at": _iso(item.updated_at)}


def _proposal_out(item: m.ProductProposal, user: m.User) -> dict:
    return {"id": item.id, "customer_id": item.customer_id, "project_id": item.project_id,
            "building_id": item.building_id, "floor_id": item.floor_id, "room_id": item.room_id,
            "product_family_id": item.product_family_id,
            "product": product_out(item.product, include_price=user.role in ADMIN_ROLES),
            "quantity": float(item.quantity), "unit": item.unit, "notes": item.notes,
            "recommendation": item.recommendation, "customer_comment": item.customer_comment,
            "status": item.status, "proposed_by": item.proposed_by, "proposed_at": _iso(item.proposed_at),
            "sent_at": _iso(item.sent_at), "withdrawn_at": _iso(item.withdrawn_at),
            "decided_by": item.decided_by, "decided_at": _iso(item.decided_at),
            "linked_inquiry_id": item.linked_inquiry_id}


def _legacy_room_products(db: Session, room_id: str, project_id: str, user: m.User) -> list[dict]:
    rows = db.scalars(select(m.RoomRequirement).join(m.Inquiry).options(
        selectinload(m.RoomRequirement.product).selectinload(m.Product.category),
        selectinload(m.RoomRequirement.product).selectinload(m.Product.family).selectinload(m.ProductFamily.media),
        selectinload(m.RoomRequirement.product).selectinload(m.Product.media),
    ).where(
        m.RoomRequirement.room_id == room_id,
        m.Inquiry.project_id == project_id,
    ).order_by(desc(m.Inquiry.updated_at), desc(m.RoomRequirement.id))).unique().all()
    # Existing deployments stored room selections per inquiry. For the current room
    # view, use the latest row for each exact variant instead of adding historical BOQs.
    seen: set[str] = set()
    result: list[dict] = []
    for row in rows:
        if row.product_id in seen:
            continue
        seen.add(row.product_id)
        result.append({"id": f"legacy:{row.id}", "project_id": project_id,
                       "building_id": row.room.floor.building_id, "floor_id": row.room.floor_id,
                       "room_id": room_id, "product": product_out(row.product, user.role in ADMIN_ROLES),
                       "quantity": float(row.quantity), "unit": row.unit, "notes": row.notes,
                       "approval_status": "ADDED", "source": "INQUIRY",
                       "linked_inquiry_id": row.inquiry_id, "created_at": None, "updated_at": None})
    return result


def _upsert_room_product(db: Session, room: m.Room, floor: m.Floor, building: m.Building,
                         project: m.Project, product: m.Product, quantity: Decimal,
                         notes: str | None, status: str, source: str, actor_id: str,
                         linked_inquiry_id: str | None) -> m.RoomProduct:
    existing = db.scalar(select(m.RoomProduct).where(
        m.RoomProduct.room_id == room.id, m.RoomProduct.product_id == product.id
    ).with_for_update())
    if existing:
        existing.quantity = Decimal(existing.quantity) + quantity
        existing.notes = notes if notes is not None else existing.notes
        existing.approval_status = status
        existing.source = source
        existing.updated_by = actor_id
        if linked_inquiry_id:
            existing.linked_inquiry_id = linked_inquiry_id
        return existing
    item = m.RoomProduct(project_id=project.id, building_id=building.id, floor_id=floor.id,
                         room_id=room.id, product_id=product.id, quantity=quantity,
                         unit=product.unit, notes=notes, approval_status=status, source=source,
                         linked_inquiry_id=linked_inquiry_id, created_by=actor_id, updated_by=actor_id)
    db.add(item); db.flush(); return item


def _sync_requirement(db: Session, inquiry_id: str | None, room: m.Room, product: m.Product,
                      quantity: Decimal, notes: str | None) -> None:
    if not inquiry_id:
        return
    inquiry = db.get(m.Inquiry, inquiry_id)
    if not inquiry or inquiry.project_id != room.floor.building.project_id:
        raise HTTPException(422, "Linked inquiry does not belong to this room's project")
    requirement = db.scalar(select(m.RoomRequirement).where(
        m.RoomRequirement.inquiry_id == inquiry.id,
        m.RoomRequirement.room_id == room.id,
        m.RoomRequirement.product_id == product.id,
    ).with_for_update())
    if requirement:
        requirement.quantity = Decimal(requirement.quantity) + quantity
        requirement.notes = notes if notes is not None else requirement.notes
    else:
        db.add(m.RoomRequirement(inquiry_id=inquiry.id, room_id=room.id, product_id=product.id,
                                 quantity=quantity, unit=product.unit, notes=notes))


@router.patch("/customers/{customer_id}", dependencies=[Depends(require_csrf)])
def update_customer(customer_id: str, body: CustomerPatch, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    customer = db.get(m.Customer, customer_id)
    if not customer:
        raise HTTPException(404, "Customer not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(customer, field, value.upper() if field == "status" and value else value)
    audit(db, user.id, "customer.updated", "customer", customer.id)
    db.commit(); return customer_out(customer)


@router.patch("/projects/{project_id}", dependencies=[Depends(require_csrf)])
def update_project(project_id: str, body: ProjectPatch, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    project = db.get(m.Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    data = body.model_dump(exclude_unset=True)
    if data.get("owner_id") and not db.get(m.User, data["owner_id"]):
        raise HTTPException(422, "Internal owner not found")
    for field, value in data.items():
        setattr(project, field, value.upper() if field == "status" and value else value)
    audit(db, user.id, "project.updated", "project", project.id)
    db.commit(); return project_basic(project)


@router.get("/projects/{project_id}/buildings")
def project_buildings(project_id: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    project = db.get(m.Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    ensure_project_access(db, user, project.id)
    scoped_building = None if user.role in ADMIN_ROLES else db.scalar(select(m.ProjectUser.building_id).where(
        m.ProjectUser.project_id == project.id, m.ProjectUser.user_id == user.id, m.ProjectUser.status == "ACTIVE"))
    buildings = db.scalars(select(m.Building).where(m.Building.project_id == project.id).order_by(m.Building.sort_order, m.Building.name)).all()
    if scoped_building:
        buildings = [building for building in buildings if building.id == scoped_building]
    result = []
    for building in buildings:
        floors = db.scalars(select(m.Floor.id).where(m.Floor.building_id == building.id)).all()
        rooms = db.scalars(select(m.Room.id).where(m.Room.floor_id.in_(floors))).all() if floors else []
        boards = db.scalar(select(func.coalesce(func.sum(m.MainBoard.quantity), 0)).where(m.MainBoard.building_id == building.id)) or 0
        room_products = db.scalars(select(m.RoomProduct).where(m.RoomProduct.building_id == building.id)).all()
        if room_products:
            unique_products = len({row.product_id for row in room_products})
            product_quantity = sum((Decimal(row.quantity) for row in room_products), Decimal("0"))
        else:
            requirements = db.scalars(select(m.RoomRequirement).where(m.RoomRequirement.room_id.in_(rooms))).all() if rooms else []
            unique_products = len({row.product_id for row in requirements})
            product_quantity = sum((Decimal(row.quantity) for row in requirements), Decimal("0"))
        result.append({"id": building.id, "project_id": building.project_id, "name": building.name,
                       "code": building.code, "building_type": building.building_type,
                       "address": building.address, "status": building.status,
                       "planned_floors": building.planned_floors, "floor_count": len(floors),
                       "room_count": len(rooms), "main_board_count": int(boards),
                       "unique_product_count": unique_products, "product_quantity": float(product_quantity),
                       "updated_at": _iso(building.updated_at)})
    return result


@router.post("/projects/{project_id}/buildings", dependencies=[Depends(require_csrf)])
def create_building(project_id: str, body: BuildingIn, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    project = db.get(m.Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    next_order = db.scalar(select(func.coalesce(func.max(m.Building.sort_order), -1)).where(m.Building.project_id == project.id)) + 1
    building = m.Building(project_id=project.id, sort_order=next_order,
                          **body.model_dump(exclude={"status"}), status=body.status.upper())
    db.add(building); db.flush()
    audit(db, user.id, "building.created", "building", building.id, {"project_id": project.id})
    db.commit(); return {"id": building.id, "project_id": project.id, "name": building.name}


@router.patch("/projects/{project_id}/buildings/{building_id}", dependencies=[Depends(require_csrf)])
def update_building(project_id: str, building_id: str, body: BuildingPatch, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    building = db.get(m.Building, building_id)
    if not building:
        raise HTTPException(404, "Building not found")
    if building.project_id != project_id:
        raise HTTPException(404, "Building not found in this project")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(building, field, value.upper() if field == "status" and value else value)
    audit(db, user.id, "building.updated", "building", building.id)
    db.commit(); return {"id": building.id, "project_id": building.project_id, "name": building.name,
                         "code": building.code, "building_type": building.building_type,
                         "address": building.address, "status": building.status}


@router.get("/projects/{project_id}/buildings/{building_id}")
def building_detail(project_id: str, building_id: str, workspace: str | None = None, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    project = db.scalar(select(m.Project).options(selectinload(m.Project.customer), selectinload(m.Project.partner), selectinload(m.Project.owner)).where(m.Project.id == project_id))
    if not project:
        raise HTTPException(404, "Project not found")
    ensure_project_access(db, user, project.id)
    show_commercial = can_view_commercial(db, user, project.id)
    show_prices = can_view_prices(db, user, project.id)
    building = db.get(m.Building, building_id)
    if not building or building.project_id != project.id:
        raise HTTPException(404, "Building not found in this project")
    ensure_building_access(db, user, project.id, building.id)
    floors = db.scalars(select(m.Floor).where(m.Floor.building_id == building.id).order_by(m.Floor.sort_order, m.Floor.name)).all()
    floor_ids = [floor.id for floor in floors]
    rooms = db.scalars(select(m.Room).where(m.Room.floor_id.in_(floor_ids)).order_by(m.Room.sort_order, m.Room.name)).all() if floor_ids else []
    boards = db.scalars(select(m.MainBoard).where(m.MainBoard.building_id == building.id).order_by(m.MainBoard.floor_id, m.MainBoard.name)).all()
    active = workspace.upper() if workspace else None
    if active:
        from .deps import ensure_workspace
        ensure_workspace(user, active)
    room_product_stmt = select(m.RoomProduct).join(m.Product).options(
        selectinload(m.RoomProduct.product).selectinload(m.Product.category),
        selectinload(m.RoomProduct.product).selectinload(m.Product.family).selectinload(m.ProductFamily.media),
        selectinload(m.RoomProduct.product).selectinload(m.Product.media),
    ).where(m.RoomProduct.building_id == building.id)
    if active: room_product_stmt = room_product_stmt.where(m.Product.workspace == active)
    room_products = db.scalars(room_product_stmt).unique().all()
    room_map: dict[str, list[m.RoomProduct]] = defaultdict(list)
    for item in room_products:
        room_map[item.room_id].append(item)
    boards_by_floor: dict[str, list[m.MainBoard]] = defaultdict(list)
    for board in boards:
        boards_by_floor[board.floor_id].append(board)
    rooms_by_floor: dict[str, list[m.Room]] = defaultdict(list)
    for room in rooms:
        rooms_by_floor[room.floor_id].append(room)
    floor_rows = []
    unique: set[str] = set()
    total_quantity = Decimal("0")
    for floor in floors:
        room_rows = []
        for room in rooms_by_floor[floor.id]:
            items = [_room_product_out(item, user) for item in room_map.get(room.id, [])]
            if not items:
                items = _legacy_room_products(db, room.id, project.id, user)
            unique.update(item["product"]["id"] for item in items)
            qty = sum((Decimal(str(item["quantity"])) for item in items), Decimal("0"))
            total_quantity += qty
            thumbs = [item["product"].get("primary_image_url") for item in items if item["product"].get("primary_image_url")][:3]
            room_boards = [board for board in boards_by_floor[floor.id] if board.room_id == room.id]
            room_rows.append({"id": room.id, "name": room.name, "room_type": room.room_type,
                              "area": float(room.area) if room.area is not None else None,
                              "occupancy": room.occupancy, "notes": room.notes,
                              "main_board_count": sum(board.quantity for board in room_boards),
                              "unique_product_count": len(items), "product_quantity": float(qty),
                              "configuration_status": "CONFIGURED" if items else "NOT_CONFIGURED",
                              "product_thumbnails": thumbs})
        floor_rows.append({"id": floor.id, "name": floor.name, "sort_order": floor.sort_order,
                           "room_count": len(room_rows),
                           "main_board_count": sum(board.quantity for board in boards_by_floor[floor.id]),
                           "unique_product_count": len({item.product_id for room in rooms_by_floor[floor.id] for item in room_map.get(room.id, [])}),
                           "product_quantity": sum(room["product_quantity"] for room in room_rows),
                           "configuration_status": "CONFIGURED" if room_rows and all(room["configuration_status"] == "CONFIGURED" for room in room_rows) else "IN_PROGRESS",
                           "rooms": room_rows})
    inquiry_stmt = select(m.Inquiry).where(m.Inquiry.project_id == project.id, or_(m.Inquiry.building_id == building.id, m.Inquiry.is_project_wide.is_(True)))
    if active: inquiry_stmt = inquiry_stmt.where(m.Inquiry.workspace == active)
    inquiries = db.scalars(inquiry_stmt.order_by(desc(m.Inquiry.created_at))).all()
    inquiry_ids = [item.id for item in inquiries]
    quotations = db.scalars(select(m.Quotation).where(m.Quotation.inquiry_id.in_(inquiry_ids)).order_by(desc(m.Quotation.quotation_date))).all() if inquiry_ids else []
    quote_ids = [item.id for item in quotations]
    orders = db.scalars(select(m.Order).where(m.Order.quotation_id.in_(quote_ids)).order_by(desc(m.Order.order_date))).all() if quote_ids else []
    order_ids = [item.id for item in orders]
    invoices = db.scalars(select(m.Invoice).where(m.Invoice.order_id.in_(order_ids)).order_by(desc(m.Invoice.invoice_date))).all() if order_ids else []
    project_users = db.scalar(select(func.count(m.ProjectUser.id)).where(m.ProjectUser.project_id == project.id, m.ProjectUser.status == "ACTIVE")) or 0
    outstanding = sum((Decimal(inv.grand_total) for inv in invoices if inv.status not in {"PAID", "CANCELLED"}), Decimal("0"))
    return {
        "customer": customer_out(project.customer),
        "project": {**project_basic(project), "owner": {"id": project.owner.id, "name": project.owner.name} if project.owner else None,
                    "partner": partner_out(project.partner), "created_at": _iso(project.created_at), "updated_at": _iso(project.updated_at)},
        "building": {"id": building.id, "project_id": building.project_id, "name": building.name,
                     "code": building.code, "building_type": building.building_type,
                     "address": building.address, "status": building.status,
                     "planned_floors": building.planned_floors,
                     "created_at": _iso(building.created_at), "updated_at": _iso(building.updated_at)},
        "stats": {"floors": len(floors), "rooms": len(rooms), "main_boards": sum(board.quantity for board in boards),
                  "unique_products": len(unique), "product_quantity": float(total_quantity),
                  "users": int(project_users), "open_inquiries": len([i for i in inquiries if i.status not in {"COMPLETED", "CANCELLED"}]),
                  "active_quotation": next((q.status for q in quotations if q.status in {"DRAFT", "SENT", "ACCEPTED"}), None),
                  "order_status": orders[0].status if orders else None,
                  "invoice_status": invoices[0].status if invoices else None,
                  "outstanding": float(outstanding)},
        "floors": floor_rows,
        "main_boards": [_board_out(board) for board in boards],
        "inquiries": [{"id": i.id, "number": i.number, "status": i.status,
                       "created_at": _iso(i.created_at), "building_scope": building.name if i.building_id else "Project-wide"} for i in inquiries],
        "quotations": [quote_out(q, db, False, show_prices) for q in quotations] if show_commercial else [],
        "orders": [order_out(o, db, False, show_prices) for o in orders] if show_commercial else [],
        "invoices": [invoice_out(inv, db, show_prices) for inv in invoices] if show_commercial else [],
    }


@router.get("/buildings/{building_id}/floors")
def building_floors(building_id: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    building = db.get(m.Building, building_id)
    if not building:
        raise HTTPException(404, "Building not found")
    ensure_project_access(db, user, building.project_id)
    ensure_building_access(db, user, building.project_id, building.id)
    return [{"id": floor.id, "building_id": floor.building_id, "name": floor.name, "sort_order": floor.sort_order}
            for floor in db.scalars(select(m.Floor).where(m.Floor.building_id == building.id).order_by(m.Floor.sort_order)).all()]


@router.get("/floors/{floor_id}/rooms")
def floor_rooms(floor_id: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    floor = db.get(m.Floor, floor_id)
    if not floor:
        raise HTTPException(404, "Floor not found")
    ensure_project_access(db, user, floor.building.project_id)
    ensure_building_access(db, user, floor.building.project_id, floor.building_id)
    return [{"id": room.id, "floor_id": room.floor_id, "name": room.name,
             "room_type": room.room_type, "area": float(room.area) if room.area is not None else None,
             "occupancy": room.occupancy, "notes": room.notes}
            for room in db.scalars(select(m.Room).where(m.Room.floor_id == floor.id).order_by(m.Room.sort_order, m.Room.name)).all()]


@router.get("/rooms/{room_id}")
def room_detail(room_id: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    room, floor, building, project = _room_scope(db, room_id)
    ensure_project_access(db, user, project.id)
    ensure_building_access(db, user, project.id, building.id)
    selections = db.scalars(select(m.RoomProduct).options(
        selectinload(m.RoomProduct.product).selectinload(m.Product.category),
        selectinload(m.RoomProduct.product).selectinload(m.Product.family).selectinload(m.ProductFamily.media),
        selectinload(m.RoomProduct.product).selectinload(m.Product.media),
    ).where(m.RoomProduct.room_id == room.id).order_by(m.RoomProduct.created_at)).unique().all()
    products = [_room_product_out(item, user) for item in selections]
    if not products:
        products = _legacy_room_products(db, room.id, project.id, user)
    boards = db.scalars(select(m.MainBoard).where(or_(m.MainBoard.room_id == room.id,
                                                      (m.MainBoard.floor_id == floor.id) & (m.MainBoard.room_id.is_(None)))).order_by(m.MainBoard.name)).all()
    proposals_stmt = select(m.ProductProposal).options(
        selectinload(m.ProductProposal.product).selectinload(m.Product.category),
        selectinload(m.ProductProposal.product).selectinload(m.Product.family).selectinload(m.ProductFamily.media),
        selectinload(m.ProductProposal.product).selectinload(m.Product.media),
    ).where(m.ProductProposal.room_id == room.id)
    if user.role not in ADMIN_ROLES:
        proposals_stmt = proposals_stmt.where(m.ProductProposal.status != "WITHDRAWN")
    proposals = db.scalars(proposals_stmt.order_by(desc(m.ProductProposal.created_at))).unique().all()
    return {"customer": customer_out(project.customer), "project": project_basic(project),
            "building": {"id": building.id, "name": building.name},
            "floor": {"id": floor.id, "name": floor.name},
            "room": {"id": room.id, "name": room.name, "room_type": room.room_type,
                     "area": float(room.area) if room.area is not None else None,
                     "occupancy": room.occupancy, "notes": room.notes,
                     "configuration_status": "CONFIGURED" if products else "NOT_CONFIGURED"},
            "products": products, "main_boards": [_board_out(board) for board in boards],
            "proposals": [_proposal_out(item, user) for item in proposals]}


@router.get("/rooms/{room_id}/products")
def room_products(room_id: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    return room_detail(room_id, db, user)["products"]


@router.post("/rooms/{room_id}/products", dependencies=[Depends(require_csrf)])
def add_room_product(room_id: str, body: RoomProductIn, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    room, floor, building, project = _room_scope(db, room_id)
    product = db.get(m.Product, body.product_id)
    if not product or product.status != "ACTIVE":
        raise HTTPException(422, "Product variant is unavailable")
    if body.linked_inquiry_id:
        inquiry = db.get(m.Inquiry, body.linked_inquiry_id)
        if not inquiry or inquiry.project_id != project.id:
            raise HTTPException(422, "Linked inquiry does not belong to this project")
        if product.workspace != inquiry.workspace:
            raise HTTPException(422, "Cross-application product selection is not allowed")
    elif body.workspace and product.workspace != body.workspace.upper():
        raise HTTPException(422, "Product does not belong to the active application")
    item = _upsert_room_product(db, room, floor, building, project, product, body.quantity,
                                body.notes, "ADDED", "ADMIN_SELECTION", user.id, body.linked_inquiry_id)
    _sync_requirement(db, body.linked_inquiry_id, room, product, body.quantity, body.notes)
    audit(db, user.id, "room_product.added", "room", room.id,
          {"product_id": product.id, "quantity": float(body.quantity)})
    db.commit(); db.refresh(item)
    return _room_product_out(item, user)


@router.patch("/rooms/{room_id}/products/{selection_id}", dependencies=[Depends(require_csrf)])
def update_room_product(room_id: str, selection_id: str, body: RoomProductPatch,
                        db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    room, _, _, project = _room_scope(db, room_id)
    item = db.get(m.RoomProduct, selection_id)
    if not item or item.room_id != room.id or item.project_id != project.id:
        raise HTTPException(404, "Room product not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(item, field, value.upper() if field == "approval_status" and value else value)
    item.updated_by = user.id
    audit(db, user.id, "room_product.updated", "room_product", item.id)
    db.commit(); return _room_product_out(item, user)


@router.delete("/rooms/{room_id}/products/{selection_id}", dependencies=[Depends(require_csrf)])
def delete_room_product(room_id: str, selection_id: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    room, _, _, project = _room_scope(db, room_id)
    item = db.get(m.RoomProduct, selection_id)
    if not item or item.room_id != room.id or item.project_id != project.id:
        raise HTTPException(404, "Room product not found")
    db.delete(item)
    audit(db, user.id, "room_product.removed", "room_product", item.id, {"room_id": room.id})
    db.commit(); return {"ok": True}


@router.post("/rooms/{room_id}/product-proposals", dependencies=[Depends(require_csrf)])
def create_proposal(room_id: str, body: ProposalIn, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    room, floor, building, project = _room_scope(db, room_id)
    product = db.get(m.Product, body.product_id)
    if not product or product.status != "ACTIVE":
        raise HTTPException(422, "Product variant is unavailable")
    now = datetime.now(timezone.utc)
    status = "PENDING_CUSTOMER" if body.send_to_customer else "DRAFT"
    proposal = m.ProductProposal(customer_id=project.customer_id, project_id=project.id,
                                 building_id=building.id, floor_id=floor.id, room_id=room.id,
                                 product_family_id=product.family_id, product_id=product.id,
                                 quantity=body.quantity, unit=product.unit, notes=body.notes,
                                 recommendation=body.recommendation,
                                 status=status, proposed_by=user.id,
                                 sent_at=now if body.send_to_customer else None,
                                 linked_inquiry_id=body.linked_inquiry_id)
    db.add(proposal); db.flush()
    audit(db, user.id, "product_proposal.created", "product_proposal", proposal.id,
          {"room_id": room.id, "product_id": product.id, "status": status})
    db.commit(); return _proposal_out(proposal, user)


@router.patch("/product-proposals/{proposal_id}/decision", dependencies=[Depends(require_csrf)])
def decide_proposal(proposal_id: str, body: ProposalDecision, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    proposal = db.get(m.ProductProposal, proposal_id)
    if not proposal:
        raise HTTPException(404, "Product proposal not found")
    if user.role in ADMIN_ROLES:
        raise HTTPException(403, "A customer project user must approve or reject this proposal")
    require_project_permission(db, user, proposal.project_id, "proposals.decide")
    if proposal.status != "PENDING_CUSTOMER":
        raise HTTPException(409, "This proposal already has a final decision")
    room, floor, building, project = _room_scope(db, proposal.room_id)
    decision = body.decision.upper()
    proposal.decided_by = user.id
    proposal.decided_at = datetime.now(timezone.utc)
    proposal.customer_comment = body.comment
    if decision == "REJECTED":
        proposal.status = "REJECTED"
    else:
        proposal.status = "APPROVED"
        _upsert_room_product(db, room, floor, building, project, proposal.product,
                             Decimal(proposal.quantity), proposal.notes, proposal.status,
                             "CUSTOMER_APPROVAL",
                             user.id, proposal.linked_inquiry_id)
        _sync_requirement(db, proposal.linked_inquiry_id, room, proposal.product,
                          Decimal(proposal.quantity), proposal.notes)
    audit(db, user.id, "product_proposal.decided", "product_proposal", proposal.id, {"decision": decision})
    db.commit(); return _proposal_out(proposal, user)


@router.get("/product-proposals/pending")
def pending_proposals(project_id: str | None = None, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    stmt = select(m.ProductProposal).options(
        selectinload(m.ProductProposal.product).selectinload(m.Product.category),
        selectinload(m.ProductProposal.product).selectinload(m.Product.family).selectinload(m.ProductFamily.media),
        selectinload(m.ProductProposal.product).selectinload(m.Product.media),
    ).where(m.ProductProposal.status == "PENDING_CUSTOMER")
    if project_id:
        ensure_project_access(db, user, project_id)
        stmt = stmt.where(m.ProductProposal.project_id == project_id)
    elif user.role not in ADMIN_ROLES:
        project_ids = db.scalars(select(m.ProjectUser.project_id).where(
            m.ProjectUser.user_id == user.id, m.ProjectUser.status == "ACTIVE"
        )).all()
        stmt = stmt.where(m.ProductProposal.project_id.in_(project_ids))
    return [_proposal_out(item, user) for item in db.scalars(stmt.order_by(desc(m.ProductProposal.sent_at))).unique().all()]


@router.post("/product-proposals/{proposal_id}/withdraw", dependencies=[Depends(require_csrf)])
def withdraw_proposal(proposal_id: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    proposal = db.get(m.ProductProposal, proposal_id)
    if not proposal:
        raise HTTPException(404, "Product proposal not found")
    if proposal.status not in {"DRAFT", "PENDING_CUSTOMER"}:
        raise HTTPException(409, "Only draft or pending proposals can be withdrawn")
    proposal.status = "WITHDRAWN"; proposal.withdrawn_at = datetime.now(timezone.utc)
    audit(db, user.id, "product_proposal.withdrawn", "product_proposal", proposal.id)
    db.commit(); return _proposal_out(proposal, user)


@router.get("/projects/{project_id}/buildings/{building_id}/main-boards")
def building_boards(project_id: str, building_id: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    building = db.get(m.Building, building_id)
    if not building or building.project_id != project_id:
        raise HTTPException(404, "Building not found in this project")
    ensure_project_access(db, user, project_id)
    ensure_building_access(db, user, project_id, building_id)
    return [_board_out(board) for board in db.scalars(select(m.MainBoard).where(m.MainBoard.building_id == building.id).order_by(m.MainBoard.name)).all()]


@router.post("/projects/{project_id}/buildings/{building_id}/main-boards", dependencies=[Depends(require_csrf)])
def create_board(project_id: str, building_id: str, body: BoardIn, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    building = db.get(m.Building, building_id)
    floor = db.get(m.Floor, body.floor_id)
    if not building or building.project_id != project_id:
        raise HTTPException(404, "Building not found in this project")
    if not floor or floor.building_id != building.id:
        raise HTTPException(422, "Floor does not belong to this building")
    if body.room_id:
        room = db.get(m.Room, body.room_id)
        if not room or room.floor_id != floor.id:
            raise HTTPException(422, "Room does not belong to this floor")
    system = body.system.upper()
    if system not in {"LIGHTING", "AUTOMATION", "MIXED"}:
        raise HTTPException(422, "System must be LIGHTING, AUTOMATION, or MIXED")
    board = m.MainBoard(project_id=project_id, building_id=building_id,
                        **body.model_dump(exclude={"system"}), system=system)
    db.add(board); db.flush()
    audit(db, user.id, "main_board.created", "main_board", board.id)
    db.commit(); return _board_out(board)
