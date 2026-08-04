"""platform config search mode

Revision ID: 20260722_0008
Revises: 20260722_0007
Create Date: 2026-07-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260722_0008"
down_revision = "20260722_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "platform_config",
        sa.Column(
            "endpoint_type",
            sa.String(length=32),
            nullable=False,
            server_default="chat_completions",
            comment="接口类型：chat_completions 普通对话接口，responses 支持工具调用的 Responses API。",
        ),
    )
    op.add_column(
        "platform_config",
        sa.Column(
            "enable_web_search",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="是否启用联网搜索增强，用于获取最新公开市场来源。",
        ),
    )
    op.add_column(
        "platform_config",
        sa.Column(
            "search_tool_type",
            sa.String(length=64),
            nullable=True,
            comment="联网搜索工具类型，如 web_search_preview 或平台兼容的 web_search。",
        ),
    )


def downgrade() -> None:
    op.drop_column("platform_config", "search_tool_type")
    op.drop_column("platform_config", "enable_web_search")
    op.drop_column("platform_config", "endpoint_type")
