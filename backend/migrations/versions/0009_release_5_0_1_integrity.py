"""release 5.0.1 catalogue, media and invitation integrity

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table)}


def _add(table: str, columns: list[sa.Column]) -> None:
    existing = _columns(table)
    for column in columns:
        if column.name not in existing:
            op.add_column(table, column)


def _checks(table: str) -> set[str]:
    return {row.get("name") for row in inspect(op.get_bind()).get_check_constraints(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if "invitation_activation_attempts" not in inspect(bind).get_table_names():
        op.create_table(
            "invitation_activation_attempts",
            sa.Column("token_hash", sa.String(64), primary_key=True),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
    _add("product_spec_definitions", [
        sa.Column("help_text", sa.String(500), nullable=True),
        sa.Column("allowed_units", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("default_value", sa.JSON(), nullable=True),
        sa.Column("min_value", sa.Numeric(18, 6), nullable=True),
        sa.Column("max_value", sa.Numeric(18, 6), nullable=True),
        sa.Column("precision", sa.Integer(), nullable=True),
        sa.Column("show_in_room_picker", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_in_exports", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("searchable", sa.Boolean(), nullable=False, server_default=sa.false()),
    ])
    _add("product_media", [
        sa.Column("last_error", sa.String(255), nullable=True),
        sa.Column("upload_attempts", sa.Integer(), nullable=False, server_default="0"),
    ])
    _add("customer_invitations", [
        sa.Column("building_id", sa.String(36), nullable=True),
    ])
    _add("project_users", [
        sa.Column("building_id", sa.String(36), nullable=True),
    ])

    constraints = [
        ("inquiries", "ck_inquiries_application"),
        ("products", "ck_products_application"),
        ("categories", "ck_categories_application"),
    ]
    for table, name in constraints:
        if name not in _checks(table):
            with op.batch_alter_table(table) as batch:
                batch.create_check_constraint(name, "workspace IN ('LIGHTING','AUTOMATION')")

    invitation_fks = {tuple(row.get("constrained_columns") or []) for row in inspect(bind).get_foreign_keys("customer_invitations")}
    if ("building_id",) not in invitation_fks:
        with op.batch_alter_table("customer_invitations") as batch:
            batch.create_foreign_key("fk_customer_invitations_building", "buildings", ["building_id"], ["id"], ondelete="CASCADE")
    membership_fks = {tuple(row.get("constrained_columns") or []) for row in inspect(bind).get_foreign_keys("project_users")}
    if ("building_id",) not in membership_fks:
        with op.batch_alter_table("project_users") as batch:
            batch.create_foreign_key("fk_project_users_building", "buildings", ["building_id"], ["id"], ondelete="CASCADE")

    # Ordinary UNIQUE constraints permit duplicate root categories because
    # NULL parent IDs compare as distinct. This expression index enforces the
    # actual case-insensitive application/parent/name invariant.
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_category_normalized_sibling ON categories (workspace, COALESCE(parent_id, ''), lower(name))")


def downgrade() -> None:
    # The revision is intentionally additive. Removing catalogue validation
    # columns would destroy administrator-defined metadata.
    pass
