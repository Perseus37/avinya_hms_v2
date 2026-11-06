"""Add private evidence attachments to reconciliation investigations."""
from alembic import op
import sqlalchemy as sa

revision = "g2a4d6e8f110"
down_revision = "f4c8a2d7e610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "procurement_reconciliation_evidence",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("exception_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(32), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("storage_key", sa.String(255), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(40), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256_hex", sa.String(64), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "evidence_type IN ('BANK_STATEMENT','PAYMENT_PROOF','INVOICE','SUPPLIER_CORRESPONDENCE','APPROVAL_RECORD','OTHER')",
            name="ck_proc_recon_evidence_type",
        ),
        sa.CheckConstraint("size_bytes > 0", name="ck_proc_recon_evidence_size"),
        sa.ForeignKeyConstraint(["exception_id"], ["procurement_reconciliation_exceptions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("storage_key", name="uq_proc_recon_evidence_storage_key"),
    )
    op.create_index(
        "ix_proc_recon_evidence_exception_time",
        "procurement_reconciliation_evidence",
        ["exception_id", "uploaded_at"],
    )
    op.create_table(
        "procurement_reconciliation_evidence_download_audits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("evidence_id", sa.Integer(), nullable=True),
        sa.Column("exception_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(32), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_email", sa.String(255), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["evidence_id"], ["procurement_reconciliation_evidence.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_proc_recon_evidence_download_time",
        "procurement_reconciliation_evidence_download_audits",
        ["exception_id", "requested_at"],
    )
    op.create_index(
        "ix_proc_recon_evidence_download_actor",
        "procurement_reconciliation_evidence_download_audits",
        ["actor_user_id", "requested_at"],
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("""
            CREATE FUNCTION prevent_proc_recon_evidence_download_audit_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'Reconciliation evidence download audit is append-only';
            END;
            $$ LANGUAGE plpgsql;
        """)
        op.execute("""
            CREATE TRIGGER trg_proc_recon_evidence_download_audit_append_only
            BEFORE UPDATE OR DELETE ON procurement_reconciliation_evidence_download_audits
            FOR EACH ROW EXECUTE FUNCTION prevent_proc_recon_evidence_download_audit_mutation();
        """)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_proc_recon_evidence_download_audit_append_only ON procurement_reconciliation_evidence_download_audits")
        op.execute("DROP FUNCTION IF EXISTS prevent_proc_recon_evidence_download_audit_mutation()")
    op.drop_index("ix_proc_recon_evidence_download_actor", table_name="procurement_reconciliation_evidence_download_audits")
    op.drop_index("ix_proc_recon_evidence_download_time", table_name="procurement_reconciliation_evidence_download_audits")
    op.drop_table("procurement_reconciliation_evidence_download_audits")
    op.drop_index("ix_proc_recon_evidence_exception_time", table_name="procurement_reconciliation_evidence")
    op.drop_table("procurement_reconciliation_evidence")
