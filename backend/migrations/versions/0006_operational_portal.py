"""operational portal modules, partner depth, dispatch, stock, RMA and activity

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Revision 0001 intentionally creates the current metadata for brand-new databases.
    # In that fresh-install path these tables already exist; this revision remains the
    # additive upgrade path for databases that reached the historical 0005 schema.
    if "stock_ledger" in set(inspect(op.get_bind()).get_table_names()):
        return
    partner_columns = {column["name"] for column in inspect(op.get_bind()).get_columns("partners")}
    for column in (
        sa.Column("partner_type", sa.String(40), nullable=False, server_default="OTHER"),
        sa.Column("legal_name", sa.String(180), nullable=True), sa.Column("tax_id", sa.String(40), nullable=True),
        sa.Column("billing_address", sa.Text(), nullable=True), sa.Column("shipping_address", sa.Text(), nullable=True),
        sa.Column("territory", sa.String(100), nullable=True), sa.Column("zone", sa.String(100), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("credit_terms_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("credit_limit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("sales_owner_id", sa.String(36), nullable=True), sa.Column("notes", sa.Text(), nullable=True),
    ):
        if column.name not in partner_columns:
            op.add_column("partners", column)
    if op.get_bind().dialect.name != "sqlite":
        op.create_unique_constraint("uq_partners_tax_id", "partners", ["tax_id"])
        op.create_foreign_key("fk_partners_sales_owner", "partners", "users", ["sales_owner_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_partners_partner_type", "partners", ["partner_type"])
    op.create_index("ix_partners_status", "partners", ["status"])
    user_columns = {column["name"] for column in inspect(op.get_bind()).get_columns("users")}
    if "partner_id" not in user_columns:
        op.add_column("users", sa.Column("partner_id", sa.String(36), nullable=True))
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key("fk_users_partner", "users", "partners", ["partner_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_users_partner_id", "users", ["partner_id"])

    op.create_table("inquiry_stage_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("inquiry_id", sa.String(36), sa.ForeignKey("inquiries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_stage", sa.String(40), nullable=True),
        sa.Column("to_stage", sa.String(40), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True), sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_inquiry_stage_history_inquiry_id", "inquiry_stage_history", ["inquiry_id"])
    op.create_index("ix_inquiry_stage_history_created_at", "inquiry_stage_history", ["created_at"])

    op.create_table("approval_requests",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("rule_code", sa.String(80), nullable=False), sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("requested_by", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("decided_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("comments", sa.Text(), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True))
    for col in ("entity_type", "entity_id", "project_id", "status"):
        op.create_index(f"ix_approval_requests_{col}", "approval_requests", [col])

    op.create_table("warehouses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("partner_id", sa.String(36), sa.ForeignKey("partners.id", ondelete="CASCADE"), nullable=True),
        sa.Column("code", sa.String(40), nullable=False), sa.Column("name", sa.String(140), nullable=False),
        sa.Column("address", sa.Text(), nullable=True), sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("allow_negative", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("partner_id", "code", name="uq_warehouses_partner_code"))
    op.create_index("ix_warehouses_partner_id", "warehouses", ["partner_id"])
    op.create_index("ix_warehouses_code", "warehouses", ["code"])

    op.create_table("stock_ledger",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("movement_type", sa.String(40), nullable=False), sa.Column("quantity", sa.Numeric(14, 2), nullable=False),
        sa.Column("direction", sa.String(3), nullable=False), sa.Column("reference_type", sa.String(40), nullable=True),
        sa.Column("reference_id", sa.String(36), nullable=True), sa.Column("idempotency_key", sa.String(120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_stock_ledger_quantity_positive"),
        sa.UniqueConstraint("idempotency_key", name="uq_stock_ledger_idempotency"))
    op.create_index("ix_stock_ledger_product_warehouse", "stock_ledger", ["product_id", "warehouse_id"])
    op.create_index("ix_stock_ledger_reference_id", "stock_ledger", ["reference_id"])

    op.create_table("dispatches",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("number", sa.String(40), nullable=False, unique=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("delivery_address", sa.Text(), nullable=False), sa.Column("transporter", sa.String(140), nullable=True),
        sa.Column("vehicle_number", sa.String(80), nullable=True), sa.Column("tracking_number", sa.String(120), nullable=True),
        sa.Column("expected_delivery", sa.Date(), nullable=True), sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True), sa.Column("receiver_name", sa.String(120), nullable=True),
        sa.Column("proof_notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_dispatches_order_id", "dispatches", ["order_id"])
    op.create_index("ix_dispatches_status", "dispatches", ["status"])
    op.create_table("dispatch_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dispatch_id", sa.String(36), sa.ForeignKey("dispatches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_item_id", sa.String(36), sa.ForeignKey("order_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 2), nullable=False),
        sa.UniqueConstraint("dispatch_id", "order_item_id", name="uq_dispatch_item_order_line"),
        sa.CheckConstraint("quantity > 0", name="ck_dispatch_items_quantity_positive"))
    op.create_index("ix_dispatch_items_dispatch_id", "dispatch_items", ["dispatch_id"])

    op.create_table("serial_units",
        sa.Column("serial_number", sa.String(120), primary_key=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("batch_number", sa.String(120), nullable=True),
        sa.Column("warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="IN_STOCK"),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("room_id", sa.String(36), sa.ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True),
        sa.Column("dispatch_id", sa.String(36), sa.ForeignKey("dispatches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("warranty_start", sa.Date(), nullable=True), sa.Column("warranty_end", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_serial_units_product_id", "serial_units", ["product_id"])
    op.create_index("ix_serial_units_batch_number", "serial_units", ["batch_number"])
    op.create_index("ix_serial_units_status", "serial_units", ["status"])

    op.create_table("rma_requests",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("number", sa.String(40), nullable=False, unique=True),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("serial_number", sa.String(120), sa.ForeignKey("serial_units.serial_number", ondelete="SET NULL"), nullable=True),
        sa.Column("quantity", sa.Numeric(14, 2), nullable=False), sa.Column("reason", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False), sa.Column("status", sa.String(32), nullable=False, server_default="REQUESTED"),
        sa.Column("resolution", sa.String(40), nullable=True),
        sa.Column("assigned_to", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("requested_by", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_rma_quantity_positive"))
    op.create_index("ix_rma_requests_project_id", "rma_requests", ["project_id"])
    op.create_index("ix_rma_requests_status", "rma_requests", ["status"])
    op.create_index("ix_rma_requests_serial_number", "rma_requests", ["serial_number"])
    op.create_table("rma_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("rma_id", sa.String(36), sa.ForeignKey("rma_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.String(32), nullable=True), sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_rma_history_rma_id", "rma_history", ["rma_id"])

    op.create_table("announcements",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("title", sa.String(180), nullable=False),
        sa.Column("content", sa.Text(), nullable=False), sa.Column("audience", sa.JSON(), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False, server_default="NORMAL"),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True), sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("link_url", sa.String(500), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_announcements_status", "announcements", ["status"])

    op.create_table("notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("notification_type", sa.String(50), nullable=False), sa.Column("title", sa.String(180), nullable=False),
        sa.Column("message", sa.Text(), nullable=False), sa.Column("deep_link", sa.String(500), nullable=True),
        sa.Column("dedupe_key", sa.String(160), nullable=False), sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "dedupe_key", name="uq_notification_user_dedupe"))
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])

    op.create_table("support_tickets",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("number", sa.String(40), nullable=False, unique=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("category", sa.String(80), nullable=False), sa.Column("subject", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False), sa.Column("priority", sa.String(20), nullable=False, server_default="NORMAL"),
        sa.Column("status", sa.String(32), nullable=False, server_default="OPEN"), sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("assigned_to", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_support_tickets_project_id", "support_tickets", ["project_id"])
    op.create_index("ix_support_tickets_status", "support_tickets", ["status"])

    op.create_table("resource_assets",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("title", sa.String(180), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False), sa.Column("workspace", sa.String(32), nullable=True),
        sa.Column("audience", sa.JSON(), nullable=False), sa.Column("url", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True), sa.Column("status", sa.String(20), nullable=False, server_default="PUBLISHED"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_resource_assets_resource_type", "resource_assets", ["resource_type"])
    op.create_index("ix_resource_assets_workspace", "resource_assets", ["workspace"])


def downgrade() -> None:
    for table in ("resource_assets", "support_tickets", "notifications", "announcements", "rma_history",
                  "rma_requests", "serial_units", "dispatch_items", "dispatches", "stock_ledger",
                  "warehouses", "approval_requests", "inquiry_stage_history"):
        op.drop_table(table)
    op.drop_index("ix_users_partner_id", table_name="users")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("fk_users_partner", type_="foreignkey")
        batch.drop_column("partner_id")
    for index_name in ("ix_partners_status", "ix_partners_partner_type"):
        op.drop_index(index_name, table_name="partners")
    with op.batch_alter_table("partners") as batch:
        batch.drop_constraint("fk_partners_sales_owner", type_="foreignkey")
        batch.drop_constraint("uq_partners_tax_id", type_="unique")
        for name in ("notes", "sales_owner_id", "credit_limit", "credit_terms_days", "status", "zone",
                     "territory", "shipping_address", "billing_address", "tax_id", "legal_name", "partner_type"):
            batch.drop_column(name)
