"""financial, pricing, targets, import, RMA service and email workflows

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from app.db import Base
from app import models  # noqa: F401

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

NEW_TABLES = [
    "financial_documents", "financial_document_items", "pricing_rules", "sales_targets",
    "catalogue_import_jobs", "catalogue_import_rows", "rma_evidence", "rma_parts",
    "email_deliveries", "notification_preferences",
]


def upgrade() -> None:
    bind = op.get_bind()
    rma_columns = {column["name"] for column in inspect(bind).get_columns("rma_requests")}
    columns = [
        sa.Column("warranty_eligible", sa.Boolean(), nullable=True),
        sa.Column("warranty_reason", sa.Text(), nullable=True),
        sa.Column("inspection_notes", sa.Text(), nullable=True),
        sa.Column("diagnosis", sa.Text(), nullable=True),
        sa.Column("customer_notes", sa.Text(), nullable=True),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        sa.Column("labour_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pickup_reference", sa.String(120), nullable=True),
        sa.Column("return_dispatch_reference", sa.String(120), nullable=True),
    ]
    for column in columns:
        if column.name not in rma_columns:
            op.add_column("rma_requests", column)
    existing = set(inspect(bind).get_table_names())
    for table_name in NEW_TABLES:
        if table_name not in existing:
            Base.metadata.tables[table_name].create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    existing = set(inspect(bind).get_table_names())
    for table_name in reversed(NEW_TABLES):
        if table_name in existing:
            Base.metadata.tables[table_name].drop(bind=bind, checkfirst=True)
    rma_columns = {column["name"] for column in inspect(bind).get_columns("rma_requests")}
    for name in ("return_dispatch_reference", "pickup_reference", "sla_due_at", "labour_cost",
                 "internal_notes", "customer_notes", "diagnosis", "inspection_notes",
                 "warranty_reason", "warranty_eligible"):
        if name in rma_columns:
            with op.batch_alter_table("rma_requests") as batch:
                batch.drop_column(name)
