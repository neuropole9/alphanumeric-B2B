from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import re
import secrets

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models as m
from .api import (
    admin_required, ensure_project_access, invoice_out, project_basic,
    project_user_out, quote_out, require_project_permission,
)
from .config import settings
from .db import get_db
from .deps import get_current_user, require_csrf
from .security import hash_password, verify_password
from .services import audit, money, next_number, recalc_quotation

router = APIRouter(prefix="/api/v1", tags=["release completion"])


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    address: str | None = None
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    expected_completion: datetime | None = None
    notes: str | None = None
    workspace_scope: list[str] = []


class FloorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    sort_order: int | None = Field(default=None, ge=0)


class FloorPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int | None = Field(default=None, ge=0)
    status: str | None = None


class RoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    room_type: str | None = Field(default=None, max_length=100)
    area: Decimal | None = Field(default=None, ge=0)
    occupancy: int | None = Field(default=None, ge=0)
    notes: str | None = None
    sort_order: int | None = Field(default=None, ge=0)


class RoomPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    room_type: str | None = Field(default=None, max_length=100)
    area: Decimal | None = Field(default=None, ge=0)
    occupancy: int | None = Field(default=None, ge=0)
    notes: str | None = None
    sort_order: int | None = Field(default=None, ge=0)
    status: str | None = None


class BoardPatch(BaseModel):
    floor_id: str | None = None
    room_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=140)
    code: str | None = Field(default=None, max_length=80)
    board_type: str | None = Field(default=None, min_length=1, max_length=100)
    system: str | None = None
    quantity: int | None = Field(default=None, gt=0)
    notes: str | None = None
    status: str | None = None
    sort_order: int | None = Field(default=None, ge=0)


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=60)
    is_primary: bool = False


class StakeholderIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    stakeholder_type: str = Field(min_length=1, max_length=60)
    organization: str | None = Field(default=None, max_length=180)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=60)
    notes: str | None = None


class SpecDefinitionIn(BaseModel):
    spec_key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    label: str = Field(min_length=1, max_length=120)
    data_type: str = Field(default="text", pattern="^(text|number|boolean|select)$")
    unit: str | None = Field(default=None, max_length=40)
    required: bool = False
    allowed_values: list[str] = []
    sort_order: int = Field(default=0, ge=0)


class QuotationTermsIn(BaseModel):
    valid_until: datetime | None = None
    payment_terms: str | None = Field(default=None, max_length=255)
    delivery_terms: str | None = None
    warranty_terms: str | None = None
    notes: str | None = None


class PaymentIn(BaseModel):
    amount: Decimal = Field(gt=0)
    method: str = Field(min_length=1, max_length=60)
    reference: str | None = Field(default=None, max_length=120)
    paid_at: datetime | None = None
    notes: str | None = None


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12)


def _floor_out(row: m.Floor) -> dict:
    return {"id": row.id, "building_id": row.building_id, "name": row.name,
            "sort_order": row.sort_order, "status": row.status}


def _room_out(row: m.Room) -> dict:
    return {"id": row.id, "floor_id": row.floor_id, "name": row.name,
            "room_type": row.room_type, "area": float(row.area) if row.area is not None else None,
            "occupancy": row.occupancy, "notes": row.notes, "sort_order": row.sort_order,
            "status": row.status}


def _board_out(row: m.MainBoard) -> dict:
    return {"id": row.id, "project_id": row.project_id, "building_id": row.building_id,
            "floor_id": row.floor_id, "room_id": row.room_id, "name": row.name,
            "code": row.code, "board_type": row.board_type, "system": row.system,
            "quantity": row.quantity, "notes": row.notes, "status": row.status,
            "sort_order": row.sort_order}


def _document_out(row: m.ProjectDocument) -> dict:
    return {"id": row.id, "project_id": row.project_id, "building_id": row.building_id,
            "floor_id": row.floor_id, "room_id": row.room_id, "title": row.title,
            "document_type": row.document_type, "revision": row.revision,
            "file_name": row.file_name, "mime_type": row.mime_type, "size_bytes": row.size_bytes,
            "notes": row.notes, "status": row.status, "uploaded_by": row.uploaded_by,
            "created_at": row.created_at.isoformat(),
            "preview_url": f"/api/v1/project-documents/{row.id}/file",
            "download_url": f"/api/v1/project-documents/{row.id}/file?download=true"}


def _validate_scope(db: Session, project_id: str, building_id: str | None,
                    floor_id: str | None, room_id: str | None) -> None:
    building = db.get(m.Building, building_id) if building_id else None
    if building_id and (not building or building.project_id != project_id):
        raise HTTPException(422, "Building does not belong to the selected project")
    floor = db.get(m.Floor, floor_id) if floor_id else None
    if floor_id and (not floor or not building or floor.building_id != building.id):
        raise HTTPException(422, "Floor does not belong to the selected building")
    room = db.get(m.Room, room_id) if room_id else None
    if room_id and (not room or not floor or room.floor_id != floor.id):
        raise HTTPException(422, "Room does not belong to the selected floor")


def _safe_file_name(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(value).name).strip(".-")
    return clean[:180] or "document"


@router.post("/customers/{customer_id}/projects", dependencies=[Depends(require_csrf)])
def create_project(customer_id: str, body: ProjectIn, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    if not db.get(m.Customer, customer_id):
        raise HTTPException(404, "Customer not found")
    duplicate = db.scalar(select(m.Project).where(
        m.Project.customer_id == customer_id,
        func.lower(m.Project.name) == body.name.strip().lower(),
        m.Project.status == "ACTIVE",
    ))
    if duplicate:
        raise HTTPException(409, "An active project with this name already exists")
    row = m.Project(customer_id=customer_id, owner_id=user.id, name=body.name.strip(),
                    address=body.address, city=body.city, state=body.state,
                    expected_completion=body.expected_completion.date() if body.expected_completion else None,
                    notes=body.notes, workspace_scope=[x.upper() for x in body.workspace_scope])
    db.add(row); db.flush(); audit(db, user.id, "project.created", "project", row.id)
    db.commit(); return project_basic(row)


@router.post("/projects/{project_id}/buildings/{building_id}/floors", dependencies=[Depends(require_csrf)])
def create_floor(project_id: str, building_id: str, body: FloorCreate, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    building = db.get(m.Building, building_id)
    if not building or building.project_id != project_id:
        raise HTTPException(404, "Building not found in this project")
    if db.scalar(select(m.Floor.id).where(m.Floor.building_id == building_id,
                                          func.lower(m.Floor.name) == body.name.strip().lower(),
                                          m.Floor.status == "ACTIVE")):
        raise HTTPException(409, "An active floor with this name already exists")
    sort_order = body.sort_order
    if sort_order is None:
        sort_order = (db.scalar(select(func.max(m.Floor.sort_order)).where(m.Floor.building_id == building_id)) or -1) + 1
    row = m.Floor(building_id=building_id, name=body.name.strip(), sort_order=sort_order)
    db.add(row); db.flush(); audit(db, user.id, "floor.created", "floor", row.id)
    db.commit(); return _floor_out(row)


@router.patch("/floors/{floor_id}", dependencies=[Depends(require_csrf)])
def update_floor(floor_id: str, body: FloorPatch, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    row = db.get(m.Floor, floor_id)
    if not row: raise HTTPException(404, "Floor not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value.upper() if field == "status" and value else value)
    audit(db, user.id, "floor.updated", "floor", row.id); db.commit(); return _floor_out(row)


@router.delete("/floors/{floor_id}", dependencies=[Depends(require_csrf)])
def archive_floor(floor_id: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    row = db.get(m.Floor, floor_id)
    if not row: raise HTTPException(404, "Floor not found")
    row.status = "ARCHIVED"; audit(db, user.id, "floor.archived", "floor", row.id)
    db.commit(); return _floor_out(row)


@router.post("/floors/{floor_id}/rooms", dependencies=[Depends(require_csrf)])
def create_room(floor_id: str, body: RoomCreate, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    floor = db.get(m.Floor, floor_id)
    if not floor: raise HTTPException(404, "Floor not found")
    if db.scalar(select(m.Room.id).where(m.Room.floor_id == floor_id,
                                         func.lower(m.Room.name) == body.name.strip().lower(),
                                         m.Room.status == "ACTIVE")):
        raise HTTPException(409, "An active room with this name already exists")
    sort_order = body.sort_order
    if sort_order is None:
        sort_order = (db.scalar(select(func.max(m.Room.sort_order)).where(m.Room.floor_id == floor_id)) or -1) + 1
    row = m.Room(**body.model_dump(exclude={"sort_order"}), floor_id=floor_id, sort_order=sort_order)
    db.add(row); db.flush(); audit(db, user.id, "room.created", "room", row.id)
    db.commit(); return _room_out(row)


@router.patch("/rooms/{room_id}", dependencies=[Depends(require_csrf)])
def update_room(room_id: str, body: RoomPatch, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    row = db.get(m.Room, room_id)
    if not row: raise HTTPException(404, "Room not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value.upper() if field == "status" and value else value)
    audit(db, user.id, "room.updated", "room", row.id); db.commit(); return _room_out(row)


@router.delete("/rooms/{room_id}", dependencies=[Depends(require_csrf)])
def archive_room(room_id: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    row = db.get(m.Room, room_id)
    if not row: raise HTTPException(404, "Room not found")
    row.status = "ARCHIVED"; audit(db, user.id, "room.archived", "room", row.id)
    db.commit(); return _room_out(row)


@router.get("/projects/{project_id}/buildings/{building_id}/floors/{floor_id}")
def floor_detail(project_id: str, building_id: str, floor_id: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    floor = db.get(m.Floor, floor_id); building = db.get(m.Building, building_id)
    if not floor or not building or building.project_id != project_id or floor.building_id != building_id:
        raise HTTPException(404, "Floor not found in this building")
    ensure_project_access(db, user, project_id)
    rooms = db.scalars(select(m.Room).where(m.Room.floor_id == floor_id).order_by(m.Room.sort_order)).all()
    boards = db.scalars(select(m.MainBoard).where(m.MainBoard.floor_id == floor_id, m.MainBoard.status == "ACTIVE").order_by(m.MainBoard.sort_order)).all()
    product_rows = db.scalars(select(m.RoomProduct).where(m.RoomProduct.floor_id == floor_id)).all()
    return {"project_id": project_id, "building": {"id": building.id, "name": building.name},
            "floor": _floor_out(floor), "rooms": [_room_out(room) for room in rooms if room.status == "ACTIVE"],
            "main_boards": [_board_out(board) for board in boards],
            "product_summary": {"unique_products": len({x.product_id for x in product_rows}),
                                "total_quantity": float(sum((Decimal(x.quantity) for x in product_rows), Decimal("0")))}}


@router.patch("/main-boards/{board_id}", dependencies=[Depends(require_csrf)])
def update_board(board_id: str, body: BoardPatch, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    row = db.get(m.MainBoard, board_id)
    if not row: raise HTTPException(404, "Main board not found")
    data = body.model_dump(exclude_unset=True)
    floor_id = data.get("floor_id", row.floor_id); room_id = data.get("room_id", row.room_id)
    _validate_scope(db, row.project_id, row.building_id, floor_id, room_id)
    for field, value in data.items():
        setattr(row, field, value.upper() if field in {"system", "status"} and value else value)
    audit(db, user.id, "main_board.updated", "main_board", row.id); db.commit(); return _board_out(row)


@router.delete("/main-boards/{board_id}", dependencies=[Depends(require_csrf)])
def archive_board(board_id: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    row = db.get(m.MainBoard, board_id)
    if not row: raise HTTPException(404, "Main board not found")
    row.status = "ARCHIVED"; audit(db, user.id, "main_board.archived", "main_board", row.id)
    db.commit(); return _board_out(row)


@router.get("/customers/{customer_id}/contacts")
def customer_contacts(customer_id: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    return [{"id": row.id, "name": row.name, "role": row.role, "email": row.email,
             "phone": row.phone, "is_primary": row.is_primary, "status": row.status}
            for row in db.scalars(select(m.CustomerContact).where(m.CustomerContact.customer_id == customer_id)).all()]


@router.post("/customers/{customer_id}/contacts", dependencies=[Depends(require_csrf)])
def add_customer_contact(customer_id: str, body: ContactIn, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    if not db.get(m.Customer, customer_id): raise HTTPException(404, "Customer not found")
    if body.is_primary:
        for current in db.scalars(select(m.CustomerContact).where(m.CustomerContact.customer_id == customer_id)).all():
            current.is_primary = False
    row = m.CustomerContact(customer_id=customer_id, **body.model_dump())
    db.add(row); db.flush(); audit(db, user.id, "customer.contact_created", "customer", customer_id, {"contact_id": row.id})
    db.commit(); return {"id": row.id, **body.model_dump()}


@router.get("/projects/{project_id}/stakeholders")
def project_stakeholders(project_id: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    ensure_project_access(db, user, project_id)
    return [{"id": row.id, "name": row.name, "stakeholder_type": row.stakeholder_type,
             "organization": row.organization, "email": row.email, "phone": row.phone,
             "notes": row.notes, "status": row.status}
            for row in db.scalars(select(m.ProjectStakeholder).where(m.ProjectStakeholder.project_id == project_id)).all()]


@router.post("/projects/{project_id}/stakeholders", dependencies=[Depends(require_csrf)])
def add_project_stakeholder(project_id: str, body: StakeholderIn, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    if not db.get(m.Project, project_id): raise HTTPException(404, "Project not found")
    row = m.ProjectStakeholder(project_id=project_id, **body.model_dump())
    db.add(row); db.flush(); audit(db, user.id, "project.stakeholder_created", "project", project_id, {"stakeholder_id": row.id})
    db.commit(); return {"id": row.id, **body.model_dump(), "status": row.status}


@router.get("/projects/{project_id}/documents")
def project_documents(project_id: str, building_id: str | None = None, floor_id: str | None = None,
                      room_id: str | None = None, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    ensure_project_access(db, user, project_id); _validate_scope(db, project_id, building_id, floor_id, room_id)
    stmt = select(m.ProjectDocument).where(m.ProjectDocument.project_id == project_id, m.ProjectDocument.status == "ACTIVE")
    if building_id: stmt = stmt.where(m.ProjectDocument.building_id == building_id)
    if floor_id: stmt = stmt.where(m.ProjectDocument.floor_id == floor_id)
    if room_id: stmt = stmt.where(m.ProjectDocument.room_id == room_id)
    return [_document_out(row) for row in db.scalars(stmt.order_by(m.ProjectDocument.document_type, m.ProjectDocument.title)).all()]


@router.post("/projects/{project_id}/documents", dependencies=[Depends(require_csrf)])
async def upload_project_document(
    project_id: str, file: UploadFile = File(...), title: str = Form(...), document_type: str = Form(...),
    revision: str = Form("A"), building_id: str | None = Form(None), floor_id: str | None = Form(None),
    room_id: str | None = Form(None), notes: str | None = Form(None),
    db: Session = Depends(get_db), user: m.User = Depends(get_current_user),
):
    admin_required(user); _validate_scope(db, project_id, building_id, floor_id, room_id)
    allowed = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg",
               "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx"}
    mime = (file.content_type or "").lower()
    if mime not in allowed: raise HTTPException(422, "Upload PDF, PNG, JPG, DOCX, or XLSX files only")
    data = await file.read(settings.media_max_bytes + 1)
    if not data or len(data) > settings.media_max_bytes: raise HTTPException(422, "Document is empty or exceeds the configured size limit")
    signatures = {"application/pdf": data.startswith(b"%PDF"), "image/png": data.startswith(b"\x89PNG\r\n\x1a\n"),
                  "image/jpeg": data.startswith(b"\xff\xd8\xff"),
                  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": data.startswith(b"PK"),
                  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": data.startswith(b"PK")}
    if not signatures[mime]: raise HTTPException(422, "File content does not match its declared type")
    root = Path(settings.media_root).expanduser().resolve(); root.mkdir(parents=True, exist_ok=True)
    key = f"documents/{project_id}/{secrets.token_hex(20)}{allowed[mime]}"
    path = (root / key).resolve()
    if root not in path.parents: raise HTTPException(422, "Invalid storage path")
    path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
    row = m.ProjectDocument(project_id=project_id, building_id=building_id, floor_id=floor_id,
                            room_id=room_id, title=title.strip(), document_type=document_type.upper(),
                            revision=revision.strip() or "A", storage_key=key,
                            file_name=_safe_file_name(file.filename or f"document{allowed[mime]}"),
                            mime_type=mime, size_bytes=len(data), notes=notes, uploaded_by=user.id)
    db.add(row); db.flush(); audit(db, user.id, "project_document.uploaded", "project_document", row.id)
    db.commit(); return _document_out(row)


@router.get("/project-documents/{document_id}/file")
def project_document_file(document_id: str, download: bool = False, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    row = db.get(m.ProjectDocument, document_id)
    if not row or row.status != "ACTIVE": raise HTTPException(404, "Document not found")
    ensure_project_access(db, user, row.project_id)
    root = Path(settings.media_root).expanduser().resolve(); path = (root / row.storage_key).resolve()
    if root not in path.parents or not path.is_file(): raise HTTPException(404, "Document file not found")
    disposition = "attachment" if download else "inline"
    audit(db, user.id, "project_document.downloaded", "project_document", row.id, {"download": download}); db.commit()
    return FileResponse(path, media_type=row.mime_type, filename=row.file_name,
                        content_disposition_type=disposition, headers={"Cache-Control": "private, no-store"})


@router.delete("/project-documents/{document_id}", dependencies=[Depends(require_csrf)])
def archive_project_document(document_id: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    row = db.get(m.ProjectDocument, document_id)
    if not row: raise HTTPException(404, "Document not found")
    row.status = "ARCHIVED"; audit(db, user.id, "project_document.archived", "project_document", row.id)
    db.commit(); return _document_out(row)


@router.get("/categories/{category_id}/spec-definitions")
def spec_definitions(category_id: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    if not db.get(m.Category, category_id): raise HTTPException(404, "Category not found")
    return [{"id": row.id, "category_id": row.category_id, "spec_key": row.spec_key,
             "label": row.label, "data_type": row.data_type, "unit": row.unit,
             "required": row.required, "allowed_values": row.allowed_values or [], "sort_order": row.sort_order}
            for row in db.scalars(select(m.ProductSpecDefinition).where(m.ProductSpecDefinition.category_id == category_id).order_by(m.ProductSpecDefinition.sort_order)).all()]


@router.post("/categories/{category_id}/spec-definitions", dependencies=[Depends(require_csrf)])
def add_spec_definition(category_id: str, body: SpecDefinitionIn, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    if not db.get(m.Category, category_id): raise HTTPException(404, "Category not found")
    if body.data_type == "select" and not body.allowed_values: raise HTTPException(422, "Select specifications require allowed values")
    row = m.ProductSpecDefinition(category_id=category_id, **body.model_dump())
    db.add(row); db.flush(); audit(db, user.id, "product_spec_definition.created", "product_spec_definition", row.id)
    db.commit(); return {"id": row.id, "category_id": category_id, **body.model_dump()}


@router.patch("/quotations/{quotation_id}/terms", dependencies=[Depends(require_csrf)])
def update_quotation_terms(quotation_id: str, body: QuotationTermsIn, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    row = db.get(m.Quotation, quotation_id)
    if not row: raise HTTPException(404, "Quotation not found")
    if row.status != "DRAFT": raise HTTPException(409, "Only a draft quotation can be edited")
    data = body.model_dump(exclude_unset=True)
    if data.get("valid_until"): data["valid_until"] = data["valid_until"].date()
    for field, value in data.items(): setattr(row, field, value)
    audit(db, user.id, "quotation.terms_updated", "quotation", row.id); db.commit(); return quote_out(row, db)


@router.post("/quotations/{quotation_id}/revise", dependencies=[Depends(require_csrf)])
def revise_quotation(quotation_id: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    original = db.get(m.Quotation, quotation_id)
    if not original: raise HTTPException(404, "Quotation not found")
    if original.status not in {"SENT", "REJECTED", "EXPIRED"}: raise HTTPException(409, "Only sent, rejected, or expired quotations can be revised")
    revision = m.Quotation(number=next_number(db, "quotation", "QT"), inquiry_id=original.inquiry_id,
                           customer_id=original.customer_id, project_id=original.project_id,
                           building_id=original.building_id, workspace=original.workspace, status="DRAFT",
                           quotation_date=datetime.now(timezone.utc).date(), valid_until=original.valid_until,
                           payment_terms=original.payment_terms, delivery_terms=original.delivery_terms,
                           warranty_terms=original.warranty_terms, notes=original.notes,
                           discount_percent=original.discount_percent, revision=original.revision + 1,
                           supersedes_id=original.id)
    db.add(revision); db.flush()
    for item in db.scalars(select(m.QuotationItem).where(m.QuotationItem.quotation_id == original.id)).all():
        db.add(m.QuotationItem(quotation_id=revision.id, product_id=item.product_id,
                               description=item.description, sku=item.sku, qty=item.qty,
                               rate=item.rate, tax_rate=item.tax_rate, amount=item.amount))
    recalc_quotation(db, revision); original.status = "SUPERSEDED"
    audit(db, user.id, "quotation.revised", "quotation", revision.id, {"supersedes_id": original.id})
    db.commit(); return quote_out(revision, db)


@router.post("/invoices/{invoice_id}/payments", dependencies=[Depends(require_csrf)])
def record_payment(invoice_id: str, body: PaymentIn, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    admin_required(user)
    invoice = db.get(m.Invoice, invoice_id)
    if not invoice: raise HTTPException(404, "Invoice not found")
    current = sum((Decimal(row.amount) for row in db.scalars(select(m.InvoicePayment).where(m.InvoicePayment.invoice_id == invoice.id)).all()), Decimal("0"))
    credits = db.scalar(select(func.coalesce(func.sum(m.FinancialDocument.grand_total), 0)).where(
        m.FinancialDocument.invoice_id == invoice.id, m.FinancialDocument.document_type == "CREDIT_NOTE",
        m.FinancialDocument.status == "ISSUED")) or 0
    debits = db.scalar(select(func.coalesce(func.sum(m.FinancialDocument.grand_total), 0)).where(
        m.FinancialDocument.invoice_id == invoice.id, m.FinancialDocument.document_type == "DEBIT_NOTE",
        m.FinancialDocument.status == "ISSUED")) or 0
    payable = Decimal(invoice.grand_total) - Decimal(credits) + Decimal(debits)
    if current + body.amount > payable: raise HTTPException(422, "Payment exceeds the adjusted invoice balance")
    row = m.InvoicePayment(invoice_id=invoice.id, amount=money(body.amount), method=body.method,
                           reference=body.reference, paid_at=body.paid_at or datetime.now(timezone.utc),
                           recorded_by=user.id, notes=body.notes)
    db.add(row); db.flush(); total = current + Decimal(row.amount)
    invoice.status = "PAID" if total == payable else "PART_PAID"
    audit(db, user.id, "invoice.payment_recorded", "invoice", invoice.id,
          {"payment_id": row.id, "amount": float(row.amount), "status": invoice.status})
    db.commit(); return invoice_out(invoice, db)


@router.post("/auth/change-password", dependencies=[Depends(require_csrf)])
def change_password(body: PasswordChangeIn, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    if not verify_password(body.current_password, user.password_hash): raise HTTPException(422, "Current password is incorrect")
    user.password_hash = hash_password(body.new_password); user.must_change_password = False
    audit(db, user.id, "auth.password_changed", "user", user.id); db.commit()
    return {"ok": True}
