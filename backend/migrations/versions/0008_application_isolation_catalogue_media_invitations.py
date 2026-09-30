"""application isolation, hierarchical catalogue, typed specs, media and invitations

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text
from app.db import Base
from app import models  # noqa: F401

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def add_missing(table: str, columns: list[sa.Column]) -> None:
    bind = op.get_bind(); existing = {x["name"] for x in inspect(bind).get_columns(table)}
    for column in columns:
        if column.name not in existing: op.add_column(table, column)


def upgrade() -> None:
    bind = op.get_bind()
    add_missing("categories", [sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"), sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0")])
    add_missing("products", [sa.Column("model_number", sa.String(100), nullable=True)])
    add_missing("inquiries", [sa.Column("linked_inquiry_id", sa.String(36), nullable=True)])
    add_missing("product_media", [
        sa.Column("workspace", sa.String(32), nullable=False, server_default="LIGHTING"),
        sa.Column("storage_provider", sa.String(32), nullable=False, server_default="local"),
        sa.Column("provider_file_id", sa.String(255), nullable=True), sa.Column("provider_parent_id", sa.String(255), nullable=True),
        sa.Column("original_filename", sa.String(255), nullable=True), sa.Column("stored_filename", sa.String(255), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True), sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("checksum_sha256", sa.String(64), nullable=True), sa.Column("upload_status", sa.String(32), nullable=False, server_default="READY"),
        sa.Column("uploaded_by", sa.String(36), nullable=True), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    ])
    add_missing("product_spec_definitions", [
        sa.Column("workspace", sa.String(32), nullable=False, server_default="LIGHTING"),
        sa.Column("product_family_id", sa.String(36), nullable=True),
        sa.Column("show_in_catalogue", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_in_project_book", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_in_quotation_pdf", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("show_in_customer_portal", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
    ])
    existing = set(inspect(bind).get_table_names())
    for name in ("product_spec_values", "customer_invitations", "migration_issues"):
        if name not in existing: Base.metadata.tables[name].create(bind=bind, checkfirst=True)

    # 0005 scoped keys only by category. Release 5 permits the same internal key
    # in separate product-family scopes while retaining an application-aware key.
    spec_uniques = {item.get("name") for item in inspect(bind).get_unique_constraints("product_spec_definitions")}
    if "uq_product_spec_category_key" in spec_uniques:
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("product_spec_definitions") as batch:
                batch.drop_constraint("uq_product_spec_category_key", type_="unique")
        else:
            op.drop_constraint("uq_product_spec_category_key", "product_spec_definitions", type_="unique")

    # Preserve the established workspace/application as the deterministic owner.
    bind.execute(text("UPDATE inquiries SET workspace = UPPER(workspace) WHERE workspace IS NOT NULL"))
    bind.execute(text("UPDATE product_media SET workspace = (SELECT workspace FROM products WHERE products.id = product_media.product_id) WHERE product_id IS NOT NULL"))
    bind.execute(text("UPDATE product_spec_definitions SET workspace = (SELECT workspace FROM categories WHERE categories.id = product_spec_definitions.category_id)"))
    # Mixed legacy inquiries are explicitly queued for administrator correction; no product is silently reassigned.
    rows = bind.execute(text("""
        SELECT rr.inquiry_id, COUNT(DISTINCT p.workspace) AS app_count
        FROM room_requirements rr JOIN products p ON p.id=rr.product_id
        GROUP BY rr.inquiry_id HAVING COUNT(DISTINCT p.workspace)>1
    """)).fetchall()
    for inquiry_id, _ in rows:
        bind.execute(text("""INSERT INTO migration_issues
          (id,migration_revision,entity_type,entity_id,issue_code,details,created_at)
          VALUES (:id,'0008','inquiry',:entity,'MIXED_APPLICATION_PRODUCTS',:details,CURRENT_TIMESTAMP)"""),
          {"id": __import__("uuid").uuid4().hex, "entity": inquiry_id, "details": '{"action":"split_into_linked_inquiries"}'})

    # Foreign keys are added explicitly on PostgreSQL; SQLite development relies on ORM-created fresh schemas.
    if bind.dialect.name == "postgresql":
        op.create_foreign_key("fk_inquiries_linked_inquiry", "inquiries", "inquiries", ["linked_inquiry_id"], ["id"], ondelete="SET NULL")
        op.create_foreign_key("fk_product_media_uploaded_by", "product_media", "users", ["uploaded_by"], ["id"], ondelete="SET NULL")
        op.create_foreign_key("fk_spec_definition_family", "product_spec_definitions", "product_families", ["product_family_id"], ["id"], ondelete="CASCADE")
        op.create_check_constraint("ck_inquiries_application", "inquiries", "workspace IN ('LIGHTING','AUTOMATION')")
        op.create_check_constraint("ck_products_application", "products", "workspace IN ('LIGHTING','AUTOMATION')")
        op.create_check_constraint("ck_categories_application", "categories", "workspace IN ('LIGHTING','AUTOMATION')")
        op.create_unique_constraint("uq_category_application_parent_name", "categories", ["workspace", "parent_id", "name"])
        op.create_unique_constraint("uq_product_media_provider_file", "product_media", ["storage_provider", "provider_file_id"])
        op.create_unique_constraint("uq_spec_definition_application_scope_key", "product_spec_definitions", ["workspace", "category_id", "product_family_id", "spec_key"])
    for table, name, columns in [
        ("categories", "ix_categories_application_parent", ["workspace", "parent_id"]),
        ("product_media", "ix_product_media_workspace_status", ["workspace", "upload_status"]),
        ("product_spec_definitions", "ix_spec_definitions_scope_order", ["workspace", "category_id", "product_family_id", "sort_order"]),
    ]:
        indexes = {x["name"] for x in inspect(bind).get_indexes(table)}
        if name not in indexes: op.create_index(name, table, columns)


def downgrade() -> None:
    # Additive release: downgrade removes only new leaf tables. Historical columns remain to avoid data loss.
    bind = op.get_bind()
    for name in ("migration_issues", "customer_invitations", "product_spec_values"):
        if name in inspect(bind).get_table_names(): Base.metadata.tables[name].drop(bind=bind, checkfirst=True)
