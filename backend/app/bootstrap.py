from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models as m
from .config import settings
from .db import SessionLocal
from .security import hash_password


def bootstrap_admin(db: Session) -> bool:
    """Create the first administrator only when the database has no users.

    This is intentionally not a data seeder: it never creates catalogue, customer,
    project, report, media, or commercial records. Credentials must be supplied via
    BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD.
    """
    if db.scalar(select(func.count()).select_from(m.User)):
        return False
    if not settings.bootstrap_admin_email and not settings.bootstrap_admin_password:
        return False
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        raise RuntimeError("Set both BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD")
    if len(settings.bootstrap_admin_password) < 12:
        raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD must contain at least 12 characters")
    db.add(m.User(
        name=settings.bootstrap_admin_name.strip() or "System Administrator",
        email=settings.bootstrap_admin_email.strip().lower(),
        password_hash=hash_password(settings.bootstrap_admin_password),
        role="ADMIN",
        status="ACTIVE",
        workspaces=["LIGHTING", "AUTOMATION"],
        permissions=["*"],
        must_change_password=True,
    ))
    db.commit()
    return True


if __name__ == "__main__":
    with SessionLocal() as db:
        created = bootstrap_admin(db)
    print("First administrator created." if created else "No bootstrap action was required.")
