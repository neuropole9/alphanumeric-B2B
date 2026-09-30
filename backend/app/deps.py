from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session
import jwt
from .db import get_db
from .models import User
from .security import decode_access_token

ROLE_PERMISSIONS = {
    "SUPER_ADMIN": {"*"},
    "ADMIN": {"*"},
    "SALES_MANAGER": {"partners.view", "partners.manage", "pipeline.view", "pipeline.manage", "commercial.view", "commercial.manage", "reports.view"},
    "SALES_EXECUTIVE": {"partners.view", "pipeline.view", "pipeline.manage", "commercial.view"},
    "DESIGNER": {"pipeline.view", "design.manage", "boq.manage"},
    "ENGINEER": {"pipeline.view", "design.manage", "boq.manage"},
    "ACCOUNTS": {"commercial.view", "payments.manage", "reports.view"},
    "WAREHOUSE": {"inventory.view", "inventory.receive", "inventory.transfer", "dispatch.manage"},
    "DISPATCH": {"inventory.view", "dispatch.manage"},
    "SERVICE": {"rma.view", "rma.manage", "tickets.manage"},
    "RMA": {"rma.view", "rma.manage", "tickets.manage"},
    "PARTNER_ADMIN": {"partner.self", "pipeline.view", "commercial.view", "inventory.view", "rma.view", "rma.create"},
    "PARTNER_USER": {"partner.self", "commercial.view", "rma.view", "rma.create"},
    "USER": set(),
}

def get_current_user(access_token: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> User:
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        user_id = decode_access_token(access_token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    user = db.get(User, user_id)
    if not user or user.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User unavailable")
    return user


def require_csrf(request: Request, x_csrf_token: str | None = Header(default=None)):
    cookie = request.cookies.get("csrf_token")
    if not cookie or not x_csrf_token or cookie != x_csrf_token:
        raise HTTPException(status_code=403, detail="CSRF validation failed")


def has_permission(user: User, permission: str) -> bool:
    grants = set(user.permissions or []) | ROLE_PERMISSIONS.get(user.role.upper(), set())
    return "*" in grants or permission in grants


def require_permission(permission: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if not has_permission(user, permission):
            raise HTTPException(status_code=403, detail="Permission denied")
        return user
    return dependency


def ensure_workspace(user: User, workspace: str):
    workspace = workspace.upper()
    if workspace not in {"LIGHTING", "AUTOMATION"}:
        raise HTTPException(status_code=422, detail="Application must be LIGHTING or AUTOMATION")
    if user.role not in {"ADMIN", "SUPER_ADMIN"} and workspace not in [str(x).upper() for x in (user.workspaces or [])]:
        raise HTTPException(status_code=403, detail="Workspace not permitted")
