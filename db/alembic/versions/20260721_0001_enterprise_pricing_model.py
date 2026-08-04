"""enterprise pricing model

Revision ID: 20260721_0001
Revises:
Create Date: 2026-07-21
"""
from __future__ import annotations

from alembic import op

revision = "20260721_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    statements = split_sql_file("db/mysql/schema.sql")
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS pricing_result")
    op.execute("DROP TABLE IF EXISTS pricing_run")
    op.execute("DROP TABLE IF EXISTS material_price")
    op.execute("DROP TABLE IF EXISTS feature_dictionary")
    op.execute("DROP TABLE IF EXISTS price_rule_component")
    op.execute("DROP TABLE IF EXISTS price_rule_condition")
    op.execute("DROP TABLE IF EXISTS price_rule")


def split_sql_file(path: str) -> list[str]:
    text = open(path, encoding="utf-8").read()
    statements: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        if stripped.upper().startswith("CREATE DATABASE") or stripped.upper().startswith("USE "):
            continue
        current.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(current).rstrip(";"))
            current = []
    if current:
        statements.append("\n".join(current))
    return statements

