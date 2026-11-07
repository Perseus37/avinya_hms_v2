"""make federation transfer logs immutable

Revision ID: f9b7c3d1e205
Revises: e1a3c7b5d902
Create Date: 2026-11-03 09:30:00.000000

"""

from alembic import op


revision = "f9b7c3d1e205"
down_revision = "e1a3c7b5d902"
branch_labels = None
depends_on = None


_TRIGGER_FUNCTION = """
CREATE OR REPLACE FUNCTION prevent_federation_transfer_log_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'federation_transfer_logs are immutable';
END;
$$;
"""

_TRIGGER = """
CREATE TRIGGER trg_federation_transfer_logs_immutable
BEFORE UPDATE OR DELETE ON federation_transfer_logs
FOR EACH ROW
EXECUTE FUNCTION prevent_federation_transfer_log_mutation();
"""

_DROP_TRIGGER = """
DROP TRIGGER IF EXISTS trg_federation_transfer_logs_immutable
ON federation_transfer_logs;
DROP FUNCTION IF EXISTS prevent_federation_transfer_log_mutation();
"""


def upgrade() -> None:
    # The baseline used ON DELETE CASCADE, which could silently erase the audit
    # history when a patient was hard-deleted. Federation transfer history is an
    # audit record, so preserve it and make patient deletion fail instead.
    # Batch mode uses SQLite's copy-and-move strategy in parity tests and emits
    # native ALTER TABLE statements on PostgreSQL.
    with op.batch_alter_table("federation_transfer_logs") as batch_op:
        batch_op.drop_constraint(
            "federation_transfer_logs_patient_id_fkey",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "federation_transfer_logs_patient_id_fkey",
            "patients",
            ["patient_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    # The immutable-row trigger is PostgreSQL-specific (production database).
    if op.get_bind().dialect.name == "postgresql":
        op.execute(_TRIGGER_FUNCTION)
        op.execute(_TRIGGER)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(_DROP_TRIGGER)

    with op.batch_alter_table("federation_transfer_logs") as batch_op:
        batch_op.drop_constraint(
            "federation_transfer_logs_patient_id_fkey",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "federation_transfer_logs_patient_id_fkey",
            "patients",
            ["patient_id"],
            ["id"],
            ondelete="CASCADE",
        )
