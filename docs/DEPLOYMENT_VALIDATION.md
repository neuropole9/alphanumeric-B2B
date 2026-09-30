> **Archived Release 4 evidence:** historical only. Current schema head and validation are documented in `PRODUCTION_RELEASE_5.0.0.md`.

# Deployment Validation — 2026-09-18

## Status

**VALIDATION PENDING — NOT DEPLOY READY**

## Static production configuration audit

**PASS**

- Docker Compose uses PostgreSQL and does not enable demo seeding.
- Docker Compose declares persistent PostgreSQL and media volumes.
- Root Dockerfile builds the frontend with `npm ci` and `package-lock.json`.
- Render runs in production mode, uses the managed database connection, enables secure cookies and mounts persistent media storage.
- Application production startup rejects non-PostgreSQL database URLs.
- Alembic now normalizes provider-style PostgreSQL URLs to `postgresql+psycopg://`, matching the installed psycopg v3 driver.
- Production requires a non-default strong secret plus configured company/bank identity values.

## Runtime production validation

**BLOCKED**

Current execution environment:

- Node: available (`v22.16.0`).
- npm: available (`10.9.2`), but registry access is unavailable/timeouts.
- Docker: unavailable (`docker: command not found`).
- PostgreSQL client/server: unavailable (`psql: command not found`), and Docker cannot provide PostgreSQL.

Therefore clean Docker startup, real PostgreSQL migrations, media/database persistence, full business E2E and Render-equivalent runtime validation are not claimed as PASS.

## Clean archive validation

**PASS**

The validation-pending ZIP was integrity-tested, extracted into a separate clean directory, and validated there. Backend import sanity passed, the backend test suite passed 11/11, Python compilation passed, and the structural Alembic migration reached `0005` head. The archive does not depend on generated caches, runtime databases, node_modules or files outside the ZIP for these checks.

## Required promotion run

In a suitable environment, execute at minimum:

1. `npm ci`, frontend tests, TypeScript validation and production build.
2. Create and verify a PostgreSQL backup, record the current Alembic revision and critical row counts, and inspect the existing named volumes.
3. Stop services without deleting volumes: `docker compose stop`.
4. `docker compose build --no-cache`, then `docker compose up -d` with production-safe `.env` values.
5. Fresh PostgreSQL migration to head and supported upgrade-path test.
6. Secure bootstrap admin → forced password change.
7. Full customer/project/building/floor/room/main-board/product/media/inquiry/BOQ/quotation/order/invoice/document workflow.
8. Project-scoped authorization/IDOR and price-redaction tests.
9. Browser E2E at 1920×1080, 1536×864, 1440×900 and 1366×768.
10. Normal restart persistence validation; never remove the named database or media volumes when records must be preserved.
11. Generate the PostgreSQL-backed Project Book, render every page at about 180 DPI, visually inspect, and reconcile commercial values.

Only after all mandatory gates pass may this package be promoted to `AlphaNumeric-B2B-Production-Ready-Final.zip`.
