"""Add auditable vendor purchase returns and cumulative quantity controls."""

from alembic import op
import sqlalchemy as sa

revision = "d2b6e8f1a903"
down_revision = "c4d8e1a9b702"
branch_labels = None
depends_on = None

RETURN_TABLE = "procurement_purchase_returns"
ITEM_TABLE = "procurement_purchase_return_items"


def upgrade() -> None:
    op.create_table(
        RETURN_TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("grn_id", sa.Integer(), sa.ForeignKey("procurement_grn.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("vendor_id", sa.Integer(), sa.ForeignKey("procurement_vendors.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("total_credit_paise", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("total_credit_paise >= 0", name="ck_purchase_return_total_non_neg"),
    )
    op.create_index("ix_purchase_return_grn", RETURN_TABLE, ["grn_id"])
    op.create_index("ix_purchase_return_vendor", RETURN_TABLE, ["vendor_id"])

    op.create_table(
        ITEM_TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("return_id", sa.Integer(), sa.ForeignKey(f"{RETURN_TABLE}.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("grn_item_id", sa.Integer(), sa.ForeignKey("procurement_grn_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("inventory_batch_id", sa.Integer(), sa.ForeignKey("inventory_batches.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("return_quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_paise", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("amount_paise", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("return_reason", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("return_quantity > 0", name="ck_purchase_return_item_qty_pos"),
        sa.CheckConstraint("unit_price_paise >= 0", name="ck_purchase_return_item_price_non_neg"),
        sa.CheckConstraint("amount_paise >= 0", name="ck_purchase_return_item_amount_non_neg"),
    )
    op.create_index("ix_purchase_return_item_grn_item", ITEM_TABLE, ["grn_item_id"])
    op.create_index("ix_purchase_return_item_return", ITEM_TABLE, ["return_id"])
    op.create_index("ix_purchase_return_item_batch", ITEM_TABLE, ["inventory_batch_id"])

    if op.get_bind().dialect.name == "postgresql":
        op.execute("""
            CREATE OR REPLACE FUNCTION prevent_purchase_return_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'Purchase return audit records are immutable';
            END;
            $$ LANGUAGE plpgsql;
        """)
        for table in (RETURN_TABLE, ITEM_TABLE):
            op.execute(f"""
                CREATE TRIGGER trg_{table}_immutable
                BEFORE UPDATE OR DELETE ON {table}
                FOR EACH ROW EXECUTE FUNCTION prevent_purchase_return_mutation();
            """)
    elif op.get_bind().dialect.name == "sqlite":
        for table in (RETURN_TABLE, ITEM_TABLE):
            op.execute(f"""
                CREATE TRIGGER trg_{table}_immutable_update
                BEFORE UPDATE ON {table}
                BEGIN SELECT RAISE(ABORT, 'Purchase return audit records are immutable'); END;
            """)
            op.execute(f"""
                CREATE TRIGGER trg_{table}_immutable_delete
                BEFORE DELETE ON {table}
                BEGIN SELECT RAISE(ABORT, 'Purchase return audit records are immutable'); END;
            """)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table in (RETURN_TABLE, ITEM_TABLE):
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable ON {table}")
        op.execute("DROP FUNCTION IF EXISTS prevent_purchase_return_mutation()")
    elif op.get_bind().dialect.name == "sqlite":
        for table in (RETURN_TABLE, ITEM_TABLE):
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable_update")
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable_delete")
    op.drop_index("ix_purchase_return_item_batch", table_name=ITEM_TABLE)
    op.drop_index("ix_purchase_return_item_return", table_name=ITEM_TABLE)
    op.drop_index("ix_purchase_return_item_grn_item", table_name=ITEM_TABLE)
    op.drop_table(ITEM_TABLE)
    op.drop_index("ix_purchase_return_vendor", table_name=RETURN_TABLE)
    op.drop_index("ix_purchase_return_grn", table_name=RETURN_TABLE)
    op.drop_table(RETURN_TABLE)
