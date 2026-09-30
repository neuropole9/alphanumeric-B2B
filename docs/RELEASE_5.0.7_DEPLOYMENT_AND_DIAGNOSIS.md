# Release 5.0.7: COB gallery and variant PATCH verification

The HTTP 422 status and variant UUID alone do not identify the rejected field. The supplied 5.0.5 database does not contain `a0f85592-fe6c-48e2-95ae-94291403b8bb`, and the browser's Network **Payload** and **Response** panels were not supplied. Do not attribute that specific request to a particular field without its `detail` response.

## Confirmed defects in the supplied source

- The older edit form submitted optional empty numeric inputs and all legacy `specs` keys. Pydantic rejects `cost: ""` with `loc: ["body","cost"]`, `type: "decimal_parsing"`, `msg: "Input should be a valid decimal"`. Version 5.0.6 normalized numeric fields and filtered configured specs. This revision additionally preserves only unchanged legacy specification values such as the seed's `source_url`, while still rejecting newly introduced or changed unknown keys. Archived definitions are ignored, matching the edit form's active-definition list.
- The previous family page placed a large image block before the COB models, and a viewport below 1500px switched the gallery to three columns. The model grid now appears first and uses four columns on wide laptop viewports, three below 1200px, two below 960px, and one below 600px. Selecting a card shows the exact variant below the grid.
- `Images/CA1.webp` through `CA10.webp` were absent from the production Compose image. This release copies those assets to `/app/Images`; the local-media importer finds them both in the container and source checkout. Bundled image files alone do not create product/media rows in PostgreSQL. The SQL seed is not run automatically because it updates existing catalogue fields.

## Verify the running Windows installation

1. Back up the existing PostgreSQL database and media volume with your established backup procedure. Keep the current Compose project directory and `.env`; replacing the directory name can attach different named volumes.
2. Overlay the extracted release **source files** into the existing project directory, excluding any local `.env` and runtime files. Rebuild/recreate the existing service from that directory: `docker compose --env-file .\.env up -d --build app`. Do not use `down -v`.
3. In PowerShell, run `(Invoke-RestMethod 'http://localhost:8080/api/openapi.json').info.version`. It must return `5.0.7`. Hard-refresh the browser to load the rebuilt frontend. If it still returns 5.0.5/5.0.6, the server is running old code, regardless of which ZIP was downloaded.
4. Run `docker compose --env-file .\.env exec app python -m scripts.check_cob_models`. It reports the exact CA1–CA10 variant status and whether each variant has a readable local primary image. If models are absent, review `seed_arcot_cob_ca1_ca10.sql` and the production catalogue before applying it: its `ON CONFLICT` statements update existing records. It is not a harmless read-only script.
5. For existing CA rows with missing media and `MEDIA_STORAGE_PROVIDER=local`, run `docker compose --env-file .\.env exec app python -m scripts.import_cob_variant_images` first, inspect the dry-run output, then run it again with `--apply` only after verifying the mappings. It does not overwrite existing variant media. With Google Drive, upload images through the authenticated product media API instead.
6. Retry the edit. For any 422, open DevTools → Network → the failed PATCH → **Response** and **Payload**. Copy `detail` (including `loc`, `msg`, `type`) and the submitted field value after removing personal data and credentials. That identifies the remaining specific validation rule. The edit dialog should also show the field message while retaining your entered values.

The family API should return the ten models in natural order and with distinct authenticated `primary_image_url` values. If it returns ten models but no image URLs, the problem is data/media registration; if it returns fewer than ten models, inspect seed state and active status; if the grid does not appear despite ten models and API version 5.0.7, the frontend build or browser cache is stale.

## Local verification

- Backend: 41 tests passed, including valid decimal/null PATCH, unchanged legacy spec acceptance, rejection of altered unknown specs, and exact CA1–CA10 image/order checks.
- Frontend: 58 tests passed; production build passed.
- Docker/PostgreSQL/your browser and the specific UUID request: blocked in this workspace. No production database, volume, or deployment was modified.
- No database migration was added; Alembic head remains `0011`.
