"""release integrity, documents, approvals, permissions, and payments

Revision ID: 0005
Revises: 0004
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {c["name"] for c in inspect(op.get_bind()).get_columns(table)}


def _add(table: str, column: sa.Column) -> None:
    if column.name not in _columns(table):
        with op.batch_alter_table(table) as batch:
            batch.add_column(column)


def upgrade() -> None:
    bind = op.get_bind()
    _add("users", sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()))
    _add("project_users", sa.Column("permissions", sa.JSON(), nullable=False, server_default="[]"))
    for table in ("floors", "rooms"):
        _add(table, sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"))
        _add(table, sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
        _add(table, sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
        if f"ix_{table}_status" not in {x["name"] for x in inspect(bind).get_indexes(table)}:
            op.create_index(f"ix_{table}_status", table, ["status"])
    _add("main_boards", sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"))
    _add("main_boards", sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))
    _add("product_families", sa.Column("suitability_guidance", sa.Text(), nullable=True))

    for column in [
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("customer_comment", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_by_id", sa.String(36), nullable=True),
    ]:
        _add("product_proposals", column)
    bind.execute(text("UPDATE product_proposals SET status='PENDING_CUSTOMER' WHERE status='PROPOSED'"))
    bind.execute(text("UPDATE product_proposals SET status='APPROVED' WHERE status IN ('ADDED','CUSTOMER_APPROVED')"))
    bind.execute(text("UPDATE product_proposals SET status='REJECTED' WHERE status='CUSTOMER_REJECTED'"))
    with op.batch_alter_table("product_proposals") as batch:
        if "fk_product_proposals_superseded_by" not in {x["name"] for x in inspect(bind).get_foreign_keys("product_proposals") if x.get("name")}:
            batch.create_foreign_key("fk_product_proposals_superseded_by", "product_proposals", ["superseded_by_id"], ["id"], ondelete="SET NULL")

    for column in [
        sa.Column("building_id", sa.String(36), nullable=True),
        sa.Column("delivery_terms", sa.Text(), nullable=True),
        sa.Column("warranty_terms", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("supersedes_id", sa.String(36), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    ]:
        _add("quotations", column)
    for column in [
        sa.Column("building_id", sa.String(36), nullable=True),
        sa.Column("delivery_address", sa.Text(), nullable=True),
        sa.Column("dispatch_reference", sa.String(120), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
    ]:
        _add("orders", column)
    _add("invoices", sa.Column("building_id", sa.String(36), nullable=True))
    _add("invoices", sa.Column("place_of_supply", sa.String(120), nullable=True))
    bind.execute(text("UPDATE quotations SET building_id=(SELECT building_id FROM inquiries WHERE inquiries.id=quotations.inquiry_id) WHERE building_id IS NULL"))
    bind.execute(text("UPDATE orders SET building_id=(SELECT building_id FROM quotations WHERE quotations.id=orders.quotation_id) WHERE building_id IS NULL"))
    bind.execute(text("UPDATE invoices SET building_id=(SELECT building_id FROM orders WHERE orders.id=invoices.order_id) WHERE building_id IS NULL"))
    for table, constraint, local, remote, ondelete in [
        ("quotations", "fk_quotations_building", "building_id", "buildings", "SET NULL"),
        ("quotations", "fk_quotations_supersedes", "supersedes_id", "quotations", "SET NULL"),
        ("orders", "fk_orders_building", "building_id", "buildings", "SET NULL"),
        ("invoices", "fk_invoices_building", "building_id", "buildings", "SET NULL"),
    ]:
        existing_fks = {x["name"] for x in inspect(bind).get_foreign_keys(table) if x.get("name")}
        if constraint not in existing_fks:
            with op.batch_alter_table(table) as batch:
                batch.create_foreign_key(constraint, remote, [local], ["id"], ondelete=ondelete)
        index_name = f"ix_{table}_{local}"
        if index_name not in {x["name"] for x in inspect(bind).get_indexes(table)}:
            op.create_index(index_name, table, [local])

    tables = _tables()
    if "customer_contacts" not in tables:
        op.create_table(
            "customer_contacts",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("role", sa.String(100), nullable=True),
            sa.Column("email", sa.String(255), nullable=True),
            sa.Column("phone", sa.String(60), nullable=True),
            sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_customer_contacts_customer_id", "customer_contacts", ["customer_id"])
    if "project_stakeholders" not in tables:
        op.create_table(
            "project_stakeholders",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("stakeholder_type", sa.String(60), nullable=False),
            sa.Column("organization", sa.String(180), nullable=True),
            sa.Column("email", sa.String(255), nullable=True),
            sa.Column("phone", sa.String(60), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_project_stakeholders_project_id", "project_stakeholders", ["project_id"])
    if "project_documents" not in tables:
        op.create_table(
            "project_documents",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("building_id", sa.String(36), sa.ForeignKey("buildings.id", ondelete="CASCADE"), nullable=True),
            sa.Column("floor_id", sa.String(36), sa.ForeignKey("floors.id", ondelete="CASCADE"), nullable=True),
            sa.Column("room_id", sa.String(36), sa.ForeignKey("rooms.id", ondelete="CASCADE"), nullable=True),
            sa.Column("title", sa.String(180), nullable=False),
            sa.Column("document_type", sa.String(60), nullable=False),
            sa.Column("revision", sa.String(40), nullable=False, server_default="A"),
            sa.Column("storage_key", sa.String(500), nullable=False, unique=True),
            sa.Column("file_name", sa.String(255), nullable=False),
            sa.Column("mime_type", sa.String(120), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
            sa.Column("uploaded_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_project_documents_scope", "project_documents", ["project_id", "building_id", "floor_id", "room_id"])
        op.create_index("ix_project_documents_document_type", "project_documents", ["document_type"])
    if "product_spec_definitions" not in tables:
        op.create_table(
            "product_spec_definitions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("category_id", sa.String(36), sa.ForeignKey("categories.id", ondelete="CASCADE"), nullable=False),
            sa.Column("spec_key", sa.String(80), nullable=False),
            sa.Column("label", sa.String(120), nullable=False),
            sa.Column("data_type", sa.String(30), nullable=False, server_default="text"),
            sa.Column("unit", sa.String(40), nullable=True),
            sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("allowed_values", sa.JSON(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("category_id", "spec_key", name="uq_product_spec_category_key"),
        )
        op.create_index("ix_product_spec_definitions_category_id", "product_spec_definitions", ["category_id"])
    if "invoice_payments" not in tables:
        op.create_table(
            "invoice_payments",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("invoice_id", sa.String(36), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
            sa.Column("amount", sa.Numeric(14, 2), nullable=False),
            sa.Column("method", sa.String(60), nullable=False),
            sa.Column("reference", sa.String(120), nullable=True),
            sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("recorded_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.CheckConstraint("amount > 0", name="ck_invoice_payments_amount_positive"),
        )
        op.create_index("ix_invoice_payments_invoice_id", "invoice_payments", ["invoice_id"])
    if "report_snapshots" not in tables:
        op.create_table(
            "report_snapshots",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("building_id", sa.String(36), sa.ForeignKey("buildings.id", ondelete="SET NULL"), nullable=True),
            sa.Column("report_type", sa.String(60), nullable=False),
            sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("checksum_sha256", sa.String(64), nullable=False),
            sa.Column("storage_key", sa.String(500), nullable=True),
            sa.Column("parameters", sa.JSON(), nullable=False),
            sa.Column("generated_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_report_snapshots_project_id", "report_snapshots", ["project_id"])


def downgrade() -> None:
    for table in ["report_snapshots", "invoice_payments", "product_spec_definitions", "project_documents", "project_stakeholders", "customer_contacts"]:
        if table in _tables():
            op.drop_table(table)
    for table, names in [
        ("invoices", ["place_of_supply", "building_id"]),
        ("orders", ["dispatched_at", "dispatch_reference", "delivery_address", "building_id"]),
        ("quotations", ["accepted_at", "sent_at", "supersedes_id", "revision", "notes", "warranty_terms", "delivery_terms", "building_id"]),
        ("product_proposals", ["superseded_by_id", "withdrawn_at", "sent_at", "customer_comment", "recommendation"]),
        ("product_families", ["suitability_guidance"]),
        ("main_boards", ["sort_order", "status"]),
        ("rooms", ["updated_at", "created_at", "status"]),
        ("floors", ["updated_at", "created_at", "status"]),
        ("project_users", ["permissions"]),
        ("users", ["must_change_password"]),
    ]:
        present = _columns(table)
        for name in names:
            if name in present:
                with op.batch_alter_table(table) as batch:
                    batch.drop_column(name)
