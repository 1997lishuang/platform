from __future__ import annotations

import argparse

from sqlalchemy import text

from boq_pricing.config import load_settings
from boq_pricing.infrastructure.db import DatabaseConfig, create_session_factory


PRESERVED_TABLES = {"alembic_version", "platform_config", "user_role"}

RESET_TABLES = [
    "pricing_result",
    "pricing_run",
    "pricing_task",
    "market_price_quote",
    "price_rule_condition",
    "price_rule_component",
    "price_rule",
    "material_price",
    "quota_consumption",
    "quota_item",
    "feature_dictionary",
]


def table_counts(session, tables: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in tables:
        counts[table] = int(session.scalar(text(f"SELECT COUNT(*) FROM {table}")) or 0)
    return counts


def reset_database(dry_run: bool) -> None:
    settings = load_settings()
    session_factory = create_session_factory(DatabaseConfig.from_settings(settings))
    all_tables = ["platform_config", "user_role", *RESET_TABLES]
    with session_factory() as session:
        before = table_counts(session, all_tables)
        print("Before reset:")
        for table, count in before.items():
            print(f"  {table}: {count}")

        if dry_run:
            print("Dry run only. No data was changed.")
            return

        session.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for table in RESET_TABLES:
            session.execute(text(f"TRUNCATE TABLE {table}"))
        session.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        session.commit()

        after = table_counts(session, all_tables)
        print("After reset:")
        for table, count in after.items():
            marker = "preserved" if table in PRESERVED_TABLES else "reset"
            print(f"  {table}: {count} ({marker})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset business data for local feature testing.")
    parser.add_argument("--dry-run", action="store_true", help="Print table counts without truncating data.")
    args = parser.parse_args()
    reset_database(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
