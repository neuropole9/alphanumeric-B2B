# Release 5.0.6 validation and deployment notes

**Readiness:** application tests and sanitized rendering pass; production rollout remains subject to real target-environment UAT, database backup, and infrastructure validation. Do not treat the sample SQLite data as the production database.

## Audit and changes

The source archive identified as 5.0.5 contained distinct report renderers (`reports.py`, `pdf.py`, `advanced_services.py`, `release503_api.py`), an authenticated catalogue/media API, invitation validator, migration history through `0011`, and a React model detail form. The exact failing variant UUID was absent from its supplied local database and no failing browser request payload/response body was supplied. A representative edit with `cost: ""` produced HTTP 422 with `detail[0] = {loc: ["body", "cost"], msg: "Input should be a valid decimal", type: "decimal_parsing", input: ""}`. Configured dynamic spec definitions also reject unknown keys. The prior frontend submitted raw optional price inputs and unfiltered spec keys. It now sends optional empty numeric fields as null, validates required numbers, retains decimal text, filters configured spec keys, and shows the backend's field path and message inside the still-open edit dialog. The exact production 422 root cause cannot be established without the original sanitized request and response.

The invitation UI submitted `CUSTOMER_APPROVER`, rejected by the backend's `CUSTOMER`/`PROJECT_USER` restriction. It now submits the latter exactly, defaults to `CUSTOMER`, and the validator normalizes friendly values while rejecting privileged roles. The COB family previously used a large shared image, plain list and lexicographic model ordering. The new responsive grid naturally orders models and resolves the exact variant's authenticated primary image, using true family media only as a fallback. The bundled CA images are not bound by the SQL seed: after importing the seed, run `cd backend && python -m scripts.import_cob_variant_images --apply` with `MEDIA_STORAGE_PROVIDER=local` and `MEDIA_ROOT` configured. Review the dry run first. Existing media remains untouched. For Google Drive, upload through the authenticated API.

PDF changes use the same page frame and content edges; the aggregated BOQ contains Product Details, Model Number, Voltage, Quantity, Unit, Rate, Total. Model fallbacks are identified; voltage is resolved through normalized aliases. Compact technical cards render only the approved 21 fields, with alias mapping, exact primary media and flowing long values. Quotation and invoice remain distinct and retain their commercial content and authorized routes. No migration or pricing/permission rule was changed.

## Changed source files (complete code included in release archive)

- `CHANGELOG.md`; `docs/PRODUCTION_RELEASE_5.0.0.md`; this report.
- `backend/app/advanced_services.py`, `arcot_import.py`, `catalog_api.py`, `main.py`, `pdf.py`, `release503_api.py`, `release5_api.py`, `reports.py`.
- `backend/scripts/generate_release_validation.py`, `import_cob_variant_images.py`; `backend/tests/seed_fixture.py`, `test_pdf_documents.py`, `test_release506.py`, `test_workflow.py`. The fixture administrator email was changed so the archive contains no value matching a credential from the supplied environment.
- `frontend/package.json`, `package-lock.json`, `src/components/UI.tsx`, `src/features/inquiries/StepProjectClient.tsx`, `inquiryWizard.test.ts`, `inquiryWizard.types.ts`, `src/pages/ModelGallery.tsx`, `ModelGallery.test.tsx`, `ProductDetailPage.tsx`, `variantPayload.ts`, `variantPayload.test.ts`, `src/styles.css`.

## PDF visual QA

The sanitized fixture contains 4 distinct products, 19 room placements, quantity 119, two different image fixtures plus a missing image, decimal quantities, long identifiers and protocol values, and a discounted invoice. Primary-image switching changed the Project Book bytes; paths and exact image-to-product mapping were checked. Every page of these samples was rasterized and inspected in contact sheets. No clipped edges, double section frames, distorted images, overlapping text, or blank pages were seen; page 3 of the Project Book and Building Book is sparse because the register continues from page 2. Long protocol text flows to the next technical page. Two ordinary product cards fit together on page 26 of the Project Book and page 20 of the Building Book; the longer content is allowed more space. Quotation/invoice legal and commercial blocks remain legible.

| Document | Route | Pages | Visual result |
|---|---|---:|---|
| Project Book | `/api/v1/projects/{id}/book.pdf` | 28 | Pass; BOQ and financial summary page 25, cards pages 26–27 |
| Building Book | `/api/v1/projects/{id}/buildings/{id}/book.pdf` | 22 | Pass; BOQ page 19, cards pages 20–21 |
| Floor Sheet | `/api/v1/projects/{id}/buildings/{id}/floors/{id}/sheet.pdf` | 1 | Pass |
| Room Sheet | `/api/v1/projects/{id}/buildings/{id}/rooms/{id}/sheet.pdf` | 2 | Pass |
| Quotation | `/api/v1/quotations/{id}/pdf` | 3 | Pass; commercial page and specification pages |
| Invoice | `/api/v1/invoices/{id}/pdf` | 1 | Pass; tax invoice and amount in words |

The fixture asserts quantity reconciliation and primary image selection; backend PDF tests cover BOQ columns, technical field mapping and two typical products, content disposition parity, amount/rounding and GST branch behavior, document identity and access rules. It does not provide a fully populated real PostgreSQL dataset or a browser session against the target deployment.

## Validation commands

- `python -m compileall -q backend/app backend/migrations backend/tests`: passed.
- `pytest -q` (backend): 41 passed, 5 warnings (dependency deprecation/serializer warnings).
- `python -m pip check`: no broken requirements.
- `npm ci --prefix frontend`: passed.
- `npm test --prefix frontend`: 58 passed in 7 files.
- `npm run build --prefix frontend`: passed.
- `npm audit --omit=dev --prefix frontend`: 0 vulnerabilities.
- `alembic heads` and `current`: `0011 (head)` on the supplied SQLite database; a fresh separate SQLite database upgraded from base through `0011` successfully, with existing migration warnings about parsed SQLite foreign keys.
- OpenAPI generation: version 5.0.6, 158 paths, variant PATCH route present.
- Docker executable unavailable; Compose config, image build, container startup and PostgreSQL migration/health: **BLOCKED**. Live Google Drive and SMTP: **BLOCKED**. Live Chrome viewport/UAT and exact production PATCH request: **BLOCKED**.

The distributable excludes `.env`, databases, dumps, virtual environments, `node_modules`, caches, temporary media/PDF pages and prior validation outputs. A comparison against three credential candidates in the source environment found zero matches among the ZIP members. Its 187 unique members pass ZIP integrity checks. An independent extraction passes backend compilation and 41 backend tests; `npm ci` installs 145 packages, 58 frontend tests pass, and the production build succeeds. The exact byte size and digest are recorded in the accompanying delivery report.
