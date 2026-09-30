"""release 5.0.4 complete product content, price history and external imports

Revision ID: 0011
Revises: 0010
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from datetime import datetime, timezone
import uuid

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    existing = _columns("products")
    additions = [
        sa.Column("internal_name", sa.String(180), nullable=True),
        sa.Column("full_description", sa.Text(), nullable=True),
        sa.Column("manufacturer", sa.String(120), nullable=True),
        sa.Column("barcode", sa.String(100), nullable=True),
        sa.Column("search_tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("highlights", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("features", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("applications", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("installation_summary", sa.Text(), nullable=True),
        sa.Column("care_guide", sa.Text(), nullable=True),
        sa.Column("warranty_summary", sa.Text(), nullable=True),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        sa.Column("mrp_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("project_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("dealer_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("reseller_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("minimum_order_quantity", sa.Numeric(14, 2), nullable=False, server_default="1"),
        sa.Column("pricing_status", sa.String(32), nullable=False, server_default="DRAFT"),
    ]
    for column in additions:
        if column.name not in existing:
            op.add_column("products", column)
    op.execute("UPDATE products SET full_description = description WHERE full_description IS NULL")
    op.execute("UPDATE products SET manufacturer = brand WHERE manufacturer IS NULL")
    op.execute("UPDATE products SET pricing_status = CASE WHEN price > 0 THEN 'APPROVED' ELSE 'PRICE_REQUIRED' END")
    op.execute("CREATE INDEX IF NOT EXISTS ix_products_barcode ON products (barcode)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_products_pricing_status ON products (pricing_status)")

    # Revision 0001 intentionally builds current metadata for brand-new SQLite
    # development databases. In that path these additive tables already exist;
    # a true 5.0.3 -> 5.0.4 upgrade reaches here without them.
    present = set(inspect(op.get_bind()).get_table_names())
    new_tables = {"product_price_history", "external_catalogue_imports", "external_product_sources"}
    if new_tables.issubset(present):
        return

    op.create_table(
        "product_price_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("price_type", sa.String(24), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("tax_inclusive", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="APPROVED"),
        sa.Column("approval_note", sa.String(500), nullable=True),
        sa.Column("approved_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("price_type IN ('COST','BASE','MRP','PROJECT','DEALER','RESELLER')", name="ck_product_price_history_type"),
        sa.CheckConstraint("amount >= 0", name="ck_product_price_history_amount"),
    )
    op.create_index("ix_product_price_history_product_id", "product_price_history", ["product_id"])
    op.create_index("ix_product_price_history_price_type", "product_price_history", ["price_type"])
    op.create_index("ix_product_price_history_status", "product_price_history", ["status"])
    op.create_index("ix_product_price_history_product_effective", "product_price_history", ["product_id", "price_type", "effective_from"])
    bind = op.get_bind()
    price_rows = []
    mapping = {"cost": "COST", "price": "BASE", "mrp_price": "MRP", "project_price": "PROJECT", "dealer_price": "DEALER", "reseller_price": "RESELLER"}
    for product in bind.execute(sa.text("SELECT id, cost, price, mrp_price, project_price, dealer_price, reseller_price, currency, pricing_status FROM products")).mappings():
        for field, price_type in mapping.items():
            if product[field] is None: continue
            price_rows.append({"id": str(uuid.uuid4()), "product_id": product["id"], "price_type": price_type,
                "amount": product[field], "currency": product["currency"] or "INR", "tax_inclusive": False,
                "effective_from": datetime.now(timezone.utc), "effective_until": None,
                "status": "APPROVED" if product["pricing_status"] == "APPROVED" else "DRAFT",
                "approval_note": "Release 5.0.4 migration baseline", "approved_by": None, "created_by": None,
                "created_at": datetime.now(timezone.utc)})
    if price_rows:
        history = sa.table("product_price_history", *[sa.column(name) for name in price_rows[0]])
        bind.execute(history.insert(), price_rows)

    op.create_table(
        "external_catalogue_imports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace", sa.String(32), nullable=False, server_default="LIGHTING"),
        sa.Column("source_domain", sa.String(255), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("rights_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(32), nullable=False, server_default="DISCOVERED"),
        sa.Column("discovered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("workspace = 'LIGHTING'", name="ck_external_catalogue_import_lighting"),
    )
    op.create_index("ix_external_catalogue_imports_workspace", "external_catalogue_imports", ["workspace"])
    op.create_index("ix_external_catalogue_imports_status", "external_catalogue_imports", ["status"])
    op.create_index("ix_external_catalogue_import_source", "external_catalogue_imports", ["source_domain", "source_url"])

    op.create_table(
        "external_product_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace", sa.String(32), nullable=False, server_default="LIGHTING"),
        sa.Column("source_domain", sa.String(255), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("source_model", sa.String(180), nullable=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("last_import_id", sa.String(36), sa.ForeignKey("external_catalogue_imports.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace", "source_domain", "source_url", name="uq_external_product_source_url"),
    )
    op.create_index("ix_external_product_sources_workspace", "external_product_sources", ["workspace"])
    op.create_index("ix_external_product_sources_fingerprint", "external_product_sources", ["fingerprint"])
    op.create_index("ix_external_product_source_product", "external_product_sources", ["product_id"])


def downgrade() -> None:
    # Production data and price history are intentionally retained.
    pass
