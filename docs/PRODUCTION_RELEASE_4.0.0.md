> **Archived Release 4 evidence:** historical only. Current schema head and validation are documented in `PRODUCTION_RELEASE_5.0.0.md`.

# AlphaNumeric B2B 4.0.0 Release Validation

Build date: 2026-09-18

## Delivered workflows

- Partner onboarding/status, warehouse creation, idempotent stock receipt/issue and low-stock visibility.
- Order dispatch with partial-quantity controls, physical warehouse deductions, delivery lifecycle and tracking fields.
- Serial/warranty registry and extended RMA lifecycle with inspection, diagnosis, warranty decision, evidence, SLA, parts/labour, stock movements and PDF service report.
- Proforma invoices and invoice-linked credit/debit notes with server-calculated totals, issue/cancel controls, PDF generation and adjusted payment balance.
- Deterministic pricing rules. Precedence is `priority DESC`, then scope specificity, oldest creation time and stable ID. The explain endpoint exposes the winner and all considered rules.
- Discount approval request/decision flow and quotation-send enforcement when a configured approval threshold is exceeded.
- Sales targets for revenue/orders/inquiries with database-derived actuals, achievement, drill-down and CSV export.
- CSV/XLSX product imports with downloadable template, validation-only runs, atomic or partial writes, 5,000-row/size limits, duplicate and type checks, persisted history and formula-safe error CSV.
- In-app preferences and optional console/file/SMTP email delivery with idempotency, status, safe error logging and retry.
- Responsive Operations Centre and Commercial Control frontend workflows.

## Validation results

| Gate | Result | Evidence |
|---|---:|---|
| Python compilation | PASS | `python -m compileall -q app migrations` |
| Backend integration/security | PASS | 16 tests passed |
| Frontend unit tests | PASS | 16 tests passed across 3 files |
| TypeScript/Vite production build | PASS | 2,280 modules transformed; production assets emitted |
| Fresh Alembic migration | PASS | SQLite upgrade from base through `0007 (head)` |
| OpenAPI generation | PASS | Version 4.0.0; 138 paths / 178 operations |
| Python dependency consistency | PASS | `pip check`: no broken requirements |
| Production npm dependency audit | PASS | Offline lockfile audit: 0 vulnerabilities |
| PostgreSQL migration/runtime | NOT EXECUTABLE HERE | `psql` and a PostgreSQL server are not installed in the build environment |
| Docker image/Compose | NOT EXECUTABLE HERE | Docker is not installed in the build environment |
| Browser E2E/viewports | NOT EXECUTABLE HERE | No browser runtime is installed in the build environment |

The three environment-dependent gates must be run before traffic is switched to the new deployment. They are not represented as passes.

## Required deployment validation

```bash
cp .env.example .env
# Fill every required production/company/database value.
docker compose config
docker compose build --no-cache
docker compose up -d
docker compose exec app alembic current
curl --fail http://localhost:8080/health/ready
```

Expected migration head: `0007`.

Then execute company UAT at laptop, tablet and mobile widths for login, inquiry-to-invoice, financial documents, pricing approval, catalogue import, targets/export, warehouse-to-delivery, RMA evidence/service report, notification preferences and SMTP retry. Confirm a PostgreSQL backup and restore before production cutover.

## Security notes

- All state-changing JSON and multipart endpoints enforce the double-submit CSRF token.
- Financial totals, price decisions, adjusted balances and stock availability are recalculated on the server.
- Uploads use type and size allowlists, generated storage keys and resolved-path checks.
- Project/partner scope and role permissions are enforced server-side.
- Production startup fails closed for non-PostgreSQL URLs, weak secrets, insecure cookies or missing legal/bank identity.
- SMTP credentials are configuration-only and are never returned by API responses or included in delivery error metadata.
