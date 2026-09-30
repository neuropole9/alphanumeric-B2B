# Requirements Traceability and Release Audit

The authoritative requirement set is `AlphaNumeric_B2B_Final_End_to_End_Requirements_and_Audit(1).docx`. This matrix records the implemented release-candidate state.

## P0 traceability

| P0 requirement | Implementation | Verification |
|---|---|---|
| Existing-context inquiry wizard | Wizard accepts `project_id` and `building_id`, loads the selected structure, carries stable floor/room IDs, and merges without deleting shared records | Integration test prevents duplicate building/floor/room records |
| Multi-building structure CRUD | Building, floor, room, and main-board create/update/archive APIs; parent scope validation; floor detail UI | Migration + API tests + production build |
| Product editor | Family editing, variant editing, category-defined typed specs, media upload/order/primary/delete/fullscreen, stock movement | Backend validation test + TypeScript build |
| Admin proposal → customer decision | Admin creates draft/pending proposal; admin cannot decide; assigned project user approves/rejects; only approval creates room product | Integration test |
| Building/floor plan documents | Revisioned scoped upload/list/preview/download UI and API; MIME/signature/size validation; document register and plan images in books | Upload/download/report integration test |
| Invoice integrity | Server-authoritative company, tax identity, bank details, amount in words, payments and balances; no hardcoded JSX identity | Integration test + source scan |
| Product request/cart | Project/building/room selector, exact-variant cart, required room scope, submission feedback | API test + production build |
| Main-board management | Scoped main-board create/update/archive, building and floor schedules, book output | API/model/report coverage |
| Contextual completeness | Customer → project → building → floor → room routes, breadcrumbs, floor/room/order detail pages | TypeScript build + route inventory |
| Commercial privacy | Project permissions for documents and prices; server-side list/detail/PDF enforcement and response redaction | Integration test |
| Production configuration | No production runtime business seeding; production fail-closed company/bank/secret validation, placeholder-only examples | Runtime smoke + source scan |
| Release gates | Unit/integration/build/SQLite migration/runtime/report/security gates executed; PostgreSQL/Docker and browser viewport checks remain blocked by the runner | `DELIVERY_VERIFICATION.md` |

## Necessary P1 completion

- Customer contacts and project stakeholders are normalized and exposed through scoped APIs.
- Quotation terms, revision lineage, send/accept timestamps, and supersession are persisted.
- Order delivery address, dispatch reference, dispatch timestamp, and building scope are persisted.
- Invoice payments and balance status are persisted.
- Category specification definitions provide required, numeric, boolean, and select validation.
- Report snapshot metadata model is included for immutable report lineage.
- Operations documentation covers migration, rollback preparation, backup/restore, media persistence, and release checks.

## Information architecture

- Admin sidebar: Dashboard, Customers, Product Catalogue, Settings, Audit Log, and Create Inquiry.
- Project users: My Project, Product Catalogue, My Requests, and Approvals.
- Commercial documents remain contextual to customer/project/building and permission gated.

## Known release blockers

This package must not be promoted to production until PostgreSQL/Docker execution and browser E2E/viewport checks pass in the deployment environment.
