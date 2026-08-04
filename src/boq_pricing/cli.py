from __future__ import annotations

import argparse
from pathlib import Path

from boq_pricing.application.batch import PricingBatchRequest, PricingBatchService
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
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    mysql_client = build_mysql_client(args)
    session_factory = None
    if args.db_backend == "sqlalchemy":
        session_factory = create_session_factory(build_database_config(args))
    if args.rule_source == "json":
        if not args.rules:
            raise SystemExit("--rules is required when --rule-source json")
        rules = JsonPriceRuleRepository().load(Path(args.rules))
    else:
        if args.db_backend == "sqlalchemy":
            rules = SqlAlchemyPriceRuleRepository(
                session_factory,
                tenant_code=args.tenant_code,
            ).load(
                version=args.rule_version,
                region_code=args.region_code,
                specialty=args.specialty,
                cost_category=args.cost_category,
            )
        else:
            rules = MySqlPriceRuleRepository(mysql_client, tenant_code=args.tenant_code).load(
                version=args.rule_version,
                region_code=args.region_code,
                specialty=args.specialty,
                cost_category=args.cost_category,
            )
        if not rules:
            raise SystemExit("No active MySQL price rules were found.")

    response = PricingBatchService().run(
        PricingBatchRequest(
            input_path=input_path,
            output_dir=output_dir,
            rules=rules,
            rule_source=args.rule_source,
            tenant_code=args.tenant_code,
            project_name=args.project_name,
            region_code=args.region_code,
            write_mysql_audit=args.write_mysql_audit,
            mysql_client=mysql_client,
            session_factory=session_factory,
        )
    )
    print(f"items={response.item_count}")
    print(f"priced={response.priced_count}")
    print(f"unpriced={response.unpriced_count}")
    print(f"issues={response.issue_counts}")
    print(f"excel={response.excel_path}")
    print(f"missing_rules={response.missing_rules_path}")
    print(f"audit={response.audit_path}")
    if response.mysql_run_code:
        print(f"mysql_run_code={response.mysql_run_code}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read BOQ workbook and calculate prices.")
    parser.add_argument("--input", required=True, help="Input BOQ workbook path")
    parser.add_argument("--rule-source", choices=("json", "mysql"), default="json")
    parser.add_argument("--db-backend", choices=("sqlalchemy", "cli"), default="sqlalchemy")
    parser.add_argument("--rules", help="JSON price rule file")
    parser.add_argument("--rule-version", help="Only load rules for this version")
    parser.add_argument("--tenant-code", default="default", help="Enterprise tenant or company code")
    parser.add_argument("--project-name", help="Project name for audit records")
    parser.add_argument("--region-code", help="Region scope, for example AH-LA")
    parser.add_argument("--specialty", help="Specialty scope, for example building or installation")
    parser.add_argument("--cost-category", help="Cost category scope")
    parser.add_argument("--output-dir", default="outputs", help="Output directory")
    parser.add_argument("--write-mysql-audit", action="store_true", help="Persist pricing run to MySQL")
    parser.add_argument("--mysql-user", default="root")
    parser.add_argument("--mysql-password", help="Prefer BOQ_MYSQL_PASSWORD environment variable")
    parser.add_argument("--mysql-host", default="127.0.0.1")
    parser.add_argument("--mysql-port", type=int, default=3306)
    parser.add_argument("--mysql-database", default="boq_pricing")
    parser.add_argument("--mysql-bin", default="mysql")
    return parser.parse_args()


def build_mysql_client(args: argparse.Namespace) -> MySqlCliClient:
    return MySqlCliClient(
        user=args.mysql_user,
        password=args.mysql_password,
        database=args.mysql_database,
        host=args.mysql_host,
        port=args.mysql_port,
        mysql_bin=args.mysql_bin,
    )


def build_database_config(args: argparse.Namespace) -> DatabaseConfig:
    return DatabaseConfig(
        user=args.mysql_user,
        password=args.mysql_password or __import__("os").getenv("BOQ_MYSQL_PASSWORD", ""),
        host=args.mysql_host,
        port=args.mysql_port,
        database=args.mysql_database,
    )


if __name__ == "__main__":
    raise SystemExit(main())
