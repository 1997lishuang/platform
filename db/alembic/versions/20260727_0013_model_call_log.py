"""add model call log

Revision ID: 20260727_0013
Revises: 20260727_0012
Create Date: 2026-07-27
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260727_0013"
down_revision = "20260727_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_call_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("tenant_code", sa.String(length=64), nullable=False, comment="企业编码"),
        sa.Column("call_code", sa.String(length=64), nullable=False, comment="模型调用流水号"),
        sa.Column("provider", sa.String(length=64), nullable=False, comment="模型平台，如 doubao、closeai、local"),
        sa.Column("model", sa.String(length=128), nullable=False, comment="模型名称或模型ID"),
        sa.Column("scenario", sa.String(length=64), nullable=False, comment="调用场景，如单项询价、Excel批量询价、计价自动询价"),
        sa.Column("task_code", sa.String(length=64), nullable=True, comment="关联任务号"),
        sa.Column("item_name", sa.String(length=255), nullable=True, comment="本次询价对象或清单项名称"),
        sa.Column("status", sa.String(length=32), nullable=False, comment="调用状态：running、succeeded、failed"),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True, comment="输入Token数"),
        sa.Column("completion_tokens", sa.Integer(), nullable=True, comment="输出Token数"),
        sa.Column("total_tokens", sa.Integer(), nullable=True, comment="总Token数"),
        sa.Column("duration_ms", sa.Integer(), nullable=True, comment="调用耗时毫秒"),
        sa.Column("response_excerpt", sa.Text(), nullable=True, comment="模型响应摘要，便于排查但不保存密钥"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="失败原因"),
        sa.Column("created_by", sa.String(length=128), nullable=True, comment="触发用户"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False, comment="创建时间"),
        sa.Column("finished_at", sa.DateTime(), nullable=True, comment="完成时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_code", "call_code", name="uk_model_call_log_code"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        comment="第三方模型调用日志，记录询价接口实时状态、耗时和Token用量",
    )
    op.create_index("idx_model_call_log_status", "model_call_log", ["tenant_code", "status", "created_at"])
    op.create_index("idx_model_call_log_task", "model_call_log", ["tenant_code", "task_code", "created_at"])
    op.create_index("idx_model_call_log_provider", "model_call_log", ["tenant_code", "provider", "model", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_model_call_log_provider", table_name="model_call_log")
    op.drop_index("idx_model_call_log_task", table_name="model_call_log")
    op.drop_index("idx_model_call_log_status", table_name="model_call_log")
    op.drop_table("model_call_log")
