"""Report missing provider objects without mutating commercial data."""
from sqlalchemy import select
from app.db import SessionLocal
from app import models as m
from app.media_storage import get_media_provider

def main() -> int:
    missing = []
    with SessionLocal() as db:
        rows = db.scalars(select(m.ProductMedia).where(m.ProductMedia.archived_at.is_(None))).all()
        for row in rows:
            provider = get_media_provider(row.storage_provider)
            if not provider.exists(row.provider_file_id or row.storage_key, row.storage_key):
                missing.append({"id": row.id, "product_id": row.product_id, "storage_key": row.storage_key})
    for item in missing: print(item)
    print(f"checked={len(rows)} missing={len(missing)}")
    return 1 if missing else 0

if __name__ == "__main__": raise SystemExit(main())
