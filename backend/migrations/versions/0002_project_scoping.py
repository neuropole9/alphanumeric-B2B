"""project-scoped users, partners, inquiry drafts and ANIPL numbering

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def has_table(name: str) -> bool:
    return name in inspect(op.get_bind()).get_table_names()


def columns(name: str) -> set[str]:
    return {c["name"] for c in inspect(op.get_bind()).get_columns(name)} if has_table(name) else set()


def add_col(table: str, col: sa.Column):
    if col.name not in columns(table):
        with op.batch_alter_table(table) as batch:
            batch.add_column(col)


def upgrade():
    bind = op.get_bind()

    if not has_table("partners"):
        op.create_table(
            "partners",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("business_name", sa.String(180), nullable=False),
            sa.Column("mobile", sa.String(60), nullable=False),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("address", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_partners_business_name", "partners", ["business_name"])

    add_col("users", sa.Column("phone", sa.String(60), nullable=True))
    add_col("projects", sa.Column("partner_id", sa.String(36), nullable=True))
    add_col("projects", sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"))
    add_col("projects", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
    if "partner_id" in columns("projects"):
        idx = {x["name"] for x in inspect(bind).get_indexes("projects")}
        if "ix_projects_partner_id" not in idx:
            op.create_index("ix_projects_partner_id", "projects", ["partner_id"])

    add_col("rooms", sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))
    add_col("inquiries", sa.Column("workspace_scope", sa.JSON(), nullable=True))
    add_col("inquiries", sa.Column("wizard_step", sa.Integer(), nullable=False, server_default="1"))
    add_col("inquiries", sa.Column("source", sa.String(32), nullable=False, server_default="ADMIN"))
    add_col("inquiries", sa.Column("notes", sa.Text(), nullable=True))
    add_col("inquiries", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
    add_col("invoices", sa.Column("project_id", sa.String(36), nullable=True))
    if "project_id" in columns("invoices"):
        idx = {x["name"] for x in inspect(bind).get_indexes("invoices")}
        if "ix_invoices_project_id" not in idx:
            op.create_index("ix_invoices_project_id", "invoices", ["project_id"])
        bind.execute(text("UPDATE invoices SET project_id=(SELECT orders.project_id FROM orders WHERE orders.id=invoices.order_id) WHERE project_id IS NULL"))

    if not has_table("project_users"):
        op.create_table(
            "project_users",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("role", sa.String(32), nullable=False, server_default="PROJECT_USER"),
            sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.UniqueConstraint("project_id", "user_id", name="uq_project_users_project_user"),
        )
        op.create_index("ix_project_users_project_id", "project_users", ["project_id"])
        op.create_index("ix_project_users_user_id", "project_users", ["user_id"])
        op.create_index("ix_project_users_status", "project_users", ["status"])

    # Normalize new fields for existing rows.
    if "workspace_scope" in columns("inquiries"):
        # JSON literals are DB-dependent; SQLAlchemy will write these naturally on next edit.
        pass

    # Seed/repair the ANIPL sequence without count()+1 generation at request time.
    if has_table("document_sequences"):
        existing = bind.execute(text("SELECT next_value FROM document_sequences WHERE key='inquiry'")).scalar()
        if existing is None:
            bind.execute(text("INSERT INTO document_sequences (key,next_value) VALUES ('inquiry',1)"))
        # If ANIPL records already exist, advance beyond the highest suffix.
        numbers = bind.execute(text("SELECT number FROM inquiries WHERE number LIKE 'ANIPL%'" )).scalars().all()
        max_seen = 0
        for value in numbers:
            try:
                max_seen = max(max_seen, int(str(value)[5:]))
            except (ValueError, TypeError):
                continue
        current = bind.execute(text("SELECT next_value FROM document_sequences WHERE key='inquiry'" )).scalar() or 1
        if current <= max_seen:
            bind.execute(text("UPDATE document_sequences SET next_value=:n WHERE key='inquiry'"), {"n": max_seen + 1})


def downgrade():
    # Conservative downgrade: remove the new association table and additive columns.
    # Production data should be backed up before downgrading.
    if has_table("project_users"):
        op.drop_table("project_users")
    for table, cols in [
        ("invoices", ["project_id"]),
        ("inquiries", ["submitted_at", "notes", "source", "wizard_step", "workspace_scope"]),
        ("rooms", ["sort_order"]),
        ("projects", ["created_at", "status", "partner_id"]),
        ("users", ["phone"]),
    ]:
        present = columns(table)
        for col in cols:
            if col in present:
                with op.batch_alter_table(table) as batch:
                    batch.drop_column(col)
                present.discard(col)
    if has_table("partners"):
        op.drop_table("partners")
