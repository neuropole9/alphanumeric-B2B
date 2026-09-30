# Upgrade to Release 5.0.4

Release 5.0.4 is an additive upgrade from 5.0.3. Do not drop the database or delete the PostgreSQL volume.

## Upgrade

1. Back up PostgreSQL and private media metadata.
2. Deploy the 5.0.4 source and dependencies.
3. Run `python -m alembic upgrade head` from `backend/`.
4. Confirm `python -m alembic current` returns `0011 (head)`.
5. Start the application and verify `/health/ready`.
6. Review imported product drafts and approve prices before quotation use.

Migration `0011` adds product identity/content fields, structured list fields, price tiers, price-history tables, and external-import provenance. Existing products are preserved. Existing base/cost values are backfilled as effective baseline history, and products without a price become `PRICE_REQUIRED`.

## Arcot importer

Configure `EXTERNAL_IMPORT_ALLOWED_DOMAINS`. The supplied default permits only `arcotindia.com` and `www.arcotindia.com`. Administrators must confirm reuse rights. Run a dry run before committing. Imported products are drafts and have no invented price.

## Rollback

The migration downgrade intentionally does not delete commercial history. Restore the pre-upgrade database backup if a full rollback is required.
