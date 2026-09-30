# Documentation / UI reference implementation map

The application was built against `reference/Project_Documentation.docx` and the supplied Admin/User UI mockups in `reference/`.

## Implemented flows

| Requirement | Implementation |
|---|---|
| One app, Lighting + Automation | Workspace switcher persists route context and backend workspace authorization |
| Admin/User login | Cookie auth, Argon2 passwords, refresh rotation, CSRF, role/permission checks |
| Admin dashboard | KPI cards, inquiry overview, trend chart, stock alerts, recent customers |
| User dashboard | Same visual system with backend-scoped own/assigned metrics |
| Product catalogue | Family-first cards, server filters, exact variants, media gallery, specs, applications, stock and lead time |
| Dynamic specs | JSON specification map per product/category/workspace |
| Customer CRM | Customer list + customer relationship detail |
| Project hierarchy | Customer → Project → Building → Floor → Room |
| Contextual workspaces | Customer/project/building/room breadcrumbs, tabs, summaries and deep links |
| Building engineering | Main-board register, floor/room schedules and per-room product schedules |
| Room approvals | Exact family/variant preview with Yes approval or No rejection retained in the audit trail |
| Inquiry builder | Multi-floor/room structure, room product assignment, copy room, apply same room/all rooms |
| BOQ | Server-side aggregation from room source data + formatted building and room-breakdown XLSX sheets |
| Project documentation | A4 project/building books and room sheets with consistent headers, footers and role-aware pricing |
| Quotation | Generated from BOQ, backend tax/discount totals, status transitions, PDF |
| Orders | Accepted quotation conversion, reservation, fulfillment statuses, dispatch stock movement |
| Invoice | Order conversion, Tally-inspired India B2B layout, PDF/print view |
| Admin users | Create users, workspaces and permission codes |
| Auditability | Audit records for auth and critical mutations + Admin Audit Log screen |
| Deployment | Root multi-stage Docker image, PostgreSQL, Alembic, Compose, Render blueprint, CI workflow |

## Visual translation

The supplied mockups use a restrained navy/white/blue enterprise palette. The implementation preserves that visual language, including:

- Fixed navy left sidebar and Lighting/Automation selector.
- White cards on a cool gray background.
- Blue as the primary interactive accent.
- Green/amber/red only for semantic success/warning/error states.
- Dense B2B tables instead of consumer e-commerce cards for operational screens.
- Responsive fallbacks for common laptop, tablet and mobile widths.

## Deliberate production decisions

- No microservices in v1. This is a modular monolith with clear domain boundaries.
- Product media accepts only validated image formats and is served through authenticated routes; executable uploads are not accepted.
- No client-side-only authority for prices, tax, inventory or permissions.
- No direct Customer → Building model; projects remain the mandatory intermediate business layer.
- Demo data is blocked at production startup.
