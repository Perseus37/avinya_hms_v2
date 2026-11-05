"""Add supplier compliance evidence and expiry tracking."""
from alembic import op
import sqlalchemy as sa

revision = "b8e4c2d7a610"
down_revision = "d3f7a9c2e610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "procurement_supplier_compliance_documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("vendor_id", sa.Integer(), nullable=False),
        sa.Column("document_type", sa.String(40), nullable=False),
        sa.Column("document_number", sa.String(100), nullable=True),
        sa.Column("issuer", sa.String(160), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("storage_key", sa.String(255), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="PENDING_VERIFICATION"),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("verified_by_id", sa.Integer(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.CheckConstraint("status IN ('PENDING_VERIFICATION','VERIFIED','REJECTED')", name="ck_supplier_compliance_status"),
        sa.CheckConstraint("expiry_date IS NULL OR issue_date IS NULL OR expiry_date >= issue_date", name="ck_supplier_compliance_dates"),
        sa.ForeignKeyConstraint(["vendor_id"], ["procurement_vendors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["verified_by_id"], ["users.id"]),
        sa.UniqueConstraint("storage_key", name="uq_supplier_compliance_storage_key"),
    )
    op.create_index("ix_supplier_compliance_vendor_type", "procurement_supplier_compliance_documents", ["vendor_id", "document_type"])
    op.create_index("ix_supplier_compliance_expiry_status", "procurement_supplier_compliance_documents", ["status", "expiry_date"])
    op.create_table(
        "procurement_supplier_compliance_download_audits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("vendor_name", sa.String(150), nullable=False),
        sa.Column("document_type", sa.String(40), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_email", sa.String(255), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["procurement_supplier_compliance_documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_supplier_compliance_audit_doc_time", "procurement_supplier_compliance_download_audits", ["document_id", "requested_at"])
    op.create_index("ix_supplier_compliance_audit_actor_time", "procurement_supplier_compliance_download_audits", ["actor_user_id", "requested_at"])


def downgrade() -> None:
    op.drop_index("ix_supplier_compliance_audit_actor_time", table_name="procurement_supplier_compliance_download_audits")
    op.drop_index("ix_supplier_compliance_audit_doc_time", table_name="procurement_supplier_compliance_download_audits")
    op.drop_table("procurement_supplier_compliance_download_audits")
    op.drop_index("ix_supplier_compliance_expiry_status", table_name="procurement_supplier_compliance_documents")
    op.drop_index("ix_supplier_compliance_vendor_type", table_name="procurement_supplier_compliance_documents")
    op.drop_table("procurement_supplier_compliance_documents")
