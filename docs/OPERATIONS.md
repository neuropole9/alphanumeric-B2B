# Production Operations

## Deploy/update

1. Back up PostgreSQL and the persistent media volume.
2. Build the image from the repository root.
3. Run `alembic upgrade head` as a one-off release task.
4. Start the new application image and check `/health`.
5. Run role-based smoke tests for admin and project-user accounts.
6. Retain the previous image tag until verification is complete.

Production startup fails closed when the secret, legal company identity, tax identity, bank configuration, or production configuration is unsafe.

## PostgreSQL backup and restore rehearsal

```bash
pg_dump --format=custom --file=alphanumeric-$(date +%F).dump "$DATABASE_URL"
createdb alphanumeric_restore_check
pg_restore --exit-on-error --no-owner --dbname=alphanumeric_restore_check alphanumeric-YYYY-MM-DD.dump
psql alphanumeric_restore_check -c 'select count(*) from projects;'
dropdb alphanumeric_restore_check
```

Back up the media volume at the same logical release point. Database rows and media objects form one recoverable unit.

## Rollback

Prefer restoring the pre-release database backup and previous image together. Alembic downgrade exists for development and controlled testing, but destructive schema rollback should not replace a verified backup restore.

## Required release checks

```bash
cd backend
python -m compileall -q app tests
python -m pytest -q
alembic upgrade head

cd ../frontend
npm ci
npm test -- --run
npm audit --omit=dev --audit-level=high
npm run build

docker compose build
docker compose up -d
curl --fail http://localhost:8080/health
```

Then execute browser E2E at desktop/tablet/mobile widths for login, inquiry wizard, product editing, proposal decision, request cart, document upload, exports, quotation/order/invoice paths, permission denial, and logout.
