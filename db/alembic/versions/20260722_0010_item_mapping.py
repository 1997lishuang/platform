"""item mapping workflow

Revision ID: 20260722_0010
Revises: 20260722_0009
Create Date: 2026-07-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260722_0010"
down_revision = "20260722_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "item_mapping",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column("tenant_code", sa.String(length=64), nullable=False, server_default="default", comment="企业编码"),
        sa.Column("mapping_code", sa.String(length=128), nullable=False, comment="映射编码"),
        sa.Column("source_item_name", sa.String(length=255), nullable=False, comment="清单原始项目名称或名称关键词"),
        sa.Column("standard_item_name", sa.String(length=255), nullable=False, comment="标准计价对象名称"),
        sa.Column("match_keywords_json", sa.JSON(), nullable=False, comment="辅助匹配关键词"),
        sa.Column("unit", sa.String(length=32), nullable=True, comment="适用单位"),
        sa.Column("feature_conditions_json", sa.JSON(), nullable=False, comment="适用特征条件"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft", comment="状态 draft/reviewing/active/rejected"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100", comment="匹配优先级，数字越小越优先"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1"), comment="是否启用"),
        sa.Column("created_by", sa.String(length=128), nullable=True, comment="创建人"),
        sa.Column("submitted_by", sa.String(length=128), nullable=True, comment="提交人"),
        sa.Column("reviewed_by", sa.String(length=128), nullable=True, comment="审核人"),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True, comment="审核时间"),
        sa.Column("review_comment", sa.String(length=512), nullable=True, comment="审核意见"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_code", "mapping_code", name="uk_item_mapping_code"),
    )
    op.create_index("idx_item_mapping_lookup", "item_mapping", ["tenant_code", "status", "active", "source_item_name", "unit"])
    op.create_table(
        "item_mapping_review",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column("tenant_code", sa.String(length=64), nullable=False, server_default="default", comment="企业编码"),
        sa.Column("review_code", sa.String(length=64), nullable=False, comment="校准单号"),
        sa.Column("workbook_name", sa.String(length=255), nullable=True, comment="来源清单文件"),
        sa.Column("source_sheet", sa.String(length=255), nullable=True, comment="来源Sheet"),
        sa.Column("source_row_number", sa.Integer(), nullable=True, comment="来源行号"),
        sa.Column("source_item_name", sa.String(length=255), nullable=False, comment="清单原始项目名称"),
        sa.Column("unit", sa.String(length=32), nullable=True, comment="计量单位"),
        sa.Column("feature_json", sa.JSON(), nullable=False, comment="清单特征"),
        sa.Column("candidate_json", sa.JSON(), nullable=False, comment="候选标准计价对象"),
        sa.Column("selected_standard_item_name", sa.String(length=255), nullable=True, comment="人工选择的标准计价对象"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending", comment="状态 pending/resolved/rejected"),
        sa.Column("created_by", sa.String(length=128), nullable=True, comment="创建人"),
        sa.Column("reviewed_by", sa.String(length=128), nullable=True, comment="校准人"),
        sa.Column("review_comment", sa.String(length=512), nullable=True, comment="校准说明"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False, comment="创建时间"),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True, comment="校准时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_code", name="uk_item_mapping_review_code"),
    )
    op.create_index("idx_item_mapping_review_status", "item_mapping_review", ["tenant_code", "status", "created_at"])
    op.create_index("idx_item_mapping_review_item", "item_mapping_review", ["tenant_code", "source_item_name", "unit"])


def downgrade() -> None:
    op.drop_index("idx_item_mapping_review_item", table_name="item_mapping_review")
    op.drop_index("idx_item_mapping_review_status", table_name="item_mapping_review")
    op.drop_table("item_mapping_review")
    op.drop_index("idx_item_mapping_lookup", table_name="item_mapping")
    op.drop_table("item_mapping")
