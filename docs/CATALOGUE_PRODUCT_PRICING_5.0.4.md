# Catalogue, Product, and Pricing Administration

## Categories

Open `/app/{application}/catalogue/categories`. Administrators can create, edit, archive, restore, change parents, drag categories into display order, or use the keyboard Move up/down controls. The API rejects cross-application parents, duplicate normalized sibling names/slugs, and direct or indirect cycles.

## Products

Product families contain exact sellable variants. Each variant supports public/internal identity, model/SKU/barcode, descriptions, structured highlights/features/applications, installation and care guidance, warranty, protected internal notes, typed dynamic specifications, stock, multiple images, and exactly one primary image.

## Pricing

Base, MRP, project, dealer, reseller, and cost prices use fixed-precision database columns. Every change writes history. Scheduled approved periods cannot overlap. Cost, price tiers, and internal notes are administrator-only. Products with an unknown price remain `PRICE_REQUIRED` and cannot receive an invented imported price.

## External discovery/import

The Arcot workflow requires rights confirmation, validates HTTPS and approved domains on every redirect, rejects private/reserved DNS destinations, discovers product links without numeric assumptions, stores source provenance, produces field-level previews, remains idempotent, and provides a CSV report with formula-injection protection. Live assets are not hotlinked.
