"""market price quote source

Revision ID: 20260721_0005
Revises: 20260721_0004
Create Date: 2026-07-21
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260721_0005"
down_revision = "20260721_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_price_quote",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_code", sa.String(length=64), nullable=False, server_default="default"),
        sa.Column("quote_code", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("item_name", sa.String(length=255), nullable=False),
        sa.Column("feature_json", sa.JSON(), nullable=False),
        sa.Column("region_code", sa.String(length=64), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("price_min", sa.Numeric(18, 4), nullable=True),
        sa.Column("price_max", sa.Numeric(18, 4), nullable=True),
        sa.Column("recommended_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("tax_included", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("confidence", sa.Numeric(6, 4), nullable=False, server_default="0"),
        sa.Column("source_urls_json", sa.JSON(), nullable=False),
        sa.Column("assumptions_json", sa.JSON(), nullable=False),
        sa.Column("raw_response", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending_review"),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("reviewed_by", sa.String(length=128), nullable=True),
        sa.Column("review_comment", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_code", "quote_code", name="uk_market_quote_code"),
    )
    op.create_index("idx_market_quote_status", "market_price_quote", ["tenant_code", "status", "created_at"])
    op.create_index("idx_market_quote_item", "market_price_quote", ["tenant_code", "item_name", "region_code"])


def downgrade() -> None:
    op.drop_index("idx_market_quote_item", table_name="market_price_quote")
    op.drop_index("idx_market_quote_status", table_name="market_price_quote")
    op.drop_table("market_price_quote")

