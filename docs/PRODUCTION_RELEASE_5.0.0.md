# AlphaNumeric B2B 5.0.0

## Application model

Lighting and Automation are isolated application contexts under `/app/lighting` and `/app/automation`. Authentication, customers, projects and infrastructure are shared. Products, categories, specifications, inquiries, quotations, orders, dashboards, search, BOQs and books are application-scoped and backend-enforced. An inquiry cannot change application after creation and cannot accept a product from another application. Customers needing both receive two linked inquiries.

## Schema

Alembic head: `0008`. The migration is additive and retains IDs and historical commercial rows. Legacy mixed inquiries are written to `migration_issues` with `MIXED_APPLICATION_PRODUCTS` for administrator correction rather than being silently reassigned.

## Media

Release 5.0.10 defaults to persistent local storage (`MEDIA_STORAGE_PROVIDER=local`) in both development and production. Google Drive remains an optional, explicitly configured provider. Regardless of provider, files are streamed only through authenticated application-aware endpoints.

## Deployment checklist

1. Back up PostgreSQL and the existing media directory.
2. Configure all required production/company variables. Configure Google Drive OAuth values only when deliberately selecting the optional `google_drive` provider.
3. Run `alembic upgrade head` before starting application workers.
4. If deliberately migrating to Google Drive, run `python backend/scripts/migrate_local_media_to_drive.py` once for legacy media.
5. Run `python backend/scripts/reconcile_media.py` when using Google Drive; investigate every missing item.
6. Execute the commands in `TEST_RESULTS_5.0.0.md` and complete real-browser UAT.
7. Review `migration_issues` and split each mixed legacy inquiry into linked Lighting and Automation inquiries.

Google Account storage is shared by Drive, Gmail and Google Photos. It is not Google Cloud Storage, and the nominal personal allowance is not guaranteed to be fully available to this application.
