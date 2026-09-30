"""strengthen project/inquiry referential integrity

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in inspect(op.get_bind()).get_table_names()


def _index_names(table: str) -> set[str]:
    if not _has_table(table):
        return set()
    return {i["name"] for i in inspect(op.get_bind()).get_indexes(table)}


def _fk_columns(table: str) -> set[tuple[str, ...]]:
    if not _has_table(table):
        return set()
    return {tuple(fk.get("constrained_columns") or []) for fk in inspect(op.get_bind()).get_foreign_keys(table)}


def _unique_columns(table: str) -> set[tuple[str, ...]]:
    if not _has_table(table):
        return set()
    return {tuple(u.get("column_names") or []) for u in inspect(op.get_bind()).get_unique_constraints(table)}


def upgrade():
    bind = op.get_bind()

    # Existing installations may contain duplicate rows from the legacy editor.
    # Merge those rows before enforcing the database-level invariant.
    if _has_table("room_requirements"):
        duplicates = bind.execute(text("""
            SELECT inquiry_id, room_id, product_id, SUM(quantity) AS total_quantity
            FROM room_requirements
            GROUP BY inquiry_id, room_id, product_id
            HAVING COUNT(*) > 1
        """)).mappings().all()
        for row in duplicates:
            ids = bind.execute(text("""
                SELECT id FROM room_requirements
                WHERE inquiry_id=:inquiry_id AND room_id=:room_id AND product_id=:product_id
                ORDER BY id
            """), dict(row)).scalars().all()
            if not ids:
                continue
            bind.execute(text("UPDATE room_requirements SET quantity=:qty WHERE id=:id"),
                         {"qty": row["total_quantity"], "id": ids[0]})
            for duplicate_id in ids[1:]:
                bind.execute(text("DELETE FROM room_requirements WHERE id=:id"), {"id": duplicate_id})

        uq = ("inquiry_id", "room_id", "product_id")
        if uq not in _unique_columns("room_requirements"):
            with op.batch_alter_table("room_requirements") as batch:
                batch.create_unique_constraint("uq_requirement_inquiry_room_product", list(uq))

    # Add the two FKs to legacy databases. Fresh installs already get them from metadata.
    if _has_table("projects") and ("partner_id",) not in _fk_columns("projects"):
        with op.batch_alter_table("projects") as batch:
            batch.create_foreign_key("fk_projects_partner_id_partners", "partners", ["partner_id"], ["id"], ondelete="SET NULL")
    if _has_table("invoices") and ("project_id",) not in _fk_columns("invoices"):
        with op.batch_alter_table("invoices") as batch:
            batch.create_foreign_key("fk_invoices_project_id_projects", "projects", ["project_id"], ["id"], ondelete="SET NULL")

    for table, name, columns in [
        ("users", "ix_users_role", ["role"]),
        ("users", "ix_users_status", ["status"]),
        ("projects", "ix_projects_name", ["name"]),
        ("projects", "ix_projects_status", ["status"]),
        ("project_users", "ix_project_users_user_status", ["user_id", "status"]),
    ]:
        if _has_table(table) and name not in _index_names(table):
            op.create_index(name, table, columns)


def downgrade():
    for table, name in [
        ("project_users", "ix_project_users_user_status"),
        ("projects", "ix_projects_status"),
        ("projects", "ix_projects_name"),
        ("users", "ix_users_status"),
        ("users", "ix_users_role"),
    ]:
        if _has_table(table) and name in _index_names(table):
            op.drop_index(name, table_name=table)

    if _has_table("room_requirements") and ("inquiry_id", "room_id", "product_id") in _unique_columns("room_requirements"):
        with op.batch_alter_table("room_requirements") as batch:
            batch.drop_constraint("uq_requirement_inquiry_room_product", type_="unique")
    if _has_table("invoices") and ("project_id",) in _fk_columns("invoices"):
        with op.batch_alter_table("invoices") as batch:
            batch.drop_constraint("fk_invoices_project_id_projects", type_="foreignkey")
    if _has_table("projects") and ("partner_id",) in _fk_columns("projects"):
        with op.batch_alter_table("projects") as batch:
            batch.drop_constraint("fk_projects_partner_id_partners", type_="foreignkey")
