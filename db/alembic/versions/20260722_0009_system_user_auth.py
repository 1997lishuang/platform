"""system user authentication

Revision ID: 20260722_0009
Revises: 20260722_0008
Create Date: 2026-07-22
"""

from __future__ import annotations

import hashlib
import secrets

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "20260722_0009"
down_revision = "20260722_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_user",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True, comment="主键ID。"),
        sa.Column("tenant_code", sa.String(length=64), nullable=False, server_default="default", comment="企业编码，用于多企业数据隔离。"),
        sa.Column("username", sa.String(length=128), nullable=False, comment="登录账号。"),
        sa.Column("display_name", sa.String(length=128), nullable=True, comment="用户显示名称。"),
        sa.Column("password_hash", sa.String(length=255), nullable=False, comment="PBKDF2-SHA256 密码哈希，不保存明文密码。"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true(), comment="是否启用，停用后不能登录。"),
        sa.Column("last_login_at", sa.DateTime(), nullable=True, comment="最后登录时间。"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False, comment="创建时间。"),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            onupdate=sa.func.current_timestamp(),
            nullable=False,
            comment="最后更新时间。",
        ),
        sa.UniqueConstraint("tenant_code", "username", name="uk_system_user_username"),
        comment="系统用户表，保存允许登录系统的账号和密码哈希，并通过 user_role 关联角色权限。",
    )
    op.create_index("idx_system_user_active", "system_user", ["tenant_code", "active", "username"])

    bind = op.get_bind()
    admin_hash = hash_password("admin123")
    bind.execute(
        text(
            """
            INSERT INTO system_user (tenant_code, username, display_name, password_hash, active)
            SELECT 'default', 'admin', '系统管理员', :password_hash, 1
            WHERE NOT EXISTS (
              SELECT 1 FROM system_user WHERE tenant_code = 'default' AND username = 'admin'
            )
            """
        ),
        {"password_hash": admin_hash},
    )
    bind.execute(
        text(
            """
            INSERT INTO user_role (tenant_code, username, display_name, role, active)
            SELECT 'default', 'admin', '系统管理员', 'admin', 1
            WHERE NOT EXISTS (
              SELECT 1 FROM user_role WHERE tenant_code = 'default' AND username = 'admin'
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_index("idx_system_user_active", table_name="system_user")
    op.drop_table("system_user")


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    iterations = 200_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"
