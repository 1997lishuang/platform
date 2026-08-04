"""link mapping reviews and market quotes to pricing tasks

Revision ID: 20260727_0012
Revises: 20260727_0011
Create Date: 2026-07-27
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260727_0012"
down_revision = "20260727_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "item_mapping_review",
        sa.Column("pricing_task_code", sa.String(length=64), nullable=True, comment="关联计价任务号，用于校准后自动续跑原任务"),
    )
    op.create_index(
        "idx_item_mapping_review_task",
        "item_mapping_review",
        ["tenant_code", "pricing_task_code", "status"],
    )
    op.add_column(
        "market_price_quote",
        sa.Column("pricing_task_code", sa.String(length=64), nullable=True, comment="关联计价任务号，用于询价复核后自动续跑原任务"),
    )
    op.create_index(
        "idx_market_quote_task",
        "market_price_quote",
        ["tenant_code", "pricing_task_code", "status"],
    )


def downgrade() -> None:
    op.drop_index("idx_market_quote_task", table_name="market_price_quote")
    op.drop_column("market_price_quote", "pricing_task_code")
    op.drop_index("idx_item_mapping_review_task", table_name="item_mapping_review")
    op.drop_column("item_mapping_review", "pricing_task_code")
