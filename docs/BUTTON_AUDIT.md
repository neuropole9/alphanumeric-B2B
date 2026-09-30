# Button and action audit — Release 5.0.4

## Executed coverage

The backend route suite exercised authentication, password change, catalogue/category/family/product/specification/media operations, category reorder and cycle rejection, Arcot dry-run/commit/report, inquiries, BOQ, quotations, orders, invoices, documents, reports, Project/Building/Room PDFs, operations, pricing, invitations, and authorization failures. Result: **31 passed**.

The frontend suite exercised **54 realistic interaction tests across 5 files**, including character-by-character typing, focus retention, row add/delete/reorder, pricing, extended identity/content fields, descriptions, specifications, image metadata, category/family changes, paste/backspace/Tab, autosave protection, and mobile viewport behavior. The Vite production build also passed.

Static route/action reconciliation confirmed that the new controls are connected to protected APIs:

| Page/control | API/action | Result |
|---|---|---|
| Category edit | `PATCH /api/v1/catalogue/categories/{id}` | PASS |
| Category drag/keyboard reorder | `PUT /api/v1/catalogue/categories/reorder` | PASS |
| Product identity/content save | `PATCH /api/v1/product-variants/{id}` | PASS |
| Tier price schedule/history | `GET/POST /api/v1/product-variants/{id}/prices` | PASS |
| Arcot discovery/commit/report | `/api/v1/catalogue/arcot/imports...` | PASS with mocked approved-domain discovery |
| Project document archive | authenticated archive action | PASS |

## External browser gate

A real Chromium/Chrome executable is not installed and the available remote browser cannot reach the isolated loopback application. Therefore an every-button physical-browser inventory and real desktop/laptop/tablet/mobile viewport pass remain **BLOCKED**, not passed. Automated realistic-input and responsive tests passed, and no application control is knowingly unimplemented.
