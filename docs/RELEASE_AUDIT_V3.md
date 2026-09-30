# AlphaNumeric B2B Portal 3.0 — Release Audit

Date: 2026-09-18

## Verdict

**RELEASE CANDIDATE.** All locally executable backend, frontend, migration and archive gates pass. It is not labelled deploy-ready because a real PostgreSQL upgrade/fresh migration, Docker runtime, authenticated browser E2E, viewport inspection and protected reference-portal comparison were not executable in this environment.

## Preserved baseline

- Cookie/JWT authentication, refresh-session revocation, CSRF checks and forced password change.
- Admin-created users and project-user isolation.
- Customer → project → building → floor → room → product hierarchy.
- Five-step inquiry wizard, mixed Lighting/Automation rooms, draft resume and ANIPL sequence.
- BOQ, quotation revisions, accepted-quotation conversion, orders, invoices, payments, PDF/Excel exports and Project Book.
- Catalogue families, variants, specifications, media precedence, product proposals and project documents.

## Added in 3.0

- Central logical role-to-permission matrix for super admin, sales, design, accounts, warehouse, dispatch, service, partner and project users.
- Extended partner profiles, types, credit settings, territories/zones, activation state and duplicate detection.
- Server-enforced inquiry pipeline transitions with immutable stage history.
- Warehouses and immutable, idempotent stock ledger with no-negative-stock enforcement.
- Order conversion now locks and validates product availability before reserving.
- Partial dispatch records and line-level over-dispatch prevention, delivery state and proof fields.
- Serial/batch registry and warranty/customer/project/room destination fields.
- RMA requests with serial duplicate prevention and enforced service transition history.
- Approval-request persistence foundation.
- Announcements, per-user notifications, support tickets and controlled resource links.
- Operations Centre UI with persisted live data, role-aware navigation, responsive tables and working create flows.
- Liveness and database-backed readiness endpoints.

## Migration

0006_operational_portal is additive. It extends partners/users and creates stage history, approvals, warehouses, stock ledger, dispatch, serial, RMA, announcement, notification, ticket and resource tables. It does not drop existing business tables or rewrite identifiers. The downgrade removes 3.0 operational data and therefore must only be used with an approved backup/change plan.

## Authorization boundaries

Backend permission checks are authoritative. Partner stock is partner-scoped, project records require an active project assignment outside admin roles, notifications are user-owned, support records are creator/service scoped, and unsafe resource URLs are rejected. Existing cross-project denial coverage remains.

## Executed validation

| Gate | Result |
|---|---|
| Python compile | PASS |
| Backend tests | PASS — 13 |
| Fresh structural migration | PASS — 0001 through 0006 |
| Frontend tests | PASS — 16 |
| TypeScript + Vite production build | PASS |
| Locked dependency install | PASS |
| Archive integrity and clean extraction | recorded in final package verification |

## Environment-blocked gates

- Real PostgreSQL fresh and supported-upgrade migration.
- Docker Compose service startup and restart persistence.
- Browser E2E journeys and desktop/tablet/mobile screenshot inspection.
- Authenticated areas of the reference portal; public URL access was not available.
- Deployed TLS/security-header verification and dependency-vulnerability resolution against the final production image.

## Known functional gaps

The release does not falsely claim every enterprise extension in the master specification is complete. Proforma/credit/debit-note documents, configurable price-rule priority resolution, sales targets, product bulk-import row reports, RMA evidence uploads/parts costing, outbound email delivery and full frontend create/edit surfaces for every operational entity still require a subsequent implementation phase. Existing workflows remain usable and the 3.0 additions are persisted APIs, not mock screens.

## Deployment

1. Copy .env.example to .env and replace every production placeholder.
2. Set a PostgreSQL DATABASE_URL, strong SECRET_KEY, secure bootstrap admin values and COOKIE_SECURE=true.
3. Run docker compose up --build.
4. Confirm /health/live and /health/ready.
5. Sign in with the configured bootstrap administrator and change the temporary password immediately.

Never use test fixture credentials in production.
