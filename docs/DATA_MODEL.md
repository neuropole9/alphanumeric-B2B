# Data model — Release 5.0.4

The operational hierarchy is `Customer → Project → Building → Floor → Room`. Commercial records remain project-scoped, while inquiries may target one building or the complete project.

## Catalogue and products

- `Category` is application-scoped, hierarchical, editable, ordered, and visibility/status controlled.
- `ProductFamily` owns family-facing name, brand, descriptions, features, applications, and family media.
- `Product` is the exact purchasable variant. It includes external/internal identity, SKU/model/barcode/HSN, complete descriptive content, structured highlights/features/applications, installation/care/warranty notes, search tags, six current price types, currency, MOQ, and pricing status.
- `ProductSpecValue` stores typed values against ordered specification definitions.
- `ProductMedia` belongs to a family or variant and retains stable order, primary state, alt text, caption, provider metadata, and readiness.
- `ProductPriceHistory` is the immutable, effective-dated record for COST, BASE, MRP, PROJECT, DEALER, and RESELLER values, including approval status/actor/note and tax-inclusive state.

## External catalogue provenance

- `ExternalCatalogueImport` records rights confirmation, approved source, dry-run/commit state, counts, report, actor, and timestamps.
- `ExternalProductSource` maps a canonical source URL/model/fingerprint to the local draft and stores the sanitized discovery snapshot. Repeated imports do not overwrite an approved product silently.

## Building engineering and access

- `MainBoard` belongs to a building.
- `RoomProduct` is the approved exact product variant and quantity for a room.
- `ProductProposal` records APPROVED or REJECTED decisions without duplicating the approved room schedule.
- Admins can operate across customers. Customer users receive access through active `ProjectUser` membership. Project, building, floor, room, inquiry, commercial, report, and media routes enforce that scope in the backend.

Schema changes are versioned through Alembic revision `0011_release_5_0_4_catalogue_completion.py`. The 5.0.3-to-5.0.4 upgrade preserves product rows and backfills current base/cost prices into history. Do not drop the database.
