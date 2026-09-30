"""Idempotently register the bundled CA1-CA10 images against exact COB variants.

Run after seed_arcot_cob_ca1_ca10.sql, inside the app container with local media:
  python -m scripts.import_cob_variant_images --apply
The default invocation is read-only. Existing variant media is never replaced.
"""
import argparse
from hashlib import sha256
from pathlib import Path
from shutil import copyfile

from PIL import Image
from sqlalchemy import select

from app import models as m
from app.config import settings
from app.db import SessionLocal


def bundled_images_dir() -> Path:
    """Locate the assets in both the source checkout and the Compose image."""
    here = Path(__file__).resolve()
    for path in (here.parents[1] / "Images", here.parents[2] / "Images"):
        if (path / "CA1.webp").is_file():
            return path
    return here.parents[1] / "Images"


def import_images(db, images: Path, media_root: Path, apply: bool = False) -> list[dict]:
    results = []
    for number in range(1, 11):
        model = f"CA{number}"
        product = db.scalar(select(m.Product).where(m.Product.sku == f"ARCOT-COB-{model}"))
        source = images / f"{model}.webp"
        if not product or product.workspace != "LIGHTING" or product.model_number != model or not source.is_file():
            results.append({"model": model, "status": "missing exact product or image"})
            continue
        existing = db.scalars(select(m.ProductMedia).where(
            m.ProductMedia.product_id == product.id, m.ProductMedia.archived_at.is_(None))).all()
        if existing:
            results.append({"model": model, "status": "existing variant media retained"})
            continue
        with Image.open(source) as image:
            image.verify()
        with Image.open(source) as image:
            width, height = image.size
        key = f"products/{product.id}/{model.lower()}.webp"
        target = media_root / key
        if apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            copyfile(source, target)
            db.add(m.ProductMedia(product_id=product.id, product_family_id=product.family_id,
                                  workspace=product.workspace, storage_provider="local", storage_key=key,
                                  original_filename=source.name, stored_filename=source.name,
                                  mime_type="image/webp", media_type="image/webp", file_size=source.stat().st_size,
                                  checksum_sha256=sha256(source.read_bytes()).hexdigest(),
                                  width=width, height=height, sort_order=0, is_primary=True,
                                  alt_text=f"Arcot COB {model} product", upload_status="READY"))
        results.append({"model": model, "status": "registered" if apply else "ready to register"})
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Copy and register missing exact variant images")
    parser.add_argument("--images", type=Path, default=bundled_images_dir())
    args = parser.parse_args()
    if settings.media_storage_provider != "local":
        parser.error("This importer supports local media only; upload through the authenticated API for other providers")
    with SessionLocal() as session:
        for result in import_images(session, args.images, Path(settings.media_root).resolve(), args.apply):
            print(f"{result['model']}: {result['status']}")
        if args.apply:
            session.commit()
