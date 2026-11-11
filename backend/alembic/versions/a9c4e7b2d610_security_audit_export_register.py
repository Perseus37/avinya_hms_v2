"""Create append-only security audit export accountability register."""

from alembic import op
import sqlalchemy as sa

revision = "a9c4e7b2d610"
down_revision = "f8d2b1c4e903"
branch_labels = None
depends_on = None

TABLE = "security_audit_export_register"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("exported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("category", sa.String(length=40), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=True),
        sa.Column("from_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("to_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("byte_count", sa.Integer(), nullable=False),
        sa.Column("criteria_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT",
                                name="fk_security_audit_export_actor"),
        sa.CheckConstraint("schema_version >= 1", name="ck_security_audit_export_schema_version"),
        sa.CheckConstraint("event_count >= 0", name="ck_security_audit_export_event_count"),
        sa.CheckConstraint("byte_count >= 0", name="ck_security_audit_export_byte_count"),
        sa.CheckConstraint("length(payload_sha256) = 64", name="ck_security_audit_export_sha256_length"),
    )
    op.create_index("ix_security_audit_export_exported_at", TABLE, ["exported_at"])
    op.create_index("ix_security_audit_export_actor", TABLE, ["actor_user_id"])

    if op.get_bind().dialect.name == "postgresql":
        op.execute("""
            CREATE OR REPLACE FUNCTION prevent_security_audit_export_register_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'security audit export register is append-only';
            END;
            $$ LANGUAGE plpgsql;
        """)
        op.execute("""
            CREATE TRIGGER trg_security_audit_export_no_mutation
            BEFORE UPDATE OR DELETE ON security_audit_export_register
            FOR EACH ROW EXECUTE FUNCTION prevent_security_audit_export_register_mutation();
        """)
    elif op.get_bind().dialect.name == "sqlite":
        op.execute("""
            CREATE TRIGGER trg_security_audit_export_no_update
            BEFORE UPDATE ON security_audit_export_register
            BEGIN SELECT RAISE(ABORT, 'security audit export register is append-only'); END;
        """)
        op.execute("""
            CREATE TRIGGER trg_security_audit_export_no_delete
            BEFORE DELETE ON security_audit_export_register
            BEGIN SELECT RAISE(ABORT, 'security audit export register is append-only'); END;
        """)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_security_audit_export_no_mutation ON security_audit_export_register")
        op.execute("DROP FUNCTION IF EXISTS prevent_security_audit_export_register_mutation()")
    elif op.get_bind().dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS trg_security_audit_export_no_update")
        op.execute("DROP TRIGGER IF EXISTS trg_security_audit_export_no_delete")
    op.drop_index("ix_security_audit_export_actor", table_name=TABLE)
    op.drop_index("ix_security_audit_export_exported_at", table_name=TABLE)
    op.drop_table(TABLE)
