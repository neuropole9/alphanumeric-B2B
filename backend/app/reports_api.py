from __future__ import annotations

from datetime import date
from io import BytesIO
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from .api import ADMIN_ROLES, can_view_prices, ensure_building_access, ensure_project_access
from .db import get_db
from .deps import get_current_user, ensure_workspace
from .reports_TableFormat import building_boq_xlsx, floor_sheet_pdf, project_book_pdf, room_sheet_pdf
from .services import audit

router = APIRouter(prefix="/api/v1", tags=["reports"])


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-")[:80] or "Project"


def _disposition(filename: str, download: bool) -> str:
    return f'{"attachment" if download else "inline"}; filename="{filename}"'


@router.get("/projects/{project_id}/book.pdf")
def project_book(
    project_id: str,
    download: bool = Query(False),
    workspace: str = Query("LIGHTING", pattern="^(LIGHTING|AUTOMATION)$"),
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    project = db.get(m.Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    ensure_project_access(db, user, project.id)
    ensure_workspace(user, workspace)
    scoped_building = None if user.role in ADMIN_ROLES else db.scalar(select(m.ProjectUser.building_id).where(
        m.ProjectUser.project_id == project.id, m.ProjectUser.user_id == user.id, m.ProjectUser.status == "ACTIVE"))
    data = project_book_pdf(db, project, include_prices=can_view_prices(db, user, project.id),
                            building_id=scoped_building, workspace=workspace)
    filename = f"AlphaNumeric_{_slug(project.customer.company_name)}_{_slug(project.name)}_Project-Book_{date.today().isoformat()}.pdf"
    audit(db, user.id, "project_book.generated", "project", project.id)
    db.commit()
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": _disposition(filename, download),
                             "X-Content-Type-Options": "nosniff"})


@router.get("/projects/{project_id}/buildings/{building_id}/book.pdf")
def building_book(
    project_id: str,
    building_id: str,
    download: bool = Query(False),
    workspace: str = Query("LIGHTING", pattern="^(LIGHTING|AUTOMATION)$"),
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    project = db.get(m.Project, project_id)
    building = db.get(m.Building, building_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if not building or building.project_id != project.id:
        raise HTTPException(404, "Building not found in this project")
    ensure_project_access(db, user, project.id)
    ensure_building_access(db, user, project.id, building.id)
    try:
        ensure_workspace(user, workspace)
        data = project_book_pdf(db, project, include_prices=can_view_prices(db, user, project.id), building_id=building.id, workspace=workspace)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    filename = (f"AlphaNumeric_{_slug(project.customer.company_name)}_{_slug(project.name)}_"
                f"{_slug(building.name)}_Building-Book_{date.today().isoformat()}.pdf")
    audit(db, user.id, "building_book.generated", "building", building.id)
    db.commit()
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": _disposition(filename, download),
                             "X-Content-Type-Options": "nosniff"})


@router.get("/projects/{project_id}/buildings/{building_id}/boq.xlsx")
def building_boq(
    project_id: str,
    building_id: str,
    workspace: str = Query("LIGHTING", pattern="^(LIGHTING|AUTOMATION)$"),
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    project = db.get(m.Project, project_id)
    building = db.get(m.Building, building_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if not building or building.project_id != project.id:
        raise HTTPException(404, "Building not found in this project")
    ensure_project_access(db, user, project.id)
    ensure_building_access(db, user, project.id, building.id)
    try:
        ensure_workspace(user, workspace)
        data = building_boq_xlsx(db, project, building.id, include_prices=can_view_prices(db, user, project.id), workspace=workspace)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    filename = f"AlphaNumeric_{_slug(project.name)}_{_slug(building.name)}_BOQ_{date.today().isoformat()}.xlsx"
    audit(db, user.id, "building_boq.generated", "building", building.id)
    db.commit()
    return StreamingResponse(BytesIO(data),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"',
                                      "X-Content-Type-Options": "nosniff"})


@router.get("/projects/{project_id}/boq.xlsx")
def project_boq(
    project_id: str,
    workspace: str = Query("LIGHTING", pattern="^(LIGHTING|AUTOMATION)$"),
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    project = db.get(m.Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    ensure_project_access(db, user, project.id)
    scoped_building = None if user.role in ADMIN_ROLES else db.scalar(select(m.ProjectUser.building_id).where(
        m.ProjectUser.project_id == project.id, m.ProjectUser.user_id == user.id, m.ProjectUser.status == "ACTIVE"))
    try:
        ensure_workspace(user, workspace)
        data = building_boq_xlsx(db, project, scoped_building, include_prices=can_view_prices(db, user, project.id), workspace=workspace)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    filename = f"AlphaNumeric_{_slug(project.name)}_Project-BOQ_{date.today().isoformat()}.xlsx"
    audit(db, user.id, "project_boq.generated", "project", project.id)
    db.commit()
    return StreamingResponse(BytesIO(data),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"',
                                      "X-Content-Type-Options": "nosniff"})


@router.get("/projects/{project_id}/buildings/{building_id}/rooms/{room_id}/sheet.pdf")
def room_sheet(
    project_id: str,
    building_id: str,
    room_id: str,
    download: bool = Query(False),
    workspace: str = Query("LIGHTING", pattern="^(LIGHTING|AUTOMATION)$"),
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    room = db.get(m.Room, room_id)
    if not room or room.floor.building_id != building_id or room.floor.building.project_id != project_id:
        raise HTTPException(404, "Room not found in this building")
    ensure_project_access(db, user, project_id)
    ensure_building_access(db, user, project_id, building_id)
    ensure_workspace(user, workspace)
    data = room_sheet_pdf(db, room, include_prices=can_view_prices(db, user, project_id), workspace=workspace)
    filename = f"AlphaNumeric_{_slug(room.floor.building.project.name)}_{_slug(room.name)}_Room-Sheet_{date.today().isoformat()}.pdf"
    audit(db, user.id, "room_sheet.generated", "room", room.id)
    db.commit()
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": _disposition(filename, download),
                             "X-Content-Type-Options": "nosniff"})


@router.get("/projects/{project_id}/buildings/{building_id}/floors/{floor_id}/sheet.pdf")
def floor_sheet(
    project_id: str,
    building_id: str,
    floor_id: str,
    download: bool = Query(False),
    workspace: str = Query("LIGHTING", pattern="^(LIGHTING|AUTOMATION)$"),
    db: Session = Depends(get_db),
    user: m.User = Depends(get_current_user),
):
    floor = db.get(m.Floor, floor_id)
    if not floor or floor.building_id != building_id or floor.building.project_id != project_id:
        raise HTTPException(404, "Floor not found in this building")
    ensure_project_access(db, user, project_id)
    ensure_building_access(db, user, project_id, building_id)
    ensure_workspace(user, workspace)
    data = floor_sheet_pdf(db, floor, include_prices=can_view_prices(db, user, project_id), workspace=workspace)
    filename = f"AlphaNumeric_{_slug(floor.building.project.name)}_{_slug(floor.name)}_Floor-Sheet_{date.today().isoformat()}.pdf"
    audit(db, user.id, "floor_sheet.generated", "floor", floor.id); db.commit()
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": _disposition(filename, download),
                             "X-Content-Type-Options": "nosniff"})
