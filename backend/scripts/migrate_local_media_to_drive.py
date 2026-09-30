"""Idempotently copy legacy local product media to private Google Drive storage."""
from pathlib import Path
from sqlalchemy import select
from app.config import settings
from app.db import SessionLocal
from app import models as m
from app.media_storage import GoogleDriveMediaStorageProvider, safe_component

def main() -> int:
    provider = GoogleDriveMediaStorageProvider(); root = Path(settings.media_root).resolve(); migrated = 0
    with SessionLocal() as db:
        rows = db.scalars(select(m.ProductMedia).where(m.ProductMedia.provider_file_id.is_(None), m.ProductMedia.archived_at.is_(None))).all()
        for row in rows:
            product = row.product
            if not product: continue
            path = (root / row.storage_key).resolve()
            if root not in path.parents or not path.is_file(): continue
            stored = provider.upload(path.read_bytes(), filename=path.name, workspace=product.workspace,
                product_folder=f"{safe_component(product.name)}_{product.id}", mime_type=row.mime_type or row.media_type)
            row.storage_provider="google_drive"; row.provider_file_id=stored.file_id; row.provider_parent_id=stored.parent_id
            row.file_size=stored.size; row.checksum_sha256=stored.checksum; row.workspace=product.workspace; migrated += 1
            db.commit()
    print(f"migrated={migrated}"); return 0

if __name__ == "__main__": raise SystemExit(main())
