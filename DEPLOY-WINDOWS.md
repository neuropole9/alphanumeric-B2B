# AlphaNumeric B2B — Windows Docker deployment

This package contains application source, migrations, assets, and `.env.example`. It does not contain your `.env`, database, uploaded media, or backups.

## New installation (PowerShell)

1. Extract the ZIP. Open PowerShell in the extracted `AlphaNumeric-B2B` directory (the one containing `docker-compose.yml`).
2. Create the configuration file: `Copy-Item .env.example .env`.
3. Edit `.env`: set a unique strong `POSTGRES_PASSWORD` and `SECRET_KEY`, a real `BOOTSTRAP_ADMIN_EMAIL` and strong `BOOTSTRAP_ADMIN_PASSWORD`, your legal company/GST/PAN/contact/bank fields, and your `PUBLIC_APP_URL`. For local HTTP only, set `COOKIE_SECURE=false` and `PUBLIC_APP_URL=http://localhost:8080`; for an HTTPS domain keep `COOKIE_SECURE=true` and configure `ALLOWED_ORIGINS` to its origin. The `.env` belongs beside `docker-compose.yml`.
4. Check your configuration: `docker compose --env-file .\.env config`.
5. Start: `docker compose --env-file .\.env up -d --build`. Open `http://localhost:8080/health`, then `http://localhost:8080`.
6. Inspect startup if needed: `docker compose --env-file .\.env logs --tail=100 app db`.

If PowerShell reports `couldn't find env file`, you are in the wrong directory or have not created `.env`. Check with `Get-Location` and `Test-Path .\.env`; Windows Explorer may hide a `.txt` suffix.

## Updating an existing installation

1. Back up the PostgreSQL database and uploaded media. Confirm the backup can be restored. Keep your existing `.env` and Docker named volumes; do not replace or delete them.
2. Extract this release into the directory containing your existing `docker-compose.yml`, overwriting application source only. This ZIP contains no `.env` or database files. If you previously customized source files, review those changes before replacing them.
3. Run `docker compose --env-file .\.env config`, then `docker compose --env-file .\.env up -d --build`.
4. Verify `docker compose --env-file .\.env ps`, `docker compose --env-file .\.env logs --tail=100 app db`, `/health`, a login, product variant editing, and representative project/book, quotation, and invoice PDF downloads. Startup runs `alembic upgrade head` automatically.

Never run `docker compose down -v` on a live installation: that deletes named database and media volumes. Never restore development SQLite files or the uploaded archive's backup dumps over your production data. A Docker Compose installation uses PostgreSQL; a separate SQLite deployment needs its own migration and backup plan.

## Package checks

The source matches the user-provided archive except for the retained PDF pagination regression assertion. No live production data or credentials are included. Docker is not installed in the packaging environment; container image build, production PostgreSQL migrations, and end-to-end behavior on your host require verification there. See `README.md` for full configuration details.

See `docs/RELEASE_5.0.11_DEPLOY_AND_VERIFY.md` for the exact source_url 422 and old-PDF verification steps.
