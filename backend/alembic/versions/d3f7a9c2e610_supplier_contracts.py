"""Add supplier contract lifecycle, negotiated rates and PO linkage."""
from alembic import op
import sqlalchemy as sa

revision = "d3f7a9c2e610"
down_revision = "a9c4e7d2f610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "procurement_supplier_contracts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("vendor_id", sa.Integer(), nullable=False),
        sa.Column("contract_number", sa.String(80), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=False),
        sa.Column("renewal_notice_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(24), nullable=False, server_default="DRAFT"),
        sa.Column("payment_terms", sa.String(255), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("document_file_url", sa.String(255), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_id", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terminated_by_id", sa.Integer(), nullable=True),
        sa.Column("terminated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("termination_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("valid_to >= valid_from", name="ck_proc_contract_valid_period"),
        sa.CheckConstraint("renewal_notice_days >= 0 AND renewal_notice_days <= 730", name="ck_proc_contract_notice_days"),
        sa.CheckConstraint("status IN ('DRAFT','PENDING_APPROVAL','ACTIVE','EXPIRED','TERMINATED')", name="ck_proc_contract_status"),
        sa.ForeignKeyConstraint(["vendor_id"], ["procurement_vendors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["terminated_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"]),
        sa.UniqueConstraint("vendor_id", "contract_number", name="uq_proc_contract_vendor_number"),
    )
    op.create_index("ix_proc_contract_vendor_status", "procurement_supplier_contracts", ["vendor_id", "status"])
    op.create_index("ix_proc_contract_validity", "procurement_supplier_contracts", ["status", "valid_to"])
    op.create_table(
        "procurement_supplier_contract_rates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("contract_id", sa.Integer(), nullable=False),
        sa.Column("scope_type", sa.String(16), nullable=False),
        sa.Column("medication_id", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(24), nullable=True),
        sa.Column("uom_code", sa.String(24), nullable=False),
        sa.Column("unit_price_paise", sa.Integer(), nullable=False),
        sa.Column("tax_percentage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("scope_type IN ('MEDICATION','CATEGORY')", name="ck_proc_contract_rate_scope"),
        sa.CheckConstraint("(scope_type = 'MEDICATION' AND medication_id IS NOT NULL AND category IS NULL) OR (scope_type = 'CATEGORY' AND medication_id IS NULL AND category IS NOT NULL)", name="ck_proc_contract_rate_scope_target"),
        sa.CheckConstraint("unit_price_paise >= 0", name="ck_proc_contract_rate_price_non_neg"),
        sa.CheckConstraint("tax_percentage >= 0 AND tax_percentage <= 100", name="ck_proc_contract_rate_tax_range"),
        sa.ForeignKeyConstraint(["contract_id"], ["procurement_supplier_contracts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["medication_id"], ["medication_master.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"]),
        sa.UniqueConstraint("contract_id", "scope_type", "medication_id", "category", "uom_code", name="uq_proc_contract_rate_scope_uom"),
    )
    op.create_index("ix_procurement_supplier_contract_rates_contract_id", "procurement_supplier_contract_rates", ["contract_id"])
    op.create_index("ix_proc_contract_rate_medication", "procurement_supplier_contract_rates", ["medication_id", "uom_code"])
    op.create_table(
        "procurement_supplier_contract_revisions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("contract_id", sa.Integer(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("prior_snapshot", sa.JSON(), nullable=False),
        sa.Column("proposed_snapshot", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="PENDING"),
        sa.Column("requested_by_id", sa.Integer(), nullable=False),
        sa.Column("reviewed_by_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('PENDING','APPROVED','REJECTED')", name="ck_proc_contract_revision_status"),
        sa.ForeignKeyConstraint(["contract_id"], ["procurement_supplier_contracts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"]),
        sa.UniqueConstraint("contract_id", "revision_number", name="uq_proc_contract_revision_number"),
    )
    op.create_index("ix_proc_contract_revision_status", "procurement_supplier_contract_revisions", ["contract_id", "status"])
    op.create_table(
        "procurement_contract_document_download_audits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("contract_id", sa.Integer(), nullable=True),
        sa.Column("contract_number", sa.String(80), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_email", sa.String(255), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["contract_id"], ["procurement_supplier_contracts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_proc_contract_doc_audit_contract_time", "procurement_contract_document_download_audits", ["contract_id", "requested_at"])
    op.create_index("ix_proc_contract_doc_audit_actor_time", "procurement_contract_document_download_audits", ["actor_user_id", "requested_at"])
    op.add_column("procurement_purchase_orders", sa.Column("contract_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_po_supplier_contract", "procurement_purchase_orders", "procurement_supplier_contracts", ["contract_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_procurement_purchase_orders_contract_id", "procurement_purchase_orders", ["contract_id"])


def downgrade() -> None:
    op.drop_index("ix_proc_contract_doc_audit_actor_time", table_name="procurement_contract_document_download_audits")
    op.drop_index("ix_proc_contract_doc_audit_contract_time", table_name="procurement_contract_document_download_audits")
    op.drop_table("procurement_contract_document_download_audits")
    op.drop_index("ix_procurement_purchase_orders_contract_id", table_name="procurement_purchase_orders")
    op.drop_constraint("fk_po_supplier_contract", "procurement_purchase_orders", type_="foreignkey")
    op.drop_column("procurement_purchase_orders", "contract_id")
    op.drop_index("ix_proc_contract_revision_status", table_name="procurement_supplier_contract_revisions")
    op.drop_table("procurement_supplier_contract_revisions")
    op.drop_index("ix_proc_contract_rate_medication", table_name="procurement_supplier_contract_rates")
    op.drop_index("ix_procurement_supplier_contract_rates_contract_id", table_name="procurement_supplier_contract_rates")
    op.drop_table("procurement_supplier_contract_rates")
    op.drop_index("ix_proc_contract_validity", table_name="procurement_supplier_contracts")
    op.drop_index("ix_proc_contract_vendor_status", table_name="procurement_supplier_contracts")
    op.drop_table("procurement_supplier_contracts")
