# Release 5.0.3 requirement verification matrix

Audit date: 20 September 2026. Governing specification: `AlphaNumeric_Master_Feature_Audit_Repair_Final_ZIP_Prompt.md`; supporting detail: `AlphaNumeric_Release_5_0_2_Catalogue_Implementation_Prompt(1).md`.

Status meanings: **Pass** = implemented and exercised; **Partial** = useful implementation exists but a named acceptance item remains; **Blocked** = implementation exists but needs deployment credentials/infrastructure; **Not implemented** = absent and not represented as complete.

| Area | Status | Implementation and evidence | Remaining limitation |
|---|---|---|---|
| Lighting/Automation URL isolation | Pass | Workspace routes, API guards, cross-application tests | None confirmed |
| Workspace switching | Pass | Guarded navigation; inquiry draft warning | Browser automation unavailable in this environment |
| Authentication/session/CSRF | Pass | HttpOnly session flow, refresh rotation, CSRF dependencies, integration tests | Production SSO is outside this release |
| Roles and permissions | Pass | Backend permission dependencies and project memberships | Deployment role review remains operational |
| User administration/password change | Pass | Admin-only user APIs; forced password change tests | None confirmed |
| Customer/project/building/floor/room hierarchy | Pass | Normalized entities, scoped APIs, integration coverage | None confirmed |
| Main boards | Pass | Scoped CRUD and document output | None confirmed |
| Five-step inquiry workflow | Pass | Persisted drafts, structures, room products, BOQ, review | Manual cloud-browser walkthrough blocked by loopback policy |
| ANIPL numbering | Pass | Backend sequence and mixed-product regression test | None confirmed |
| Customer portal invitation | Pass | Optional invitation, reuse confirmation, revoke/resend/expiry/single-use tests | SMTP delivery needs deployment configuration |
| Customer/project authorization | Pass | Explicit membership/building scope; cross-project 403 tests | None confirmed |
| Catalogue landing routes | Pass | `/catalogue`, categories, products, imports, builder, versions | None confirmed |
| Catalogue dashboard counts | Pass | Category/family/product/missing data/status/import metrics | Missing-data counts are exact-variant based |
| Category hierarchy/API | Pass | Root/child tree, cycle and cross-app prevention, normalized name/slug uniqueness | None confirmed |
| Category metadata | Pass | Slug, descriptions, visibility, SEO metadata, actors/timestamps, status/order | Category icon upload remains URL/metadata only |
| Category tree UI | Partial | Tree, nesting, counts, create root/child, archive/restore, ordering field | No drag-and-drop and no separate edit drawer |
| Inline category creation | Pass | Real modal/API refresh, auto-select, product draft preservation | None confirmed |
| Product families/variants | Pass | Family detail/editor, exact SKU variant CRUD, availability | None confirmed |
| Product editor identity/content | Partial | Names, brand, model, SKU, HSN, descriptions, features, applications, warranty | Barcode, tags, installation/care/internal notes and structured highlight editor are absent |
| Product pricing | Partial | Fixed precision cost/base/tax, pricing rules, approvals, quotation snapshots | Dedicated MRP/dealer/reseller product price-history table is absent |
| Dynamic specifications | Pass | Typed definitions/values, constraints, units, visibility and ordered PDF output | Definition editing UI is less complete than API |
| Product media | Pass | JPEG/PNG/WebP decoded validation, checksum dedupe, metadata, ordering, primary image, secure delivery | Product PDF/document attachments are not implemented |
| Input focus defect | Pass | Root cause fixed in module-scope modal lifecycle; 13 realistic focus regression cases within 35 frontend tests | Cloud browser could not reach local loopback for an additional manual pass |
| Google Drive abstraction | Pass | Local and private Drive providers, authenticated proxy, quota and mocked error/missing tests | Real OAuth upload is a staging gate (no credentials supplied) |
| Media reconciliation/migration | Pass | `reconcile_media.py` and resumable `migrate_local_media_to_drive.py` support dry-run/provider checks | Real Drive credentials remain a staging gate |
| CSV/XLSX import | Pass | Template, dry-run, atomic/partial, row errors, formula protection; now application-locked | Commit import should be trialled with a production data copy |
| Arcot discovery/import | Not implemented | No unsafe scraper or invented pricing was added | Requires written reuse authorization and an approved-domain staging network path |
| Catalogue Builder | Pass | Metadata, price mode, inclusion settings and application-scoped snapshot | Product/category selection is API-capable but UI currently publishes the filtered active application set |
| Catalogue PDF | Pass | Shared snapshot renderer, cover/contents/product/spec/contact pages, download | Seed sample has no usable media, so placeholder path was exercised |
| Catalogue immutable versions | Pass | Unique version, stored JSON snapshot, publish/archive/download/audit; immutability test | Clone-as-new-version UI is not separate (new version form is used) |
| Product picker/room selection | Pass | Exact models, application scope, server pricing, per-room selection | Full-details presentation is compact rather than a side drawer |
| Project Book | Pass | 22-page A4 sample generated/rendered; room schedules, BOQ, unique data sheets | Seed media exercises placeholders |
| Building Book | Pass | 22-page A4 sample generated/rendered and access scoped | Seed project has one building, so content matches Project Book by design |
| Floor Sheet | Pass | Endpoint and automated document coverage | Separate sample not required by requested three-artifact gate |
| Room Sheet | Pass | Repaired 3-page A4 schedule with image/model/SKU/specs/qty/price/notes plus data sheets | Seed media exercises placeholders |
| Quotations/approvals/orders/invoices/payments | Pass | End-to-end business-chain tests and server-authoritative totals/PDFs | Tax/legal setup requires accountant review |
| Inventory/warehouse/dispatch/serial/warranty/RMA | Pass | Ledger/idempotency, dispatch, serial, RMA evidence/parts/service PDF tests | Physical barcode hardware integration is outside scope |
| Partners/zones/sales targets | Pass | Partner lifecycle, pricing scopes, target reporting/export | None confirmed |
| Notifications/email/support/resources | Pass | In-app/email delivery, retry, preferences, tickets, announcements/resources | SMTP provider is a deployment gate |
| Dashboards/search/reports/exports | Pass | DB-derived trends, authorization-aware search, PDF/XLSX/CSV exports | None confirmed |
| Responsive/accessibility | Partial | Responsive CSS, semantic controls, mobile focus regression at 390 px | Manual Chrome matrix at desktop/tablet/mobile blocked by cloud-browser loopback policy |
| Database migrations | Pass | Clean SQLite chain `0001 -> 0010`; schema head verified | PostgreSQL execution unavailable locally |
| PostgreSQL production enforcement | Pass | Production startup rejects non-PostgreSQL URLs | Managed PostgreSQL connection is a deployment gate |
| Docker/deployment assets | Pass | Dockerfiles, Compose and Render blueprint present and statically inspected | Docker executable is unavailable, so image build was not run |
| Security headers/production fail-closed | Pass | CSP, frame/content/referrer/permissions/HSTS; required secret/company/Drive checks | CSP should be rechecked behind the final reverse proxy |
| Automated regression suites | Pass | Backend 28/28; frontend 35/35; production build pass | Three non-failing dependency deprecation/serialization warnings documented |

## Release blockers versus deployment gates

No confirmed defect in the tested core workflow remains release-blocking. The items marked Partial are explicit scope limitations and must not be presented as implemented. The real Google Drive OAuth transfer, PostgreSQL migration against the target managed database, Docker image build, SMTP delivery, and reverse-proxy browser smoke test are deployment-environment gates.
