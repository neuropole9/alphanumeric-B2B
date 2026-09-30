from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from .config import settings
from .db import SessionLocal, engine, Base, is_postgresql_url
from .api import router
from .catalog_api import router as catalog_router
from .workspace_api import router as workspace_router
from .reports_api import router as reports_router
from .release_api import router as release_router
from .operations_api import router as operations_router
from .release4_api import router as release4_router
from .release5_api import router as release5_router
from .release503_api import router as release503_router
from .arcot_import import router as arcot_import_router
from .bootstrap import bootstrap_admin

@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.environment == "production":
        if not is_postgresql_url(settings.database_url):
            raise RuntimeError("Production DATABASE_URL must use PostgreSQL with psycopg")
        if settings.secret_key == "CHANGE_ME_IN_PRODUCTION" or len(settings.secret_key) < 32:
            raise RuntimeError("Production SECRET_KEY must be a strong value of at least 32 characters")
        if not settings.cookie_secure:
            raise RuntimeError("Production COOKIE_SECURE must be true")
        required = {
            "COMPANY_NAME": settings.company_name,
            "COMPANY_GSTIN": settings.company_gstin,
            "COMPANY_PAN": settings.company_pan,
            "COMPANY_ADDRESS": settings.company_address,
            "COMPANY_PHONE": settings.company_phone,
            "COMPANY_EMAIL": settings.company_email,
            "BANK_NAME": settings.bank_name,
            "BANK_ACCOUNT_NAME": settings.bank_account_name,
            "BANK_ACCOUNT_NUMBER": settings.bank_account_number,
            "BANK_IFSC": settings.bank_ifsc,
        }
        missing = [name for name, value in required.items() if not value.strip()]
        if missing:
            raise RuntimeError(f"Production company configuration is incomplete: {', '.join(missing)}")
        if settings.media_storage_provider.lower() != "google_drive":
            raise RuntimeError("Production MEDIA_STORAGE_PROVIDER must be google_drive")
        drive_values = {
            "GOOGLE_DRIVE_CLIENT_ID": settings.google_drive_client_id,
            "GOOGLE_DRIVE_CLIENT_SECRET": settings.google_drive_client_secret,
            "GOOGLE_DRIVE_REFRESH_TOKEN": settings.google_drive_refresh_token,
            "GOOGLE_DRIVE_ROOT_FOLDER_ID": settings.google_drive_root_folder_id,
        }
        missing_drive = [name for name, value in drive_values.items() if not value]
        if missing_drive:
            raise RuntimeError(f"Production Google Drive configuration is incomplete: {', '.join(missing_drive)}")
    # Production uses Alembic before startup. SQLite development can self-initialize.
    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        bootstrap_admin(db)
    yield

app=FastAPI(title=settings.app_name,version="5.0.11",lifespan=lifespan,docs_url="/api/docs",openapi_url="/api/openapi.json")
if settings.environment != "production":
    app.add_middleware(CORSMiddleware,allow_origins=settings.origins,allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
app.include_router(router)
app.include_router(catalog_router)
app.include_router(workspace_router)
app.include_router(reports_router)
app.include_router(release_router)
app.include_router(operations_router)
app.include_router(release4_router)
app.include_router(release5_router)
app.include_router(release503_router)
app.include_router(arcot_import_router)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Content-Security-Policy", "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), geolocation=(), microphone=()")
    if settings.environment == "production":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response

@app.get("/health")
def health():
    with engine.connect() as c: c.execute(text("SELECT 1"))
    return {"status":"ok"}

@app.get("/health/live", include_in_schema=False)
def liveness():
    return {"status": "alive"}

@app.get("/health/ready", include_in_schema=False)
def readiness():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ready", "database": "ok"}


static_dir = Path(__file__).resolve().parent.parent / "static"
if static_dir.exists():
    assets_dir = static_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        candidate = (static_dir / full_path).resolve()
        if full_path and static_dir.resolve() in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(static_dir / "index.html")
