"""Preserve immutable audit-export references when investigations are deleted."""
from alembic import op

revision = "k6e9f1b3c210"
down_revision = "j5d8c2a7f410"
branch_labels = None
depends_on = None


def upgrade() -> None:
    table = "procurement_reconciliation_audit_exports"
    if op.get_bind().dialect.name == "postgresql":
        op.drop_constraint(
            "procurement_reconciliation_audit_exports_exception_id_fkey",
            table,
            type_="foreignkey",
        )
        op.create_foreign_key(
            "fk_proc_recon_audit_export_exception",
            table,
            "procurement_reconciliation_exceptions",
            ["exception_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    else:
        naming = {
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        }
        with op.batch_alter_table(table, naming_convention=naming) as batch_op:
            batch_op.drop_constraint(
                "fk_procurement_reconciliation_audit_exports_exception_id_procurement_reconciliation_exceptions",
                type_="foreignkey",
            )
            batch_op.create_foreign_key(
                "fk_proc_recon_audit_export_exception",
                "procurement_reconciliation_exceptions",
                ["exception_id"],
                ["id"],
                ondelete="RESTRICT",
            )


def downgrade() -> None:
    table = "procurement_reconciliation_audit_exports"
    if op.get_bind().dialect.name == "postgresql":
        op.drop_constraint("fk_proc_recon_audit_export_exception", table, type_="foreignkey")
        op.create_foreign_key(
            "procurement_reconciliation_audit_exports_exception_id_fkey",
            table,
            "procurement_reconciliation_exceptions",
            ["exception_id"],
            ["id"],
            ondelete="SET NULL",
        )
    else:
        naming = {
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        }
        with op.batch_alter_table(table, naming_convention=naming) as batch_op:
            batch_op.drop_constraint("fk_proc_recon_audit_export_exception", type_="foreignkey")
            batch_op.create_foreign_key(
                "fk_procurement_reconciliation_audit_exports_exception_id_procurement_reconciliation_exceptions",
                "procurement_reconciliation_exceptions",
                ["exception_id"],
                ["id"],
                ondelete="SET NULL",
            )
