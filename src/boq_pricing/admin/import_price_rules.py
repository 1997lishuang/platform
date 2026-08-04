from __future__ import annotations

import argparse

from boq_pricing.infrastructure import (
    DatabaseConfig,
    JsonPriceRuleRepository,
    MySqlCliClient,
    MySqlPriceRuleRepository,
    SqlAlchemyPriceRuleRepository,
    create_session_factory,
)


def main() -> int:
    args = parse_args()
    rules = JsonPriceRuleRepository().load(args.json)
    if args.db_backend == "sqlalchemy":
        session_factory = create_session_factory(build_database_config(args))
        count = SqlAlchemyPriceRuleRepository(
            session_factory,
            tenant_code=args.tenant_code,
        ).upsert_many(rules)
    else:
        client = MySqlCliClient(
            user=args.mysql_user,
            password=args.mysql_password,
            database=args.mysql_database,
            host=args.mysql_host,
            port=args.mysql_port,
            mysql_bin=args.mysql_bin,
        )
        count = MySqlPriceRuleRepository(client, tenant_code=args.tenant_code).upsert_many(rules)
    print(f"imported={count}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import JSON price rules into MySQL.")
    parser.add_argument("--json", required=True, help="JSON price rule file")
    parser.add_argument("--mysql-user", default="root")
    parser.add_argument("--mysql-password", help="Prefer BOQ_MYSQL_PASSWORD environment variable")
    parser.add_argument("--mysql-host", default="127.0.0.1")
    parser.add_argument("--mysql-port", type=int, default=3306)
    parser.add_argument("--mysql-database", default="boq_pricing")
    parser.add_argument("--mysql-bin", default="mysql")
    parser.add_argument("--tenant-code", default="default")
    parser.add_argument("--db-backend", choices=("sqlalchemy", "cli"), default="sqlalchemy")
    return parser.parse_args()


def build_database_config(args: argparse.Namespace) -> DatabaseConfig:
    import os

    return DatabaseConfig(
        user=args.mysql_user,
        password=args.mysql_password or os.getenv("BOQ_MYSQL_PASSWORD", ""),
        host=args.mysql_host,
        port=args.mysql_port,
        database=args.mysql_database,
    )


if __name__ == "__main__":
    raise SystemExit(main())
