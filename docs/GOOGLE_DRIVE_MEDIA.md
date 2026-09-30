# Google Drive OAuth and Product Media

Use a dedicated company Google account. In Google Cloud Console, enable the Google Drive API, create an OAuth client, complete consent, and obtain a refresh token using the narrow `drive.file` scope. Create a private root folder named `AlphaNumeric Quotation`, record its folder ID, and configure the variables shown in `.env.example`. Never commit the client secret, refresh token, token cache or downloaded credential JSON.

The provider creates application and product folders but persists Drive IDs in PostgreSQL. It never enables “Anyone with the link.” Images are decoded as genuine JPEG, PNG or WebP on upload; SVG, HTML, executable, malformed and renamed files are rejected.

Migration:

```bash
cd backend
python scripts/migrate_local_media_to_drive.py
python scripts/reconcile_media.py
```

The migration is idempotent because rows with a provider file ID are skipped. Keep the local backup until reconciliation and PDF UAT pass. Quota failures leave the prior image intact and return a retryable error; monitor `/api/v1/media-storage/quota` as an administrator.
