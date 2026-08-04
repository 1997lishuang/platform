from __future__ import annotations

import json
import uuid
from pathlib import Path

from boq_pricing.domain import PricingResult
from boq_pricing.infrastructure.mysql_client import MySqlCliClient, sql_quote
from boq_pricing.pricing.calculations import calculate_total_price


class MySqlPricingAuditWriter:
    def __init__(self, client: MySqlCliClient, tenant_code: str = "default") -> None:
        self._client = client
        self._tenant_code = tenant_code

    def write_run(
        self,
        workbook_path: str | Path,
        rule_source: str,
        results: list[PricingResult],
        project_name: str | None = None,
        region_code: str | None = None,
    ) -> str:
        run_code = uuid.uuid4().hex
        priced_count = sum(1 for result in results if result.quote.unit_price is not None)
        versions = sorted({result.quote.rule_version for result in results if result.quote.rule_version})
        rule_version = ",".join(versions) if versions else None
        self._client.execute(
            """
            INSERT INTO pricing_run
              (
                tenant_code, run_code, workbook_name, project_name, region_code,
                rule_source, rule_version, item_count, priced_count, unpriced_count
              )
            VALUES
              (
            """
            + f"{sql_quote(self._tenant_code)}, "
            + f"{sql_quote(run_code)}, "
            + f"{sql_quote(Path(workbook_path).name)}, "
            + f"{sql_quote(project_name)}, "
            + f"{sql_quote(region_code)}, "
            + f"{sql_quote(rule_source)}, "
            + f"{sql_quote(rule_version)}, "
            + f"{len(results)}, "
            + f"{priced_count}, "
            + f"{len(results) - priced_count}"
            + ")"
        )
        run_id = self._client.query_rows(
            "SELECT id FROM pricing_run WHERE tenant_code = "
            + sql_quote(self._tenant_code)
            + " AND run_code = "
            + sql_quote(run_code)
            + " LIMIT 1"
        )[0]["id"]
        self._insert_results(run_id, results)
        return run_code

    def _insert_results(self, run_id: str, results: list[PricingResult]) -> None:
        if not results:
            return
        values = []
        for result in results:
            item = result.item
            quote = result.quote
            total_price = calculate_total_price(item.quantity, quote.unit_price)
            values.append(
                "("
                f"{run_id}, "
                f"{sql_quote(item.source.sheet)}, "
                f"{item.source.row_number}, "
                f"{sql_quote(item.sequence)}, "
                f"{sql_quote(item.item_code)}, "
                f"{sql_quote(item.item_name)}, "
                f"{sql_quote(item.unit)}, "
                f"{item.quantity if item.quantity is not None else 'NULL'}, "
                f"{quote.unit_price if quote.unit_price is not None else 'NULL'}, "
                f"{total_price if total_price is not None else 'NULL'}, "
                f"{sql_quote(quote.rule_id)}, "
                f"{sql_quote(quote.rule_version)}, "
                f"{sql_quote(quote.source)}, "
                f"{quote.confidence}, "
                f"CAST({sql_quote(json.dumps(item.features.values if item.features else {}, ensure_ascii=False))} AS JSON), "
                f"CAST({sql_quote(json.dumps([issue.message for issue in result.issues], ensure_ascii=False))} AS JSON)"
                ")"
            )
        sql = """
            INSERT INTO pricing_result
              (
                run_id, source_sheet, source_row_number, sequence_no, item_code,
                item_name, unit, quantity, unit_price, total_price, rule_code,
                rule_version, price_source, confidence, features_json, issues_json
              )
            VALUES
        """ + ", ".join(values)
        self._client.execute(sql)
