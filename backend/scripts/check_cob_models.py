"""Read-only check of CA1–CA10 in the configured database and media store.

Run inside the deployed app container: python -m scripts.check_cob_models
This command prints product/image status only; it never creates catalogue data.
"""
from pathlib import Path

from sqlalchemy import select

from app import models as m
from app.config import settings
from app.db import SessionLocal


def check_models(db, media_root: Path) -> list[dict[str, str]]:
    result = []
    for number in range(1, 11):
        model = f"CA{number}"
        product = db.scalar(select(m.Product).where(m.Product.sku == f"ARCOT-COB-{model}"))
        if not product or product.workspace != "LIGHTING" or product.model_number != model:
            result.append({"model": model, "product": "missing exact LIGHTING variant", "image": "missing"})
            continue
        media = db.scalars(select(m.ProductMedia).where(
            m.ProductMedia.product_id == product.id,
            m.ProductMedia.archived_at.is_(None),
            m.ProductMedia.upload_status == "READY",
        ).order_by(m.ProductMedia.is_primary.desc(), m.ProductMedia.sort_order)).all()
        primary = media[0] if media else None
        if primary is None:
            image = "missing exact variant media"
        elif primary.storage_provider == "local":
            image = "ready" if (media_root / primary.storage_key).is_file() else "media file missing"
        else:
            image = "registered; verify authenticated provider access"
        result.append({"model": model, "product": product.status, "image": image})
    return result


if __name__ == "__main__":
    with SessionLocal() as session:
        for row in check_models(session, Path(settings.media_root).resolve()):
            print(f"{row['model']}: {row['product']} | {row['image']}")
