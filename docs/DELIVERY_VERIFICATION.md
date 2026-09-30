> **Archived Release 4 evidence:** historical only. Current schema head and validation are documented in `PRODUCTION_RELEASE_5.0.0.md`.

# Delivery Verification — 2026-09-17

## Executed gates

| Gate | Result | Evidence |
|---|---|---|
| Python compilation | PASS | `python -m compileall -q app tests` |
| Backend integration/security tests | PASS | 8 tests passed, including the exact 103-unit lifecycle |
| Frontend domain/navigation tests | PASS | 8 tests passed |
| TypeScript + Vite production build | PASS | `tsc -b && vite build` |
| Clean Alembic upgrade | PASS | revisions 0001 through 0005, head `0005` |
| Backend runtime | PASS | `/health`, isolated test login, and 89-path OpenAPI document through `TestClient` |
| Frontend preview runtime | PARTIAL | built HTML and hashed assets compiled; browser could not reach the local runner |
| npm production dependency audit | PASS | 0 vulnerabilities |
| Python dependency consistency | PASS | `pip check` found no broken requirements |
| Project/building/quotation/invoice PDFs | PASS | response signatures and authorization verified by integration tests |
| Project/building BOQ XLSX | PASS | generated workbooks verified by response signature and integration tests |
| Security/package scan | PASS | no shipped `.env`, secrets, virtual environments, caches, local DBs, test uploads, or generated builds |

## Covered critical flows

- Existing-project and existing-building inquiry context without duplicate hierarchy records.
- Cross-project authorization and parent/child scope validation.
- Explicit room-scoped product requests.
- Admin proposal followed by independent project-user approval/rejection.
- Product media signature validation and authenticated delivery.
- Revision-controlled project document upload/list/preview and inclusion in project books.
- Archive-safe floor and room mutations.
- Project permission redaction of commercial records and prices.
- Invoice payment balance tracking and configured legal/bank identity.
- Project-level BOQ export and room-level breakdown across all buildings.
- Project, building, floor, room, BOQ, quote, order, and invoice report endpoints.

## Environment limitations

- Docker and PostgreSQL executables were not available in the verification workspace. The image and PostgreSQL Compose stack were therefore not executed here.
- No browser executable was available to the local runner, and the remote browser cannot access the local preview. Full click-path/viewport E2E remains a deployment-environment gate.
- Production company-specific UAT, backup/restore rehearsal, and statutory review remain operator responsibilities.

Because the PostgreSQL/Docker and browser viewport gates above are not executed, this artifact is classified as a **release candidate**, not an unqualified production-ready release.
