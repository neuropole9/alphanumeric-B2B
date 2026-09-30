# Upgrade to Release 5.0.3

1. Back up PostgreSQL and private product media. Do not drop the database.
2. Unpack the release over a new application directory; preserve environment secrets and media storage.
3. Install dependencies with `pip install -r backend/requirements.txt` and `npm ci --prefix frontend`.
4. Run `cd backend && python -m scripts.release5_preflight`.
5. Run `cd backend && alembic upgrade head`. Revision `0010` is additive and preserves existing records.
6. Run backend and frontend tests, then `npm run build --prefix frontend`.
7. Configure production PostgreSQL, HTTPS cookies, company/legal/bank data, Google Drive OAuth and SMTP.
8. Build the container and deploy to staging. Run login, catalogue, inquiry, commercial PDF and Drive upload smoke tests through the public HTTPS URL.
9. Promote only after backup restoration, OAuth upload/download, email and reverse-proxy checks pass.

Rollback should use the previous application image with the same upgraded database: migration `0010` intentionally keeps additive columns/snapshots rather than destroying data in downgrade.
