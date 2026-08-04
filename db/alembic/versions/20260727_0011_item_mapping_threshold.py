"""item mapping threshold setting

Revision ID: 20260727_0011
Revises: 20260722_0010
Create Date: 2026-07-27
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260727_0011"
down_revision = "20260722_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "item_mapping_setting",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column("tenant_code", sa.String(length=64), nullable=False, server_default="default", comment="企业编码"),
        sa.Column("confidence_threshold", sa.Numeric(6, 4), nullable=False, server_default="0.8500", comment="自动映射置信度阈值，低于该值进入人工校准"),
        sa.Column("updated_by", sa.String(length=128), nullable=True, comment="更新人"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_code", name="uk_item_mapping_setting_tenant"),
    )
    op.execute(
        """
        INSERT INTO item_mapping_setting (tenant_code, confidence_threshold)
        VALUES ('default', 0.8500)
        ON DUPLICATE KEY UPDATE confidence_threshold = confidence_threshold
        """
    )


def downgrade() -> None:
    op.drop_table("item_mapping_setting")
