"""add updated time to pricing runs

Revision ID: 20260803_0014
Revises: 20260727_0013
Create Date: 2026-08-03
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260803_0014"
down_revision = "20260727_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pricing_run",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
            comment="更新时间，记录批次最近一次计价结果写入时间",
        ),
    )


def downgrade() -> None:
    op.drop_column("pricing_run", "updated_at")
