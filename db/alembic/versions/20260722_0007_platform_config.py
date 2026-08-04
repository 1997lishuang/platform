"""platform configuration

Revision ID: 20260722_0007
Revises: 20260722_0006
Create Date: 2026-07-22
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260722_0007"
down_revision = "20260722_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_config",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID。"),
        sa.Column("tenant_code", sa.String(length=64), nullable=False, server_default="default", comment="租户编码。"),
        sa.Column("provider", sa.String(length=64), nullable=False, comment="平台编码，如 doubao、closeai、local。"),
        sa.Column("display_name", sa.String(length=128), nullable=False, comment="平台显示名称。"),
        sa.Column("base_url", sa.String(length=512), nullable=False, comment="OpenAI兼容接口基础地址。"),
        sa.Column("model", sa.String(length=128), nullable=False, comment="默认调用模型名称。"),
        sa.Column("api_key", sa.String(length=1024), nullable=True, comment="平台API Key，查询接口不回显明文。"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="60", comment="接口调用超时时间，单位秒。"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1"), comment="是否启用。"),
        sa.Column("remark", sa.String(length=512), nullable=True, comment="配置备注。"),
        sa.Column("updated_by", sa.String(length=128), nullable=True, comment="最后更新人账号。"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间。"),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="最后更新时间。",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_code", "provider", name="uk_platform_config_provider"),
        comment="第三方平台配置表，维护市场询价模型渠道和本地大模型连接信息。",
    )
    op.create_index("idx_platform_config_active", "platform_config", ["tenant_code", "active", "provider"])


def downgrade() -> None:
    op.drop_index("idx_platform_config_active", table_name="platform_config")
    op.drop_table("platform_config")
