# AlphaNumeric B2B Production Release 5.0.3 validation report

## Repair summary

- Fixed the release test harness deleting SQLite during pytest collection; the full backend suite now runs reliably.
- Preserved the Release 5.0.2 input-focus fix. Root cause: the Modal escape-key effect depended on an inline `onClose` function, so every keystroke tore down/rebound modal lifecycle work and contributed to unstable form descendants. `onClose` is held in a ref and the effect depends only on `open`; form components remain at module scope and repeatable rows use persistent IDs.
- Added application-specific Catalogue Management navigation and functional landing, category, product, import, builder and versions routes.
- Added category slug, description, visibility, SEO, actor and timestamp metadata; normalized uniqueness; unsafe-markup rejection; cycle/cross-application checks; archive/restore; counts.
- Added inline category creation without losing the current Add Product draft.
- Locked catalogue imports and import history to the active application and added import-download authorization checking.
- Added immutable, audited catalogue publication snapshots and a common preview/download A4 PDF renderer.
- Repaired Room Sheet product layout to include image/placeholder, exact model, model number, SKU, ordered key specifications, quantity, price/tax when authorized, placement notes and detailed per-product specification blocks.
- Added Alembic revision `0010` without destructive data changes.

## Exact executed results

| Check | Result |
|---|---|
| Backend `pytest -q` | **28 passed**, 3 warnings, 0 failed |
| Frontend `vitest run` | **35 passed**, 5 files, 0 failed |
| Frontend production build | **Pass**, 2,282 modules transformed |
| `npm audit` | **0 vulnerabilities** |
| Clean migration | **Pass**, revisions `0001` through `0010 (head)` |
| Release preflight | **Pass**, zero reported issues |
| Project Book | **Pass**, 22 A4 pages, 43,067 bytes, every page rendered |
| Building Book | **Pass**, 22 A4 pages, 43,025 bytes, every page rendered |
| Room Sheet | **Pass**, 3 A4 pages, 7,415 bytes, every page rendered after repair |
| PDF text/layout review | **Pass**, no raw JSON/HTML, clipped tables, distorted images or accidental blank pages observed |
| Docker image build | **Not executed**, Docker command unavailable |
| PostgreSQL migration | **Not executed**, no PostgreSQL service/credentials supplied |
| Real Google Drive upload | **Not executed**, no OAuth credentials supplied; mocked provider tests pass |
| Manual Chrome responsive pass | **Blocked**, cloud browser policy could not open local `127.0.0.1`; automated mobile-width focus test passes |

Warnings are limited to Starlette's `BlockingPortal` deprecation and Pydantic Decimal serializer warnings in two tests. They do not fail the suite but should be removed during the next dependency-maintenance cycle.

## PDF visual inspection

Project and Building Books were rendered at 120 DPI into 22 PNG pages each and reviewed as contact sheets, with full-size inspection of the dense room schedule and both technical-specification pages. The repaired Room Sheet was rendered and reviewed at full size page-by-page. Tables stay inside A4 margins, headings and footers are visible, long specification values wrap, placeholder media preserves the grid, and each exact product receives one detailed block.

Validation samples are in `validation_artifacts/pdfs/` and the reproducible generator is `backend/scripts/generate_release_validation.py`.

## Security and permission review

- Catalogue/category/publication mutations require CSRF and administrator product permission.
- Application access is checked server-side for reads and writes.
- Category parents and publication selections cannot cross applications.
- Catalogue imports are locked to one explicit application; mismatched rows are rejected.
- Media remains private and passes through authenticated authorization-checked endpoints.
- Uploaded images are decoded and type/size/checksum validated; malformed image and cross-application media tests pass.
- Category and catalogue rich text rejects active-content patterns; PDF output escapes all stored text.
- Production startup fails closed for database type, secret/cookie security, company identity, bank fields and Google Drive credentials.

## Known limitations and deployment gates

See the feature matrix for every Partial/Blocked item. Most importantly: Arcot ingestion was not implemented without reuse authorization; product attachments and full historical multi-tier price tables are absent; category drag/drop and a few rich product-content fields remain partial. Real Drive OAuth, managed PostgreSQL migration, Docker build, SMTP delivery and public HTTPS/browser smoke tests must be run in staging.

## Deployment decision

The archive is deploy-ready for a **staging deployment** after the documented environment values are supplied. Production promotion remains conditional on the five environment gates above and on acceptance of the explicitly Partial/Not implemented matrix rows.
