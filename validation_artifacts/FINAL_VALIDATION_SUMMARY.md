# Final validation summary — Release 5.0.4

## Release status

All **277 executable application and packaging requirements** in the atomic matrix pass. Five external-environment gates remain BLOCKED: real Google Drive OAuth, real SMTP delivery, real Chromium viewport/every-button validation, Docker/Compose runtime, and PostgreSQL runtime migration. This is an application-complete release candidate, not an unconditional production-ready declaration until those five staging checks pass.

## Exact executed results

| Check | Result |
|---|---|
| Backend `pytest -q` | 31 passed, 0 failed, 4 warnings, 10.87s |
| Frontend Vitest | 54 passed, 0 failed, 5 files, 4.41s |
| Frontend production build | PASS; 2,282 modules transformed |
| npm production audit | PASS; 0 vulnerabilities |
| Python dependency check | PASS; no broken requirements |
| Python compilation | PASS |
| OpenAPI generation | PASS; 158 paths, 201 operations |
| Fresh SQLite migration | PASS; `0011 (head)`, 66 tables |
| Representative 5.0.3 upgrade | PASS; 12/12 products preserved, 12 approved, 24 baseline price-history rows |
| Clean extracted archive rerun | PASS; backend, frontend tests/build, migration, PDF parse, integrity, and hygiene rerun |

The four warnings are one Starlette `BlockingPortal` deprecation and three Pydantic Decimal serialization warnings in existing tests. They do not fail a workflow but should be removed during routine dependency maintenance.

## Project Book / Building Book / Room Sheet QA

- Sanitized dataset: Skyline Towers — Tower A.
- Real sanitized images: two different 1200×900 PNG product images, plus a second LED-panel image used to test primary switching.
- Pages rendered and visually inspected with Poppler: Project Book 23, Building Book 23, Room Sheet 3; **49 total**, all A4.
- Correct SKU-to-image mapping: PASS.
- Primary-image switching changes the generated Project Book and selects the new storage key: PASS.
- Proportional aspect ratio: PASS.
- Missing-image fallback for Track Light 20W: PASS.
- Room placement rows: 11 expected / 11 rendered.
- Ordered technical specifications: PASS.
- Quantity reconciliation: 92 room units / 92 aggregate BOQ / 92 product-sheet total.
- Clipping, overlap, distortion, blank-page, and unreadable-text review: PASS.

## External integrations and deployment gates

- Google Drive: local and mocked provider success/failure/quota/missing-file behavior passes; real OAuth upload/download BLOCKED because credentials are absent.
- SMTP: application logging/retry/failure handling is implemented and tested; real delivery BLOCKED because no SMTP server/credentials are present.
- Arcot: rights gate, approved-domain HTTPS allowlist, DNS/private-address/redirect defenses, link discovery, dry run, draft commit, provenance, idempotency, no invented price, and safe CSV report pass with mocked approved-domain content. No live assets were copied.
- Docker/Podman: BLOCKED; no executable is installed.
- PostgreSQL: BLOCKED; no server, client, socket, or credentials are available. Both fresh and representative-upgrade migrations pass on SQLite.
- Browser: BLOCKED; no Chromium/Chrome executable is installed and the remote browser cannot access the isolated loopback application. Automated focus/mobile/responsive tests pass.

## Packaging

The final ZIP excludes `.env`, runtime databases, caches, `node_modules`, frontend `dist`, temporary files, and test media. ZIP integrity, a separate clean extraction, migration, backend/frontend suites, production build, and packaged PDF parsing were rerun against the extracted release. ZIP size and SHA-256 are reported with the downloadable artifact because a ZIP cannot contain its own stable hash.
