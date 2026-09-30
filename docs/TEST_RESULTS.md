> **Archived Release 4 evidence:** historical only. Current schema head and validation are documented in `PRODUCTION_RELEASE_5.0.0.md`.

# Test Results — 2026-09-18

## Executed

| Check | Command / method | Result |
|---|---|---|
| Backend tests | `python -m pytest -q` | **PASS — 11 passed** |
| Python compile | `python -m compileall -q app migrations tests` | **PASS** |
| Alembic structural migration | Fresh temporary SQLite DB, `alembic upgrade head` | **PASS — 0001 → 0005 (head)** |
| Source/package presence | Required backend/frontend/migrations/tests/docs/Docker/Render files checked | **PASS** |
| Clean ZIP extraction | Extracted candidate archive, backend imports, 11 backend tests, compile and structural migration | **PASS** |
| Dummy-data source scan | Production runtime source/config scan | **PASS** |
| Secret source scan | Distributable source/config scan | **PASS** |

The Alembic structural check is not a substitute for the mandatory PostgreSQL gate; it only proves the migration chain is internally executable in the available environment.

## Blocked / not executed

| Check | Status | Reason |
|---|---|---|
| `npm ci` | **BLOCKED** | npm registry access times out / DNS requests fail (`EAI_AGAIN`) |
| Frontend unit tests | **NOT EXECUTED** | locked dependencies unavailable |
| TypeScript validation | **NOT EXECUTED** | locked dependencies unavailable |
| Vite production build | **NOT EXECUTED** | locked dependencies unavailable |
| Docker build/runtime | **BLOCKED** | `docker` executable unavailable |
| PostgreSQL fresh migration | **BLOCKED** | no PostgreSQL service/client; Docker unavailable |
| PostgreSQL supported-upgrade migration | **BLOCKED** | same blocker |
| Browser E2E | **NOT EXECUTED** | complete stack unavailable |
| Four desktop viewport matrix | **NOT EXECUTED** | complete stack unavailable |
| Runtime button audit | **NOT EXECUTED** | complete stack unavailable |
| Restart persistence | **NOT EXECUTED** | Docker/PostgreSQL unavailable |

No blocked or unexecuted result is represented as PASS.
