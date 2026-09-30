# 5.0.11

- Keep legacy imported catalogue provenance on variant edits without sending `source_url` as an editable technical specification. Reject newly introduced or changed unknown specification keys.
- Retain the compact project book, room tables, seven-column BOQ and two-product technical cards from 5.0.10. A project book containing Main Board Details or one full-page catalogue description per product was produced by older code; rebuild the app image and confirm `/api/openapi.json` reports 5.0.11.

# 5.0.10

- Align every full-width section bar, floor schedule, room product table, financial section and cover precisely with the outer page rails.
- Display room lights in a clear product table with image, product, model, voltage, quantity, unit, rate and total.
- Preserve room grouping, calculation and authorization behavior.

# 5.0.9

- Arrange configured product rows by room in complete, readable sections; keep each normal room with its subtotal on one page.
- List empty rooms once in their floor schedule instead of repeating empty product tables.
- Preserve project financial totals and every quotation, invoice, authorization and download route.

# Changelog

# 5.0.8

- Client-ready report layout: align section bars and tables with the outer frame; remove unused room fields and main-board placeholder table; condense technical cards and unnecessary page breaks.
- Preserve BOQ financial calculations, quotation/invoice content, permissions, and download routes.

# 5.0.7

- Put the naturally ordered model grid first on the COB family page and keep four cards on wide laptop screens.
- Allow unchanged legacy catalogue provenance specifications during variant PATCH while rejecting new or altered unknown keys; align validation with active definitions.
- Package CA1–CA10 image assets in the Compose image, resolve their path in both environments, and add a read-only deployed-data check.
- No schema change; existing PostgreSQL data and media volumes remain authoritative.

# 5.0.6

- Normalized variant edit payloads to decimal strings, null optional prices, validated numeric inputs and configured specification keys; surfaced backend field errors inside the edit dialog.
- Corrected customer invitation role values and normalized safe presentation variants while retaining privileged-role rejection.
- Added a responsive naturally ordered COB model gallery with exact variant media and a controlled missing-image placeholder. Added an opt-in importer for bundled CA1–CA10 local images.
- Aligned the shared PDF page frame, simplified aggregated BOQ to seven columns, and rendered compact alias-aware technical cards while preserving financial document content and routes.
- Added backend and frontend regression coverage. No schema revision; Alembic head is `0011`.

# 5.0.0 — 2026-09-19

- Isolated Lighting and Automation across routes, APIs, permissions, catalogues, inquiries, dashboards, search and reports.
- Rejected cross-application product injection and legacy mixed quotation generation.
- Added hierarchical categories, family/variant catalogue, typed dynamic specifications and ordered document rendering.
- Added private local/Google Drive media providers, strict image decoding, authenticated streaming, reconciliation and migration tools.
- Added pending customer accounts, hashed single-use invitations, activation, expiry/revocation and project/application grants.
- Fixed Super Admin parity without widening specialized role permissions.
- Added Alembic revision `0008` and Release 5 security, data, Drive, backup and validation documentation.

## 4.0.0 — 2026-09-18

### Added
- Complete operational forms and controlled status transitions for partners, warehouses, stock, dispatch/delivery, serials, warranty, RMA service, announcements, support and resources.
- Proforma invoices, credit/debit notes, server-authoritative totals, PDF output and adjusted invoice balances.
- Deterministic scoped pricing rules with explain output and quotation approval enforcement.
- Sales targets with persisted definitions, calculated actuals, drill-down and CSV export.
- CSV/XLSX catalogue import with template, dry-run, atomic/partial modes, validation history and row-level error exports.
- RMA assessment, evidence, parts/labour, SLA, stock consumption and service-report PDF workflows.
- Optional console/file/SMTP delivery with idempotent logs, retry and notification preferences.
- Alembic revision `0007` and Commercial Control UI.

### Verification
- Backend: 16 integration/security tests pass.
- Frontend: 16 unit tests pass; TypeScript and Vite production build pass.
- Fresh SQLite Alembic chain reaches `0007 (head)`; OpenAPI exposes 178 operations across 138 paths.
- This build environment does not contain Docker, PostgreSQL client/server, or a browser runtime, so those infrastructure-dependent gates are documented as not executable here and remain mandatory in the target deployment environment.

## 2.2.3-validation-pending.2 — 2026-09-18

### Fixed
- Preserved all prior production-hardening, commercial workflow, Project Book, media, password-change and document-workflow fixes.
- Corrected Alembic PostgreSQL URL handling so provider-style `postgres://` / `postgresql://` URLs are normalized to the installed psycopg v3 driver before migrations connect.
- Included the exact-variant-first media correction, 3-image PDF regression and restored Project Document Archive UI from the latest validation pass.

### Verification
- Backend: 11/11 tests pass.
- Python compilation passes.
- Structural Alembic chain reaches `0005` head.
- Docker/PostgreSQL/npm/browser production gates remain blocked or not executed in the current environment; this source package is therefore Validation Pending, not Production Ready.


## 2.2.3 — Project Book visibility and reference verification

### Changed
- Added immediate Preview Project Book and Download Project Book actions to the Project page header for authorized admin and project users.
- Retained the existing Building page Preview Book, Download PDF, and Download BOQ actions.
- Added typed, URL-safe project and building book route helpers.

### Verification
- Confirmed the Project Book renderer matches the uploaded 12-page reference structure: branded cover, inquiry/customer/partner information, document register, project summary, floor views, room configurations, aggregated BOQ, commercial history, and page numbering.
- Added regression assertions for Project Book and Building Book MIME types, attachment filenames, 12-page output, required headings, and the 103-unit acceptance scenario.

## 2.2.2 — Inquiry validation and session-refresh correction

### Fixed
- Displayed field-specific FastAPI validation messages instead of hiding HTTP 422 details.
- Added client-side validation for customer/partner email, partner mobile, room measurements, occupancy, product identity, and positive quantities.
- Normalized inquiry text fields and stopped sending update-only fields during inquiry creation.
- Serialized simultaneous access-token refresh attempts so parallel API requests share one refresh operation.
- Moved PDF test parsing and pytest out of production dependencies into `requirements-dev.txt`.

## 2.2.1 — Quotation and invoice document separation

### Fixed
- Routed quotation view/download actions exclusively to the quotation PDF endpoint and invoice actions exclusively to the invoice PDF endpoint.
- Added document-specific attachment names and safe server-side `Content-Disposition` headers.
- Restored a full quotation layout with project/customer metadata, itemized BOQ, tax breakdown, totals, terms, warranty, notes, and page numbering.
- Prevented quotation generation when persisted BOQ lines are missing and invoice generation before quotation acceptance/order confirmation.

### Verification
- Added API regression coverage for document identity, MIME type, filenames, authorization, missing records, cross-ID access, repeat generation, and the 103-unit Chaitanya Arcot lifecycle.
- Added frontend regression coverage proving quotation and invoice helpers use distinct resource paths.
- Preserved the existing Project Book and BOQ renderers without modification.

## 2.0.0 — Customer, building, product and report workspace

### Added
- Contextual Customer → Project → Building → Floor → Room workspaces with deep links, breadcrumbs and scoped commercial history.
- Normalized product families, exact variants and authenticated product-media management.
- Building main boards, room product schedules and auditable product proposal approvals/rejections.
- Project and building book PDFs, room-sheet PDFs, and a formatted two-sheet building BOQ workbook.
- Database migration `0004` for the normalized catalogue, building metadata, boards, room products and proposals.

### Changed
- Reduced Admin navigation to Dashboard, Customers, Product Catalogue, Settings and Audit Log.
- Reworked product selection into a family-first, exact-variant confirmation flow.
- Added route-level frontend code splitting and real media-backed product cards.
- Production startup now requires real company, tax, banking and secret configuration; fake production defaults were removed.
- Added persistent media storage to Docker Compose and the Render blueprint.

### Security and verification
- Hardened SPA static-file path resolution and retained cookie, CSRF, role and project-membership controls.
- Expanded backend coverage to 6 integration/security tests; frontend domain coverage remains 4 tests.
- Verified fresh and legacy upgrades through `0004`, report generation, every PDF page, and both BOQ workbook sheets.

## 1.1.2 — Application-wide UI refinement

### Changed
- Introduced a cohesive visual system across the complete Admin and Project User application.
- Redesigned the sidebar, workspace switcher, top navigation, global search, page headers, cards, buttons, forms, dialogs, status indicators, empty states and responsive breakpoints.
- Rebuilt the Projects page with structured project identity, customer, location, building/system statistics and clear navigation actions.
- Upgraded Customers, Quotations, Invoices, Settings and Audit Log with dedicated page hierarchy, summary surfaces and readable data tables.
- Improved dashboard, inventory, project detail, customer detail, inquiry detail, orders, room detail, quotation detail and invoice presentation through shared production-grade components.
- Replaced placeholder product glyphs with consistent Lucide product icons.

### Fixed
- Corrected project cards that were falling back to browser-default button styling.
- Corrected collapsed project names, customer names, addresses, statistics and status controls.
- Fixed missing cart-row layout styling and inconsistent modal/form controls.
- Added safe table overflow, responsive card grids and compact navigation behavior for standard laptop, tablet and mobile widths.
- Corrected notice and activity-timeline selectors so success, warning, error and audit states render consistently.

## 1.1.1 — Inquiry wizard visual refinement

### Changed
- Rebuilt the five-step inquiry interface with a consistent card hierarchy, aligned form controls, clearer spacing and responsive layouts.
- Redesigned Floors & Rooms into structured floor panels with independent room cards and compact duplicate/delete actions.
- Redesigned Room Products into a project-room navigator and aligned product assignment table.
- Reworked BOQ Review and Final Review with readable product rows, summary metrics and stronger information hierarchy.
- Rebuilt the product picker as an overflow-safe, responsive modal with styled filters, product cards and assignment controls.

### Fixed
- Removed duplicate wizard step indicators and normalized active/completed step states.
- Removed browser-default-looking controls in the inquiry wizard.
- Fixed collapsed labels, quantities and metadata in product and BOQ rows.
- Prevented horizontal modal overflow at standard laptop and tablet widths.

## 1.1.0 — Project-scoped production workflow

### Added
- Five-step Admin inquiry wizard: Project & Client, Floors & Rooms, Room Products, BOQ Review, Final Review.
- Persisted inquiry drafts with resume/edit support and backend-generated `ANIPL0001` numbering.
- Optional Partner entity and project relationship.
- Explicit `ProjectUser` membership for customer/project access.
- Project detail workspace with Overview, Floors & Rooms, Users, Inquiries, Quotations, Orders and Invoices.
- User-facing My Project, Room Detail, Shop Products, local cart and server-persisted B2B product request flow.
- Inquiry-specific Quotation and Activity tabs.
- Project-scoped commercial history and invoice visibility.
- Real 30-day, 3-month and 6-month dashboard aggregation from database timestamps.
- Database migrations `0002` and `0003` for project scoping and integrity constraints.

### Changed
- Inquiry room structure now stores independent rooms for every floor instead of repeating one global room list.
- Room requirements support both Lighting and Automation products in the same project/inquiry structure.
- Project user management moved from the main sidebar into Project → Users.
- Global search routes Product, Customer, Project, Inquiry, Quotation, Order and Invoice results.
- Primary production flows use application modals/notices instead of browser `prompt()`/`alert()`.
- Customer, project and inquiry tab controls now change real content and route to real records.

### Fixed
- Inquiry quotation lookup is now keyed by `quotation.inquiry_id`.
- Save Draft now persists and updates the same inquiry rather than behaving as a decorative control.
- Dashboard period selectors now refetch and update actual trend data.
- Recent Customer/Product Alert navigation is functional.
- Duplicate room-product assignments are merged by quantity and protected by a database uniqueness constraint.
- Inquiry editing refuses destructive project-structure replacement when rooms are referenced by another inquiry.
- Corrected the Vite TypeScript project configuration so the real `tsc -b` production gate succeeds.
- Added executable inquiry-wizard domain tests and made frontend tests mandatory in CI.
- Locked frontend dependencies and switched CI/Docker builds to deterministic `npm ci` installs.

### Security
- Customer/project users are authorized by explicit active `ProjectUser` membership, not `Inquiry.owner_id`.
- Cross-project URL access returns HTTP 403.
- Internal CRM/commercial mutation endpoints require Admin authorization.
- New project users receive a cryptographically random one-time temporary password when an invitation account is created; no shared hard-coded password remains.
- Existing HTTP-only cookie, CSRF and permission checks remain in place.

### Database Changes
- New `partners` and `project_users` tables.
- Added user phone, project partner/status metadata, inquiry draft/workspace metadata, room sort order and invoice project linkage.
- Added referential integrity/indexes and unique `(inquiry_id, room_id, product_id)` requirement constraint.
- Legacy invoice `project_id` is backfilled from Order → Project where possible.

### Verification
- Backend integration/security suite: 4 passed.
- Frontend inquiry-wizard domain suite: 4 passed.
- TypeScript and Vite production build: passed.
- Fresh and legacy-schema Alembic upgrades through `0003`: passed.
# Release candidate 2.1 — 2026-09-17

- Added migration 0005 for project permissions, scoped commercial records, contacts, stakeholders, documents, typed product specs, payments, and report snapshots.
- Made inquiry editing safe for existing projects/buildings and stable floor/room identities.
- Enforced independent admin proposal and customer approval roles.
- Added customer request cart, approvals, floor detail, order detail, and plans/documents screens.
- Completed family/variant/spec/media editing and authenticated document management.
- Removed hardcoded invoice identity and bank data from the frontend.
- Added commercial price/document permission redaction and production fail-closed configuration.
- Expanded release verification, report rendering, security scans, and operations documentation.
# 2.2.0 — Project workspace and commercial lifecycle correction

- Replaced ambiguous project/building navigation with Customer → Project → Building → Floor → Room.
- Added the eight-section project workspace and limited building pages to physical configuration.
- Added persisted project/building BOQ aggregation, filters, room breakdown, and project BOQ Excel export.
- Added record-backed workflow tracking and actionable commercial empty states.
- Preserved project/building context in inquiry creation and corrected direct commercial detail routes.
- Made `RoomProduct` the authoritative current configuration while retaining inquiry BOQ snapshots.
- Added the exact 103-unit acceptance lifecycle, idempotency, scope, authorization, PDF, and Excel tests.
- Removed secrets, virtual environments, caches, generated builds, local databases, and test uploads from release packaging.
# 5.0.5

- Replaced the dense Project Book room-product grid with readable product cards containing the primary image, family, exact variant/model, SKU, ordered specifications, quantity, unit, unit price, and pre-tax line total.
- Added per-room subtotal-before-tax and a final aggregated BOQ with the complete commercial summary; GST is now shown only in the final summary and never mixes CGST/SGST with IGST.
- Added shared Decimal-safe quantity, percentage, and Indian-number currency formatters for commercial PDFs.
- Rebuilt the invoice document as a distinct server-generated tax invoice with project/shipping details, product family/model/SKU, discount, taxable value, tax amount, amount in words, payment status, bank details, terms, signature area, repeated item headers, and page numbering.
- Added PDF regression coverage for quantity formatting, Project Book tax placement, invoice completeness, tax exclusivity, and preview/download content parity.
- Corrected release packaging to include both environment templates and made persistent local media the Compose default; documented application settings are now forwarded into the app container.
- Removed stale deployment guidance that forced Google Drive or recommended deleting Docker volumes.
- No schema change; Alembic head remains `0011`.

# 5.0.4

- Added editable, accessible category tree administration with drag/drop, keyboard reordering, parent moves, cycle validation, and audited ordering persistence.
- Completed exact-product identity and content fields: internal name, manufacturer, barcode, tags, full description, structured highlights/features/applications, installation, care, warranty summary, and protected internal notes.
- Added fixed-precision MRP, project, dealer, reseller, base, and cost prices with approval state, effective periods, overlap protection, and immutable history.
- Added rights-gated Arcot discovery/import with HTTPS domain allowlisting, DNS/redirect SSRF controls, dry-run diff, idempotency, downloadable reports, private-asset policy, and mandatory `PRICE_REQUIRED` drafts.
- Added migration `0011` with preservation/backfill for existing products and baseline price history.
- Expanded continuous-typing regression coverage and responsive/accessibility rules.
- Replaced PDF validation placeholders with two mapped sanitized PNG product images, explicit primary-image switching, proportional rendering, and controlled missing-image fallback.
- Expanded final verification documentation and clean-archive checks.

# 5.0.3

- Added application-specific Catalogue Management routes, dashboard, category tree, imports, builder and immutable publication versions.
- Added complete category metadata/validation and inline category creation that preserves product drafts.
- Locked catalogue imports/history to the active application.
- Added migration `0010` and catalogue snapshot/PDF regression tests.
- Repaired Room Sheet product schedules and technical specification blocks.
- Fixed hermetic backend test database ownership; preserved and revalidated the Release 5.0.2 continuous-typing fix.
