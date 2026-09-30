> **Archived Release 4 evidence:** historical only. Current schema head and validation are documented in `PRODUCTION_RELEASE_5.0.0.md`.

# AlphaNumeric B2B — Final Release Audit

Date: 2026-09-18

## Final status

**NOT DEPLOY READY — VALIDATION PENDING**

This package is the latest complete patched source tree. It intentionally is not labelled Production Ready because mandatory production-stack gates could not be executed in the current environment.

## Source state preserved

The package preserves the completed fixes from the previous validation passes, including:

- production runtime demo seeding removed/isolated from production startup;
- secure first-admin bootstrap and `must_change_password` workflow;
- frontend forced Change Password route/workflow;
- production PostgreSQL enforcement and Render PostgreSQL URL normalization;
- production `COOKIE_SECURE` fail-closed validation;
- Content-Security-Policy and existing security headers;
- Decimal-based commercial calculations;
- inquiry submit status `IN_PROCESS`, automatic idempotent DRAFT quotation, and `QUOTED` only when quotation is sent;
- quotation revision/snapshot handling;
- exact-variant-first product media with true family-level fallback;
- variant-scoped primary/reorder media handling;
- three-image primary/order PDF regression coverage using meaningful PNG fixtures;
- redesigned Project Book with cover, customer/inquiry, partner, main boards, floor pages, room product lists, one selected thumbnail per row, aggregated BOQ and commercial history;
- Project Document upload/preview/download/archive workflow, including the restored Archive frontend control;
- production-safe Docker/Render source configuration and deterministic frontend Docker `npm ci` build;
- updated README and deployment guidance.

## Final source audit correction

A final source audit found one production-path defect: Alembic used the raw `DATABASE_URL` while application startup normalized Render-style `postgres://` / `postgresql://` URLs to the installed psycopg v3 driver. `backend/migrations/env.py` now applies the same `normalized_database_url()` function before Alembic opens a connection. This prevents migration startup from silently selecting an unavailable PostgreSQL driver when a provider emits a generic PostgreSQL URL.

## Executed checks

- Backend integration/security tests: **11/11 PASS**.
- Python compilation: **PASS**.
- Alembic structural migration smoke: **PASS**, revisions `0001 -> 0002 -> 0003 -> 0004 -> 0005` to head.
- Package/source presence audit: **PASS**.
- Clean ZIP extraction/import/backend-test/compile/structural-migration validation: **PASS**.
- Production dummy-data source scan: **PASS** for production runtime; remaining fixtures are test-only.
- Secret source scan: **PASS**; distributable configuration contains templates/placeholders, not real credentials.
- Package.json / package-lock are present and retained.

## Blocked / not executed production gates

- `npm ci`: **BLOCKED** — registry requests fail/time out with DNS/network errors (`EAI_AGAIN` / no registry response).
- Frontend unit tests: **NOT EXECUTED** because locked dependencies could not be installed.
- TypeScript/Vite production build: **NOT EXECUTED** for the same dependency blocker.
- Docker build/runtime: **BLOCKED** — Docker executable is not available in the current environment.
- Real PostgreSQL fresh/upgrade migration validation: **BLOCKED** — PostgreSQL client/server is not available and Docker is unavailable.
- Browser E2E and required viewport matrix: **NOT EXECUTED** because the complete frontend/runtime stack could not be started.
- Runtime every-button audit: **NOT EXECUTED** for the same reason.
- Production-stack inquiry 422 browser regression, IDOR, price authorization, restart persistence, PostgreSQL-backed Project Book, final production PDF page-by-page inspection and commercial reconciliation: **NOT EXECUTED**.

## Release decision

The complete latest updated source is packaged as:

`AlphaNumeric-B2B-Latest-Updated-Validation-Pending.zip`

It must not be promoted or renamed to `AlphaNumeric-B2B-Production-Ready-Final.zip` until all blocked/not-executed mandatory gates pass in a Docker + PostgreSQL + working npm-registry + browser-E2E environment.
