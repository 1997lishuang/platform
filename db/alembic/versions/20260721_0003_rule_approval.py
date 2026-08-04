"""rule approval workflow

Revision ID: 20260721_0003
Revises: 20260721_0002
Create Date: 2026-07-21
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260721_0003"
down_revision = "20260721_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("price_rule", sa.Column("created_by", sa.String(length=128), nullable=True))
    op.add_column("price_rule", sa.Column("submitted_by", sa.String(length=128), nullable=True))
    op.add_column("price_rule", sa.Column("reviewed_by", sa.String(length=128), nullable=True))
    op.add_column("price_rule", sa.Column("reviewed_at", sa.DateTime(), nullable=True))
    op.add_column("price_rule", sa.Column("review_comment", sa.String(length=512), nullable=True))
    op.create_table(
        "user_role",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_code", sa.String(length=64), nullable=False, server_default="default"),
        sa.Column("username", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_code", "username", name="uk_user_role_username"),
    )
    op.create_index("idx_user_role_role", "user_role", ["tenant_code", "role", "active"])
    op.execute(
        """
        INSERT INTO user_role (tenant_code, username, display_name, role, active)
        VALUES
          ('default', 'admin', '系统管理员', 'admin', 1),
          ('default', 'estimator', '造价员', 'estimator', 1),
          ('default', 'reviewer', '审核员', 'reviewer', 1)
        ON DUPLICATE KEY UPDATE role = VALUES(role), active = VALUES(active)
        """
    )


def downgrade() -> None:
    op.drop_index("idx_user_role_role", table_name="user_role")
    op.drop_table("user_role")
    op.drop_column("price_rule", "review_comment")
    op.drop_column("price_rule", "reviewed_at")
    op.drop_column("price_rule", "reviewed_by")
    op.drop_column("price_rule", "submitted_by")
    op.drop_column("price_rule", "created_by")

