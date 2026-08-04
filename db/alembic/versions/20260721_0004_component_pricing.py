"""component pricing and quota model

Revision ID: 20260721_0004
Revises: 20260721_0003
Create Date: 2026-07-21
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260721_0004"
down_revision = "20260721_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("price_rule_component", sa.Column("material_code", sa.String(length=128), nullable=True))
    op.add_column("price_rule_component", sa.Column("quota_code", sa.String(length=128), nullable=True))
    op.add_column(
        "price_rule_component",
        sa.Column("price_source_type", sa.String(length=32), nullable=False, server_default="manual"),
    )
    op.create_index("idx_component_material", "price_rule_component", ["material_code"])
    op.create_index("idx_component_quota", "price_rule_component", ["quota_code"])
    op.create_table(
        "quota_item",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_code", sa.String(length=64), nullable=False, server_default="default"),
        sa.Column("quota_code", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("quota_name", sa.String(length=255), nullable=False),
        sa.Column("specialty", sa.String(length=64), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("work_content", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_code", "quota_code", "version", name="uk_quota_item_code_version"),
    )
    op.create_index("idx_quota_item_lookup", "quota_item", ["tenant_code", "specialty", "quota_name"])
    op.create_table(
        "quota_consumption",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("quota_item_id", sa.BigInteger(), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_code", sa.String(length=128), nullable=True),
        sa.Column("resource_name", sa.String(length=255), nullable=False),
        sa.Column("material_code", sa.String(length=128), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("consumption", sa.Numeric(18, 6), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["quota_item_id"], ["quota_item.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_quota_consumption_quota", "quota_consumption", ["quota_item_id"])
    op.create_index("idx_quota_consumption_material", "quota_consumption", ["material_code"])


def downgrade() -> None:
    op.drop_index("idx_quota_consumption_material", table_name="quota_consumption")
    op.drop_index("idx_quota_consumption_quota", table_name="quota_consumption")
    op.drop_table("quota_consumption")
    op.drop_index("idx_quota_item_lookup", table_name="quota_item")
    op.drop_table("quota_item")
    op.drop_index("idx_component_quota", table_name="price_rule_component")
    op.drop_index("idx_component_material", table_name="price_rule_component")
    op.drop_column("price_rule_component", "price_source_type")
    op.drop_column("price_rule_component", "quota_code")
    op.drop_column("price_rule_component", "material_code")

