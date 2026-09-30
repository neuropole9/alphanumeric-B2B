"""normalized catalogue, building scope, boards, and room approvals

Revision ID: 0004
Revises: 0003
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in inspect(op.get_bind()).get_table_names()


def _columns(name: str) -> set[str]:
    return {c["name"] for c in inspect(op.get_bind()).get_columns(name)} if _has_table(name) else set()


def _indexes(name: str) -> set[str]:
    return {i["name"] for i in inspect(op.get_bind()).get_indexes(name)} if _has_table(name) else set()


def _add_column(table: str, column: sa.Column) -> None:
    if column.name not in _columns(table):
        with op.batch_alter_table(table) as batch:
            batch.add_column(column)


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", (value or "product").lower()).strip("-")
    return cleaned[:170] or "product"


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(timezone.utc)

    # Additive metadata for existing CRM/project/building records.
    _add_column("customers", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    _add_column("projects", sa.Column("owner_id", sa.String(36), nullable=True))
    _add_column("projects", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    for column in [
        sa.Column("code", sa.String(60), nullable=True),
        sa.Column("building_type", sa.String(80), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    ]:
        _add_column("buildings", column)

    if "updated_at" in _columns("customers"):
        bind.execute(text("UPDATE customers SET updated_at=COALESCE(updated_at, created_at, :now)"), {"now": now})
    if "updated_at" in _columns("projects"):
        bind.execute(text("UPDATE projects SET updated_at=COALESCE(updated_at, created_at, :now)"), {"now": now})
    if "created_at" in _columns("buildings"):
        bind.execute(text("UPDATE buildings SET created_at=COALESCE(created_at, :now), updated_at=COALESCE(updated_at, :now)"), {"now": now})

    # Product family is the published product; products remain compatible variant rows.
    if not _has_table("product_families"):
        op.create_table(
            "product_families",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("workspace", sa.String(32), nullable=False),
            sa.Column("category_id", sa.String(36), sa.ForeignKey("categories.id"), nullable=False),
            sa.Column("name", sa.String(180), nullable=False),
            sa.Column("slug", sa.String(200), nullable=False),
            sa.Column("brand", sa.String(100), nullable=False, server_default="AlphaNumeric"),
            sa.Column("short_description", sa.String(500), nullable=True),
            sa.Column("full_description", sa.Text(), nullable=True),
            sa.Column("features", sa.JSON(), nullable=False),
            sa.Column("applications", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("workspace", "slug", name="uq_product_families_workspace_slug"),
        )
        op.create_index("ix_product_families_workspace", "product_families", ["workspace"])
        op.create_index("ix_product_families_category_id", "product_families", ["category_id"])
        op.create_index("ix_product_families_name", "product_families", ["name"])
        op.create_index("ix_product_families_brand", "product_families", ["brand"])
        op.create_index("ix_product_families_status", "product_families", ["status"])
        op.create_index("ix_product_families_workspace_status", "product_families", ["workspace", "status"])

    for column in [
        sa.Column("family_id", sa.String(36), nullable=True),
        sa.Column("variant_name", sa.String(180), nullable=True),
        sa.Column("cost", sa.Numeric(14, 2), nullable=True),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("warranty", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    ]:
        _add_column("products", column)

    if "family_id" in _columns("products"):
        rows = bind.execute(text(
            "SELECT id, workspace, category_id, name, description, brand, family_id "
            "FROM products ORDER BY workspace, name, id"
        )).mappings().all()
        used: set[tuple[str, str]] = set()
        for row in rows:
            if row["family_id"]:
                continue
            base = _slug(row["name"])
            slug = base
            suffix = 2
            while (row["workspace"], slug) in used or bind.execute(
                text("SELECT 1 FROM product_families WHERE workspace=:w AND slug=:s"),
                {"w": row["workspace"], "s": slug},
            ).scalar():
                slug = f"{base[:160]}-{suffix}"
                suffix += 1
            used.add((row["workspace"], slug))
            family_id = str(uuid.uuid4())
            bind.execute(text("""
                INSERT INTO product_families
                    (id, workspace, category_id, name, slug, brand, short_description,
                     full_description, features, applications, status, created_at, updated_at)
                VALUES
                    (:id, :workspace, :category_id, :name, :slug, :brand, :short_description,
                     :full_description, :features, :applications, 'ACTIVE', :created_at, :updated_at)
            """), {
                "id": family_id,
                "workspace": row["workspace"],
                "category_id": row["category_id"],
                "name": row["name"],
                "slug": slug,
                "brand": row["brand"] or "AlphaNumeric",
                "short_description": row["description"],
                "full_description": row["description"],
                "features": "[]",
                "applications": "[]",
                "created_at": now,
                "updated_at": now,
            })
            bind.execute(text("""
                UPDATE products
                SET family_id=:family_id, variant_name=COALESCE(variant_name, name),
                    created_at=COALESCE(created_at, :now), updated_at=COALESCE(updated_at, :now)
                WHERE id=:id
            """), {"family_id": family_id, "id": row["id"], "now": now})

    if "family_id" in _columns("products") and "ix_products_family_id" not in _indexes("products"):
        op.create_index("ix_products_family_id", "products", ["family_id"])
        with op.batch_alter_table("products") as batch:
            batch.create_foreign_key("fk_products_family_id", "product_families", ["family_id"], ["id"], ondelete="SET NULL")

    if not _has_table("product_media"):
        op.create_table(
            "product_media",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("product_family_id", sa.String(36), sa.ForeignKey("product_families.id", ondelete="CASCADE"), nullable=True),
            sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=True),
            sa.Column("storage_key", sa.String(500), nullable=False, unique=True),
            sa.Column("media_type", sa.String(100), nullable=False),
            sa.Column("alt_text", sa.String(255), nullable=False),
            sa.Column("caption", sa.String(500), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("width", sa.Integer(), nullable=True),
            sa.Column("height", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        for name, columns in [
            ("ix_product_media_product_family_id", ["product_family_id"]),
            ("ix_product_media_product_id", ["product_id"]),
            ("ix_product_media_is_primary", ["is_primary"]),
            ("ix_product_media_family_sort", ["product_family_id", "sort_order"]),
            ("ix_product_media_variant_sort", ["product_id", "sort_order"]),
        ]:
            op.create_index(name, "product_media", columns)

    if not _has_table("main_boards"):
        op.create_table(
            "main_boards",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("building_id", sa.String(36), sa.ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False),
            sa.Column("floor_id", sa.String(36), sa.ForeignKey("floors.id", ondelete="CASCADE"), nullable=False),
            sa.Column("room_id", sa.String(36), sa.ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True),
            sa.Column("name", sa.String(140), nullable=False),
            sa.Column("code", sa.String(80), nullable=True),
            sa.Column("board_type", sa.String(100), nullable=False),
            sa.Column("system", sa.String(32), nullable=False, server_default="MIXED"),
            sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("quantity > 0", name="ck_main_boards_quantity_positive"),
        )
        for column in ["project_id", "building_id", "floor_id", "room_id", "system"]:
            op.create_index(f"ix_main_boards_{column}", "main_boards", [column])
        op.create_index("ix_main_boards_scope", "main_boards", ["project_id", "building_id", "floor_id", "room_id"])

    _add_column("inquiries", sa.Column("building_id", sa.String(36), nullable=True))
    _add_column("inquiries", sa.Column("is_project_wide", sa.Boolean(), nullable=False, server_default=sa.false()))
    if "building_id" in _columns("inquiries"):
        bind.execute(text("""
            UPDATE inquiries
            SET building_id=(
                SELECT MIN(buildings.id) FROM buildings
                WHERE buildings.project_id=inquiries.project_id
                HAVING COUNT(buildings.id)=1
            )
            WHERE building_id IS NULL
        """))
        if "ix_inquiries_building_id" not in _indexes("inquiries"):
            op.create_index("ix_inquiries_building_id", "inquiries", ["building_id"])
            with op.batch_alter_table("inquiries") as batch:
                batch.create_foreign_key("fk_inquiries_building_id", "buildings", ["building_id"], ["id"], ondelete="SET NULL")

    if not _has_table("room_products"):
        op.create_table(
            "room_products",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("building_id", sa.String(36), sa.ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False),
            sa.Column("floor_id", sa.String(36), sa.ForeignKey("floors.id", ondelete="CASCADE"), nullable=False),
            sa.Column("room_id", sa.String(36), sa.ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False),
            sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
            sa.Column("quantity", sa.Numeric(14, 2), nullable=False),
            sa.Column("unit", sa.String(30), nullable=False, server_default="Nos"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("approval_status", sa.String(32), nullable=False, server_default="ADDED"),
            sa.Column("source", sa.String(40), nullable=False, server_default="ADMIN_SELECTION"),
            sa.Column("linked_inquiry_id", sa.String(36), sa.ForeignKey("inquiries.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("updated_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("room_id", "product_id", name="uq_room_products_room_variant"),
            sa.CheckConstraint("quantity > 0", name="ck_room_products_quantity_positive"),
        )
        for column in ["project_id", "building_id", "floor_id", "room_id", "product_id", "approval_status", "source", "linked_inquiry_id"]:
            op.create_index(f"ix_room_products_{column}", "room_products", [column])
        op.create_index("ix_room_products_scope", "room_products", ["project_id", "building_id", "floor_id", "room_id"])

    if not _has_table("product_proposals"):
        op.create_table(
            "product_proposals",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("building_id", sa.String(36), sa.ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False),
            sa.Column("floor_id", sa.String(36), sa.ForeignKey("floors.id", ondelete="CASCADE"), nullable=False),
            sa.Column("room_id", sa.String(36), sa.ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False),
            sa.Column("product_family_id", sa.String(36), sa.ForeignKey("product_families.id", ondelete="SET NULL"), nullable=True),
            sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
            sa.Column("quantity", sa.Numeric(14, 2), nullable=False),
            sa.Column("unit", sa.String(30), nullable=False, server_default="Nos"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="PROPOSED"),
            sa.Column("proposed_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("proposed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("decided_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("linked_inquiry_id", sa.String(36), sa.ForeignKey("inquiries.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("quantity > 0", name="ck_product_proposals_quantity_positive"),
        )
        for column in ["customer_id", "project_id", "building_id", "floor_id", "room_id", "product_family_id", "product_id", "status", "linked_inquiry_id"]:
            op.create_index(f"ix_product_proposals_{column}", "product_proposals", [column])
        op.create_index("ix_product_proposals_scope_status", "product_proposals", ["project_id", "room_id", "status"])

    # Helpful lookup indexes added only if this is an upgraded legacy database.
    for table, name, columns in [
        ("projects", "ix_projects_owner_id", ["owner_id"]),
        ("buildings", "ix_buildings_status", ["status"]),
    ]:
        if _has_table(table) and name not in _indexes(table):
            op.create_index(name, table, columns)


def downgrade() -> None:
    # The normalized catalogue backfill is intentionally conservative. Downgrading
    # removes additive tables/columns but leaves the legacy products untouched.
    for table in ["product_proposals", "room_products", "main_boards", "product_media"]:
        if _has_table(table):
            op.drop_table(table)

    for table, names in [
        ("inquiries", ["is_project_wide", "building_id"]),
        ("products", ["updated_at", "created_at", "warranty", "lead_time_days", "cost", "variant_name", "family_id"]),
        ("buildings", ["updated_at", "created_at", "status", "address", "building_type", "code"]),
        ("projects", ["updated_at", "owner_id"]),
        ("customers", ["updated_at"]),
    ]:
        present = _columns(table)
        for name in names:
            if name in present:
                with op.batch_alter_table(table) as batch:
                    batch.drop_column(name)
                present.discard(name)

    if _has_table("product_families"):
        op.drop_table("product_families")
