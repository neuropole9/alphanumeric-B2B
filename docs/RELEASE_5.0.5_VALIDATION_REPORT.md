# AlphaNumeric B2B Production Release 5.0.5 validation report

## Decision

Release 5.0.5 is an application-level release candidate. All checks executable in Work Mode passed. It is **not unconditionally production-ready** because protected Windows PostgreSQL-volume backup/restore, Docker Compose, real Google Drive OAuth, real SMTP delivery, and real Chrome every-button/viewport testing require the user's staging environment and credentials and remain `BLOCKED`.

## Confirmed defects and root causes

| Area | Confirmed defect | Root cause | Resolution |
|---|---|---|---|
| Project Book room products | Quantity/unit/tax/price fields wrapped into unreadable narrow columns | One dense 11-column A4 table included row-level tax | Replaced with stable product cards and removed row-level tax |
| Decimal display | Quantities such as `12.00` were displayed with meaningless precision | PDF code formatted stored `Numeric(14,2)` values directly | Added shared Decimal-safe compact formatting |
| Currency display | Commercial values used western grouping and narrow invoice cells split amounts | Generic Python comma formatting and breakable spaces | Added Indian grouping and non-breaking currency cells |
| Project Book totals | Room total included tax and final BOQ repeated tax per row | Tax was calculated and displayed at product-row level | Added room subtotal before tax and final-only financial summary |
| Technical specifications | Short products occupied separate A4 pages | Generous per-cell padding made two compact blocks exceed a page | Added compact ordered spec blocks; two short products now share a page |
| Invoice detail | Invoice omitted product family/model, discount, taxable value, line tax, place of supply, payment status, amount in words and project shipping context | Legacy seven-column invoice renderer exposed only a subset of persisted snapshot data | Rebuilt the dedicated invoice renderer around the existing server snapshot |
| GST jurisdiction | New invoices always stored CGST and SGST | Invoice creation did not evaluate customer/company state | Added mutually exclusive server-side CGST/SGST or IGST snapshot logic |
| Invoice wrapping | HSN/SAC and currency values could split across lines | Insufficient numeric column widths | Rebalanced columns and used smaller right-aligned numeric styling |

No schema change was necessary. Existing invoice snapshots remain unchanged; the jurisdiction fix applies when a new invoice snapshot is created.

## Project Book QA

- Sanitized data: 2 buildings, 5 floors, 16 rooms, 19 configured product placements, 4 unique products.
- Quantity reconciliation: `119` expected and rendered, including `6.5` and `0.25` fractional quantities.
- Project Book: 29 A4 pages. Building Book: 23 pages. Floor Sheet: 1 page. Room Sheet: 3 pages.
- Two sanitized 1200×900 product images were used. Exact variant media remained authoritative; family-level media was only a fallback.
- Primary-image switching changed the regenerated Project Book bytes and the selected storage key.
- Missing-image product rendered `Image unavailable` without aborting generation.
- Aspect ratio used proportional ReportLab images; rendered pages showed no stretching.
- Room cards show family, exact variant/model, SKU, ordered specs, quantity, unit, rate and pre-tax line total.
- Room tax columns were absent; every priced room ended with `Room Subtotal Before Tax`.
- Aggregated BOQ included all four products, long SKU coverage, rates and pre-tax totals; financial summary followed the final row.
- Technical specifications preserved order, omitted empty values/raw JSON, and rendered two compact products per page where content fit.
- Text extraction confirmed no `12.00 Nos`, correct missing-image fallback, long-SKU presence, final-only GST and no simultaneous CGST/SGST/IGST.
- All 29 final Project Book pages were rendered to PNG and visually inspected: no clipping, overlap, distorted images, broken headers or unexpected blank pages.

## Invoice QA and calculation reconciliation

- Dedicated Tax Invoice: 1 A4 page; not a renamed quotation.
- Contains invoice/order dates and numbers, due date, payment terms, Bill To, Ship To/project, place of supply, GSTIN, family/model/SKU, HSN/SAC, quantity, unit, rate, discount, taxable value, tax rate/amount, line total, amount in words, payment status, bank details, terms, signature and page number.
- Preview and download returned identical extracted content from the same backend generator; only `Content-Disposition` differed.
- Sample calculation: subtotal `INR 37,585.00`; discount 7.5% `INR 2,818.88`; taxable value `INR 34,766.12`; CGST `INR 3,128.95`; SGST `INR 3,128.95`; grand total `INR 41,024.02`.
- Line totals `8,868.43 + 27,833.25 + 4,322.34 = 41,024.02`.
- Automated tests cover intra-state CGST/SGST and inter-state IGST exclusivity.
- The final page was rendered at 140 DPI and visually inspected: no clipping, overlap, broken rows, stretched logo, unreadable numeric wrapping or unexpected blank page.
- Multipage invoice behavior is backed by `repeatRows=1` and row-level splitting; the full backend regression suite exercises PDF generation. A real high-volume finalized staging invoice remains part of browser staging validation.

## Exact validation results

| Validation | Result |
|---|---|
| Python compileall | PASS |
| Backend pytest | PASS — 35 passed, 0 failed, 4 non-fatal dependency/serializer warnings |
| Frontend npm ci | PASS — 145 packages installed from lock file |
| Frontend tests | PASS — 5 files, 54 tests |
| TypeScript/Vite production build | PASS — 2,282 modules transformed |
| npm production audit | PASS — 0 vulnerabilities |
| Python dependency consistency | PASS — no broken requirements |
| OpenAPI generation | PASS — version 5.0.5, 158 paths, 201 operations |
| Fresh migration | PASS — 0001 through 0011 on a temporary SQLite database |
| Previous-head upgrade | PASS — 0010 to 0011 on a separate temporary SQLite database |
| Alembic head | PASS — `0011 (head)` |
| PDF signature/text extraction/render | PASS |
| Clean extracted-ZIP tests/build | Recorded after final archive creation in the delivery report |

The SQLite migration checks are regression checks only and are not represented as PostgreSQL validation.

## External validation status

| Check | Status | Reason |
|---|---|---|
| Protected Windows PostgreSQL backup/restore and record preservation | BLOCKED | Work Mode cannot access the user's Windows Docker volume or database |
| PostgreSQL backend suite | BLOCKED | `psql` and a target PostgreSQL server are unavailable here |
| Docker/Compose build, health and persistence | BLOCKED | Docker CLI/daemon are unavailable here |
| Real Google Drive OAuth upload/download | BLOCKED | No dedicated OAuth credentials supplied; local media remains enabled |
| Real SMTP delivery | BLOCKED | No SMTP credentials or receiving mailbox supplied |
| Real Chrome responsive/every-button test | BLOCKED | No Chrome/Chromium connected to the local staging stack |

## Changed files

- `backend/app/pdf_format.py`
- `backend/app/reports.py`
- `backend/app/pdf.py`
- `backend/app/services.py`
- `backend/app/main.py`
- `backend/app/arcot_import.py`
- `backend/scripts/generate_release_validation.py`
- `backend/tests/conftest.py`
- `backend/tests/test_pdf_documents.py`
- `frontend/package.json`
- `frontend/package-lock.json`
- `.env.example`
- `backend/.env.example`
- `docker-compose.yml`
- `README.md`
- `docs/DEPLOYMENT_VALIDATION.md`
- `docs/PRODUCTION_RELEASE_5.0.0.md`
- `CHANGELOG.md`
- `docs/RELEASE_5.0.5_VALIDATION_REPORT.md`
- regenerated sanitized PDF/QA files under `validation_artifacts/`

## Deployment and rollback

Before deployment on Windows, create and verify a PostgreSQL backup and record `alembic current` plus critical table counts. Do not drop the database, reset Alembic history, or remove Docker volumes. Deploy the source, keep `MEDIA_STORAGE_PROVIDER=local`, run `docker compose config`, build, start normally, verify database/app health, run `alembic upgrade head`, and execute the blocked staging checks.

Rollback is application-first: stop the 5.0.5 app without deleting volumes, restore the prior application image/source, and retain the database because 5.0.5 adds no migration. Restore the verified database backup only if staging verification finds database corruption; restore it into a separate database first and compare counts before any production cutover.
