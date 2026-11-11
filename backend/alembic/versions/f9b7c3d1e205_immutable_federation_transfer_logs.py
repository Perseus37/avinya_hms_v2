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


def _replace_patient_foreign_key(ondelete: str) -> None:
    dialect = op.get_bind().dialect.name

    # The original baseline declared this FK without an explicit name. PostgreSQL
    # assigned its standard *_fkey name, while SQLite reflects it as unnamed.
    # Give SQLite's reflected FK a deterministic name for Alembic batch mode.
    sqlite_naming = {
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
    }
    batch_kwargs = {"naming_convention": sqlite_naming} if dialect == "sqlite" else {}
    constraint_name = (
        "fk_federation_transfer_logs_patient_id_patients"
        if dialect == "sqlite"
        else "federation_transfer_logs_patient_id_fkey"
    )

    with op.batch_alter_table(
        "federation_transfer_logs",
        **batch_kwargs,
    ) as batch_op:
        batch_op.drop_constraint(constraint_name, type_="foreignkey")
        batch_op.create_foreign_key(
            "federation_transfer_logs_patient_id_fkey",
            "patients",
            ["patient_id"],
            ["id"],
            ondelete=ondelete,
        )


def upgrade() -> None:
    # The baseline used ON DELETE CASCADE, which could silently erase the audit
    # history when a patient was hard-deleted. Federation transfer history is an
    # audit record, so preserve it and make patient deletion fail instead.
    _replace_patient_foreign_key("RESTRICT")

    # The immutable-row trigger is PostgreSQL-specific (production database).
    if op.get_bind().dialect.name == "postgresql":
        op.execute(_TRIGGER_FUNCTION)
        op.execute(_TRIGGER)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(_DROP_TRIGGER)

    _replace_patient_foreign_key("CASCADE")
