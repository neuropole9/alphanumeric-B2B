# Test Results 5.0.0

Validated on 2026-09-19. These results distinguish executed checks from infrastructure that was unavailable in the build environment.

| Check | Result | Detail |
|---|---|---|
| Python compile | PASS | `python -m compileall -q backend/app backend/migrations backend/tests` |
| Backend tests | PASS | 24 passed, 0 failed, 3 warnings |
| Frontend clean install | PASS | `npm ci`, 117 packages installed |
| Frontend tests | PASS | 22 passed, 0 failed across 4 files |
| Frontend production build | PASS | TypeScript and Vite build, 2,281 modules transformed |
| Fresh Alembic migration | PASS | SQLite base → `0008 (head)` |
| Upgrade migration | PASS | Existing `0007` → `0008 (head)` on SQLite |
| OpenAPI generation | PASS | 150 paths, release version 5.0.0 |
| Health/liveness/readiness | PASS | `/health`, `/health/live`, `/health/ready` returned HTTP 200 |
| Python dependency consistency | PASS | `pip check`: no broken requirements |
| Production npm audit | PASS | 0 known production vulnerabilities |
| Deployment YAML parsing | PASS | `docker-compose.yml` and `render.yaml` |
| PostgreSQL migration | NOT EXECUTED | PostgreSQL client/server was not available in this environment |
| Docker image/Compose startup | NOT EXECUTED | Docker CLI/daemon was not available in this environment |
| Live Google Drive OAuth/API | NOT EXECUTED | No company OAuth credentials were supplied; provider behavior is isolated behind the storage abstraction |
| Interactive responsive browser pass | NOT EXECUTED | The remote browser cannot connect to the isolated local preview address (`ERR_BLOCKED_BY_CLIENT`) |

Warnings are upstream deprecation/Decimal-serialization warnings and do not represent test failures. Deployment gates that require external infrastructure must be run in the target CI/staging environment before production promotion.
