"""release 5.0.3 catalogue management and immutable publication snapshots

Revision ID: 0010
Revises: 0009
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    existing = _columns("categories")
    additions = [
        sa.Column("slug", sa.String(160), nullable=True),
        sa.Column("short_description", sa.String(500), nullable=True),
        sa.Column("full_description", sa.Text(), nullable=True),
        sa.Column("image_alt_text", sa.String(255), nullable=True),
        sa.Column("catalogue_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("customer_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("search_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("page_title", sa.String(180), nullable=True),
        sa.Column("meta_description", sa.String(320), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    ]
    for column in additions:
        if column.name not in existing:
            op.add_column("categories", column)
    op.execute("UPDATE categories SET slug = lower(replace(trim(name), ' ', '-')) WHERE slug IS NULL")
    op.execute("UPDATE categories SET created_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_category_normalized_slug ON categories (workspace, COALESCE(parent_id, ''), lower(slug))")
    if "workspace" not in _columns("catalogue_import_jobs"):
        op.add_column("catalogue_import_jobs", sa.Column("workspace", sa.String(32), nullable=False, server_default="LIGHTING"))
        op.create_index("ix_catalogue_import_jobs_workspace", "catalogue_import_jobs", ["workspace"])
    if "catalogue_publications" not in inspect(op.get_bind()).get_table_names():
        op.create_table(
            "catalogue_publications",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("workspace", sa.String(32), nullable=False),
            sa.Column("name", sa.String(180), nullable=False),
            sa.Column("code", sa.String(80), nullable=False),
            sa.Column("version", sa.String(40), nullable=False),
            sa.Column("status", sa.String(24), nullable=False, server_default="DRAFT"),
            sa.Column("cover_title", sa.String(180), nullable=False),
            sa.Column("cover_subtitle", sa.String(300), nullable=True),
            sa.Column("introduction", sa.Text(), nullable=True),
            sa.Column("price_mode", sa.String(24), nullable=False, server_default="NONE"),
            sa.Column("settings", sa.JSON(), nullable=False),
            sa.Column("snapshot", sa.JSON(), nullable=False),
            sa.Column("effective_date", sa.Date(), nullable=True),
            sa.Column("expiry_date", sa.Date(), nullable=True),
            sa.Column("created_by", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint("workspace IN ('LIGHTING','AUTOMATION')", name="ck_catalogue_publication_application"),
            sa.UniqueConstraint("workspace", "code", "version", name="uq_catalogue_publication_version"),
        )
        op.create_index("ix_catalogue_publications_workspace", "catalogue_publications", ["workspace"])
        op.create_index("ix_catalogue_publications_status", "catalogue_publications", ["status"])


def downgrade() -> None:
    # Additive release migration: published snapshots and audit metadata are retained.
    pass
