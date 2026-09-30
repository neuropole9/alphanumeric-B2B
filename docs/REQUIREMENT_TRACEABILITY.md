> **Archived Release 4 evidence:** historical only. Current schema head and validation are documented in `PRODUCTION_RELEASE_5.0.0.md`.

# Requirement Traceability — Latest Updated Validation-Pending Source

> Version 3.0 adds the operational portal matrix in docs/RELEASE_AUDIT_V3.md. Items marked blocked below remain environment gates rather than claimed passes.

| 3.0 requirement | Implementation | Validation | Status |
|---|---|---|---|
| Partner onboarding/profile/status | models.py, operations_api.py, Operations Centre | backend integration test | PASS |
| Inquiry stage state machine/history | InquiryStageHistory and stage APIs | transition validation/source | PASS |
| Warehouse stock ledger | Warehouse, StockLedger and stock APIs | receipt/idempotency/negative-stock test | PASS |
| Dispatch/partial quantity safeguards | Dispatch, DispatchItem and dispatch APIs | server validation/source | PASS |
| Serial and RMA lifecycle | SerialUnit, RMARequest and RMAHistory | duplicate/state guards | PASS |
| Announcements/notifications/tickets/resources | operational models/APIs/UI | backend tests + frontend build | PASS |
| Expanded logical roles | centralized permission matrix | backend authorization regression | PASS |
| Full PostgreSQL/Docker/browser production gate | deployment environment required | not run here | BLOCKED |

| Major requirement | Implemented location / evidence | Verification | Status |
|---|---|---|---|
| No runtime production demo seeding | backend bootstrap/startup + production config | Source scan + backend tests | **PASS** |
| Secure first admin bootstrap | `backend/app/bootstrap.py` | Backend tests / structural DB check | **PASS** |
| Forced password change | backend user/auth logic + `frontend/src/pages/ChangePasswordPage.tsx` | Backend/source verification | **PASS**; browser flow pending |
| PostgreSQL required in production | `backend/app/main.py`, `backend/app/db.py` | Production config/source test | **PASS**; real PostgreSQL runtime pending |
| Provider DB URL normalization | `backend/app/db.py`, `backend/migrations/env.py` | Source audit + compile/tests | **PASS** |
| Security headers / secure cookies | `backend/app/main.py` | Source audit + backend tests | **PASS**; deployed HTTPS validation pending |
| Decimal commercial calculations | backend commercial services | Backend tests | **PASS** |
| Inquiry lifecycle | backend inquiry/quotation services | Backend tests | **PASS**; browser E2E pending |
| Automatic idempotent DRAFT quotation | backend inquiry finalization | Backend tests | **PASS**; PostgreSQL E2E pending |
| Quotation snapshot/revision | backend commercial models/services | Backend tests | **PASS**; production E2E pending |
| Exact variant media precedence | backend catalog/report media selection | 3-image regression test | **PASS** |
| Family media fallback | backend catalog/report media selection | Regression coverage | **PASS** |
| Exactly one Project Book product image | `backend/app/reports.py` | PDF regression | **PASS** on isolated test; PostgreSQL final PDF pending |
| Main-board Project Book page | `backend/app/reports.py` | Backend/PDF regression | **PASS** on isolated test |
| Complete floor and room pages | `backend/app/reports.py` | Backend/PDF regression | **PASS** on isolated test |
| Aggregated BOQ / commercial history | `backend/app/reports.py` | Backend/PDF regression | **PASS** on isolated test |
| Project Document archive control | `frontend/src/pages/ProjectDocumentsPage.tsx` + authenticated API | Source audit/backend route coverage | **PASS** source; runtime UI pending |
| Deterministic frontend Docker build | root/frontend Dockerfiles, lockfile | Source audit | **PASS** source; runtime build blocked |
| PostgreSQL migrations | `backend/migrations/versions/0001..0005` | Structural migration to head | **PASS** structurally; PostgreSQL gate blocked |
| Frontend tests/build | frontend package scripts | Not executable | **BLOCKED** |
| Docker production runtime | Docker/Compose configuration | Docker unavailable | **BLOCKED** |
| Browser E2E + viewports | real stack required | Not executable | **NOT EXECUTED** |
| Every-button runtime audit | real stack required | Not executable | **NOT EXECUTED** |
| PostgreSQL-backed final Project Book | real production-style E2E data | Not executable | **NOT EXECUTED** |
| Restart persistence | Docker/PostgreSQL required | Not executable | **NOT EXECUTED** |
| Clean ZIP extraction | Complete packaged source | Extract/import/backend tests/compile/structural migration | **PASS** |
