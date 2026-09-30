"""Authorized, allowlisted external catalogue discovery and import.

The importer never hotlinks assets and never invents prices. Network access is
isolated behind ``fetch_html`` so discovery can be verified with deterministic
approved-domain responses in tests.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import csv
from io import StringIO
import ipaddress
import re
import socket
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models as m
from .config import settings
from .db import get_db
from .deps import ensure_workspace, get_current_user, require_csrf, require_permission
from .services import audit

router = APIRouter(prefix="/api/v1/catalogue/arcot", tags=["authorized Arcot catalogue import"])
ADMIN_ROLES = {"ADMIN", "SUPER_ADMIN"}


def allowed_domains() -> set[str]:
    return {value.strip().lower().rstrip(".") for value in settings.external_import_allowed_domains.split(",") if value.strip()}


def validate_source_url(url: str, resolve_dns: bool = False) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not host or host not in allowed_domains() or parsed.username or parsed.password:
        raise HTTPException(422, "Import URL must use HTTPS on an approved source domain")
    if parsed.port not in {None, 443}:
        raise HTTPException(422, "Non-standard source ports are not allowed")
    if resolve_dns:
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
        except OSError as exc:
            raise HTTPException(502, "Approved source domain could not be resolved") from exc
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                raise HTTPException(422, "Approved source resolved to a non-public address")
    return url


def fetch_html(url: str) -> str:
    current = validate_source_url(url, resolve_dns=True)
    headers = {"User-Agent": "AlphaNumeric-authorized-catalogue-import/5.0.10", "Accept": "text/html"}
    with httpx.Client(timeout=12, follow_redirects=False, headers=headers) as client:
        for _ in range(4):
            response = client.get(current)
            if response.status_code in {301, 302, 303, 307, 308}:
                target = response.headers.get("location")
                if not target: raise HTTPException(502, "Source redirect omitted a destination")
                current = validate_source_url(urljoin(current, target), resolve_dns=True)
                continue
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if "text/html" not in content_type: raise HTTPException(422, "Source response is not HTML")
            if len(response.content) > 5 * 1024 * 1024: raise HTTPException(413, "Source page exceeds the import limit")
            return response.text
    raise HTTPException(422, "Source redirected too many times")


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.links: list[str] = []; self.images: list[str] = []; self.documents: list[str] = []
        self.title = ""; self.h1 = ""; self.description = ""; self.text: list[str] = []; self._tag = ""; self.specs: dict[str, str] = {}
        self._cells: list[str] = []; self._cell = ""

    def handle_starttag(self, tag, attrs):
        values = dict(attrs); self._tag = tag
        if tag == "a" and values.get("href"): self.links.append(values["href"])
        if tag == "img" and values.get("src"): self.images.append(values["src"])
        if tag == "meta" and values.get("name", "").lower() == "description": self.description = values.get("content", "").strip()
        if tag in {"td", "th"}: self._cell = ""

    def handle_data(self, data):
        value = " ".join(data.split())
        if not value: return
        self.text.append(value)
        if self._tag == "title": self.title += (" " if self.title else "") + value
        if self._tag == "h1": self.h1 += (" " if self.h1 else "") + value
        if self._tag in {"td", "th"}: self._cell += (" " if self._cell else "") + value

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self._cell: self._cells.append(self._cell.strip())
        if tag == "tr" and len(self._cells) >= 2:
            self.specs[self._cells[0][:120]] = self._cells[1][:500]; self._cells = []
        self._tag = ""


def parse_page(url: str, html: str) -> dict:
    parser = PageParser(); parser.feed(html)
    name = (parser.h1 or parser.title or urlparse(url).path.rsplit("/", 1)[-1].replace("-", " ")).strip()
    model_match = re.search(r"(?:model|code|sku)\s*[:#-]?\s*([A-Z0-9][A-Z0-9._/-]{1,30})", " ".join(parser.text), re.I)
    model = model_match.group(1).upper() if model_match else None
    return {"source_url": url, "name": name[:180], "model": model, "description": parser.description[:2000] or None,
            "highlights": parser.text[:8], "specifications": parser.specs,
            "images": [urljoin(url, item) for item in parser.images],
            "documents": [urljoin(url, item) for item in parser.links if item.lower().split("?")[0].endswith(".pdf")],
            "related_urls": [urljoin(url, item) for item in parser.links]}


def discover_products(start_url: str, fetcher=fetch_html) -> list[dict]:
    start_url = validate_source_url(start_url)
    index = parse_page(start_url, fetcher(start_url))
    candidates = []
    for target in index["related_urls"]:
        try: validate_source_url(target)
        except HTTPException: continue
        path = urlparse(target).path.lower().rstrip("/")
        if target != start_url and ("product" in path or "/cob" in path): candidates.append(target)
    candidates = list(dict.fromkeys(candidates))[:100]
    products = []
    for target in candidates:
        try: products.append(parse_page(target, fetcher(target)))
        except (HTTPException, httpx.HTTPError): continue
    return products or [index]


class ArcotImportIn(BaseModel):
    source_url: str = "https://arcotindia.com/cobs-product"
    rights_confirmed: bool
    dry_run: bool = True
    category_id: str | None = None
    selected_urls: list[str] = Field(default_factory=list, max_length=100)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:170] or "imported-product"


@router.post("/imports", dependencies=[Depends(require_csrf)])
def run_arcot_import(body: ArcotImportIn, db: Session = Depends(get_db), user: m.User = Depends(require_permission("products.create"))):
    if user.role not in ADMIN_ROLES: raise HTTPException(403, "Administrator access required")
    ensure_workspace(user, "LIGHTING")
    if not body.rights_confirmed: raise HTTPException(422, "Confirm content and asset reuse rights before discovery")
    source = validate_source_url(body.source_url)
    category = db.get(m.Category, body.category_id) if body.category_id else None
    if not body.dry_run and (not category or category.workspace != "LIGHTING" or category.status == "ARCHIVED"):
        raise HTTPException(422, "Choose an active Lighting category before committing an import")
    products = discover_products(source)
    if body.selected_urls:
        selected = {validate_source_url(url) for url in body.selected_urls}; products = [item for item in products if item["source_url"] in selected]
    report_rows = []; imported = skipped = 0
    job = m.ExternalCatalogueImport(workspace="LIGHTING", source_domain=urlparse(source).hostname or "arcotindia.com",
        source_url=source, rights_confirmed=True, dry_run=body.dry_run, status="DISCOVERED",
        discovered_count=len(products), report={}, created_by=user.id)
    db.add(job); db.flush()
    for item in products:
        canonical = validate_source_url(item["source_url"]); fingerprint = sha256(repr(sorted(item.items())).encode()).hexdigest()
        existing = db.scalar(select(m.ExternalProductSource).where(
            m.ExternalProductSource.workspace == "LIGHTING", m.ExternalProductSource.source_url == canonical))
        action = "UNCHANGED" if existing and existing.fingerprint == fingerprint else ("UPDATE_REVIEW" if existing else "CREATE_DRAFT")
        if body.dry_run:
            report_rows.append({**item, "action": action, "price_status": "PRICE_REQUIRED"}); continue
        if existing:
            existing.fingerprint = fingerprint; existing.source_snapshot = item; existing.last_import_id = job.id; skipped += 1
            report_rows.append({**item, "action": action, "product_id": existing.product_id, "price_status": "PRICE_REQUIRED"}); continue
        model = item.get("model") or sha256(canonical.encode()).hexdigest()[:10].upper()
        family = db.scalar(select(m.ProductFamily).where(m.ProductFamily.workspace == "LIGHTING", func.lower(m.ProductFamily.name) == item["name"].lower()))
        if not family:
            base = _slug(item["name"]); slug = base; suffix = 2
            while db.scalar(select(m.ProductFamily.id).where(m.ProductFamily.workspace == "LIGHTING", m.ProductFamily.slug == slug)):
                slug = f"{base[:160]}-{suffix}"; suffix += 1
            family = m.ProductFamily(workspace="LIGHTING", category_id=category.id, name=item["name"], slug=slug,
                brand="Arcot", short_description=item.get("description"), full_description=item.get("description"),
                features=item.get("highlights") or [], applications=[], status="DRAFT")
            db.add(family); db.flush()
        sku = f"ARCOT-{re.sub(r'[^A-Z0-9]+', '-', model).strip('-')[:60]}"
        if db.scalar(select(m.Product.id).where(func.lower(m.Product.sku) == sku.lower())): sku = f"{sku[:68]}-{fingerprint[:8]}"
        product = m.Product(workspace="LIGHTING", category_id=category.id, family_id=family.id, sku=sku,
            name=item["name"], variant_name=model, model_number=item.get("model"), brand="Arcot", manufacturer="Arcot",
            description=item.get("description"), full_description=item.get("description"), highlights=item.get("highlights") or [],
            specs=item.get("specifications") or {}, images=[], price=0, pricing_status="PRICE_REQUIRED", status="DRAFT")
        db.add(product); db.flush()
        mapping = m.ExternalProductSource(workspace="LIGHTING", source_domain=urlparse(canonical).hostname or "arcotindia.com",
            source_url=canonical, source_model=item.get("model"), fingerprint=fingerprint, product_id=product.id,
            last_import_id=job.id, source_snapshot=item)
        db.add(mapping); imported += 1
        report_rows.append({**item, "action": "CREATED_DRAFT", "product_id": product.id, "price_status": "PRICE_REQUIRED"})
    job.imported_count, job.skipped_count = imported, skipped
    job.status = "DRY_RUN_COMPLETE" if body.dry_run else "COMPLETED"; job.report = {"rows": report_rows}; job.completed_at = datetime.now(timezone.utc)
    audit(db, user.id, "catalogue.arcot_import", "external_catalogue_import", job.id,
          {"dry_run": body.dry_run, "discovered": len(products), "imported": imported, "skipped": skipped})
    db.commit()
    return {"id": job.id, "status": job.status, "discovered": len(products), "imported": imported,
            "skipped": skipped, "rows": report_rows, "pricing_policy": "PRICE_REQUIRED", "assets_hotlinked": False}


@router.get("/imports/{job_id}/report.csv")
def arcot_report(job_id: str, db: Session = Depends(get_db), user: m.User = Depends(get_current_user)):
    if user.role not in ADMIN_ROLES: raise HTTPException(403, "Administrator access required")
    row = db.get(m.ExternalCatalogueImport, job_id)
    if not row: raise HTTPException(404, "External import not found")
    ensure_workspace(user, row.workspace); output = StringIO(); writer = csv.writer(output)
    writer.writerow(["Source URL", "Model", "Name", "Action", "Price status", "Product ID"])
    for item in (row.report or {}).get("rows", []):
        safe = lambda value: f"'{value}" if str(value).startswith(("=", "+", "-", "@")) else value
        writer.writerow([safe(item.get("source_url", "")), safe(item.get("model", "")), safe(item.get("name", "")),
                         item.get("action", ""), item.get("price_status", ""), item.get("product_id", "")])
    return PlainTextResponse(output.getvalue(), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="arcot-import-{job_id}.csv"'})
