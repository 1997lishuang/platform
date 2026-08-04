"""pricing task status

Revision ID: 20260721_0002
Revises: 20260721_0001
Create Date: 2026-07-21
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260721_0002"
down_revision = "20260721_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pricing_task",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_code", sa.String(length=64), nullable=False, server_default="default"),
        sa.Column("task_code", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("message", sa.String(length=512), nullable=True),
        sa.Column("workbook_name", sa.String(length=255), nullable=False),
        sa.Column("upload_path", sa.String(length=512), nullable=False),
        sa.Column("project_name", sa.String(length=255), nullable=True),
        sa.Column("region_code", sa.String(length=64), nullable=True),
        sa.Column("specialty", sa.String(length=64), nullable=True),
        sa.Column("cost_category", sa.String(length=64), nullable=True),
        sa.Column("rule_version", sa.String(length=64), nullable=True),
        sa.Column("mysql_run_code", sa.String(length=64), nullable=True),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("priced_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unpriced_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("excel_path", sa.String(length=512), nullable=True),
        sa.Column("missing_rules_path", sa.String(length=512), nullable=True),
        sa.Column("audit_path", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_code", "task_code", name="uk_pricing_task_code"),
    )
    op.create_index(
        "idx_pricing_task_status",
        "pricing_task",
        ["tenant_code", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_pricing_task_status", table_name="pricing_task")
    op.drop_table("pricing_task")

