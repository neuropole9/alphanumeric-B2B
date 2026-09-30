# AlphaNumeric B2B Release 5.0.1 Audit

Audit date: 2026-09-20  
Source: `AlphaNumeric-B2B-Production-Release-5.0.0.zip`  
Requirements: `AlphaNumeric_Release_5_Implementation_Prompt.md`

## Result

Release 5.0.0 was functional but not deploy-ready against the full Release 5 prompt. Confirmed implementation defects were corrected in 5.0.1. The corrected source passes the backend and frontend suites, a production frontend build, dependency audit, fresh schema migration, 0008-to-0009 upgrade migration, and rendered PDF inspection.

Production rollout remains conditional on environment-specific checks that cannot be performed without the target infrastructure: PostgreSQL migration rehearsal/restore, real Google Drive OAuth and quota behavior, SMTP delivery, HTTPS/proxy configuration, and company-data UAT.

## Requirement status after correction

| Area | Status | Evidence / correction |
|---|---|---|
| Application isolation | Implemented | Application-locked product picker, scoped search routes, backend cross-application rejection, workspace checks and database constraints. |
| Catalogue hierarchy | Implemented | Parent-cycle validation, case-insensitive sibling uniqueness including root categories, family and exact-variant workflow. |
| Dynamic specifications | Implemented | Text, long text, number, decimal, boolean, single/multi select, date and measurement; help, units, defaults, bounds, precision, visibility and search metadata; category/family scope validation. |
| Product media workflow | Implemented | Multiple file selection/drop, file-count progress, cancel/retry, strict decode, size/count limits, SHA-256 deduplication, bounded storage retries, primary/order metadata and soft archival. |
| Google Drive abstraction | Implemented; live credentials required | Private OAuth provider, application/product folder lookup, persisted file/parent IDs, provider-aware reads, quota endpoint, migration/reconciliation tools and mocked provider tests. |
| Customer invitations | Implemented | Explicit existing-account confirmation, no password reset for active reused accounts, project/building scope, single-use rotation/revoke/expiry, database-backed throttling and audit events. |
| Media authorization | Implemented | Application plus project/building authorization, archived/failed media denial, private cache headers, safe disposition, length and checksum ETag. |
| Inquiry safety | Implemented | Unsaved-change warning, application switch confirmation, application-locked product selection and existing-project/building reuse. |
| Project Book PDF | Implemented | Actual product image in room tables; family, variant/model, SKU, specifications, notes, quantity and unit; technical appendix and BOQ. |
| Quotation PDF | Implemented | Image, product/model, SKU, quantity, unit, rate, discount, tax, amount and technical-specification appendix. |
| Database migration | Implemented | Revision 0009 adds missing spec/media/scope/throttle fields, portable application checks, foreign keys and normalized category uniqueness. Read-only preflight is included. |
| Security baseline | Implemented | CSRF, secure cookies, CSP/security headers, role checks, project/building scope, upload verification, stored token hashes and database-backed activation throttling. |

## Confirmed Release 5.0.0 defects corrected

- Removed cross-application “All Products” picker behavior and corrected cross-workspace search navigation.
- Completed specification-definition schema and typed normalization, including family scope, measurement units, bounds and precision.
- Replaced the incomplete variant specification editor and internal-key display with label-based typed controls.
- Added multi-image selection/drop, progress, cancel and retry behavior.
- Added checksum deduplication and bounded provider retries; made reads/reconciliation honor each row's stored provider.
- Changed destructive product-media deletion to archive behavior with deterministic primary replacement.
- Added project and optional building authorization to media, project workspace, reports and invitation memberships.
- Prevented an existing active account invitation from acting as a password-reset token.
- Added explicit confirmation before granting an existing account access and restricted invitation roles.
- Replaced per-process activation throttling with database-backed attempt state.
- Added portable application checks and case-insensitive root/sibling category uniqueness.
- Added real images and required product detail columns to room tables and quotation PDFs.
- Added unsaved inquiry warnings and fixed application-aware global-search links.
- Made tests use a hermetic test database regardless of import order.

## Verification performed

| Check | Result |
|---|---|
| Backend pytest | 26 passed |
| Frontend Vitest | 22 passed |
| TypeScript + Vite production build | Passed; 2,281 modules transformed |
| Production npm audit | 0 vulnerabilities |
| Python compile | Passed |
| Fresh SQLite Alembic migration | Head `0009`; schema verified |
| Existing SQLite upgrade | `0008` → `0009`; schema verified |
| Release 5 preflight on seeded test data | Pass; 0 issues |
| Project Book render | 31 A4 pages; no clipping/overlap found; room images and columns verified |
| Quotation render | 2 A4 pages; commercial table and technical appendix verified |

## Environment-specific deployment gates

These are not source-code failures, but must pass before production traffic:

1. Back up production PostgreSQL, run `python -m scripts.release5_preflight`, rehearse `alembic upgrade head` on a restored copy, and verify rollback/restore timing.
2. Test the dedicated Google Drive account with real OAuth credentials: upload, stream, archive, quota warning, refresh-token rotation and reconciliation.
3. Test real SMTP delivery, resend, expiry and existing-account grant notifications.
4. Run browser UAT at desktop/mobile widths on the deployed HTTPS origin. The audit environment's remote browser could not reach its localhost server, so frontend verification here used source review, unit tests and the production build.
5. Validate real company identity, GST/place-of-supply policy, bank details, product master, least-privilege roles and backup monitoring.

## Deployment decision

The 5.0.1 package is suitable for staging deployment. Production readiness is **conditional** on the five target-environment gates above; no further implementation prompt is required unless one of those checks fails.
