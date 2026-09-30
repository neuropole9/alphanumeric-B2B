# Data Model 5.0.0

- `categories`: application-owned self-referencing hierarchy, status and ordering.
- `product_families` → `products`: main family to exact sellable variant/model.
- `product_spec_definitions`: application/category/family scope, type, unit, allowed values, ordering and visibility flags.
- `product_spec_values`: validated structured value per variant and definition.
- `product_media`: provider/file/folder IDs, checksum, dimensions, order, primary flag, lifecycle and audit metadata.
- `inquiries.workspace`: immutable LIGHTING or AUTOMATION owner. `linked_inquiry_id` connects the counterpart application inquiry.
- `customer_invitations`: SHA-256 token hash, expiry, consumption/revocation and application/project scope.
- `migration_issues`: unresolved legacy data requiring explicit administrator correction.

Historical inactive or archived catalogue records remain referenced by commercial documents; production workflows do not hard-delete them.
