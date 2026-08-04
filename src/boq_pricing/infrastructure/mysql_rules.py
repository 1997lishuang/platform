from __future__ import annotations

import json
from decimal import Decimal

from boq_pricing.domain import PriceRule
from boq_pricing.infrastructure.mysql_client import MySqlCliClient, sql_quote


class MySqlPriceRuleRepository:
    def __init__(self, client: MySqlCliClient, tenant_code: str = "default") -> None:
        self._client = client
        self._tenant_code = tenant_code

    def load(
        self,
        version: str | None = None,
        region_code: str | None = None,
        specialty: str | None = None,
        cost_category: str | None = None,
    ) -> list[PriceRule]:
        where = [
            "active = 1",
            "status = 'active'",
            f"tenant_code = {sql_quote(self._tenant_code)}",
        ]
        if version:
            where.append(f"version = {sql_quote(version)}")
        if region_code:
            where.append(f"(region_code IS NULL OR region_code = {sql_quote(region_code)})")
        if specialty:
            where.append(f"(specialty IS NULL OR specialty = {sql_quote(specialty)})")
        if cost_category:
            where.append(f"(cost_category IS NULL OR cost_category = {sql_quote(cost_category)})")
        sql = f"""
            SELECT
              rule_code,
              version,
              item_name_contains,
              unit,
              JSON_UNQUOTE(JSON_EXTRACT(feature_conditions_json, '$')) AS feature_conditions_json,
              unit_price,
              source
            FROM price_rule
            WHERE {' AND '.join(where)}
            ORDER BY match_priority ASC, version DESC, id ASC
        """
        rows = self._client.query_rows(sql)
        return [
            PriceRule(
                rule_id=row["rule_code"],
                item_name_contains=row["item_name_contains"],
                unit=row.get("unit") or None,
                feature_conditions=json.loads(row["feature_conditions_json"] or "{}"),
                unit_price=Decimal(row["unit_price"]),
                source=row["source"],
                version=row["version"],
            )
            for row in rows
        ]

    def upsert_many(self, rules: list[PriceRule]) -> int:
        if not rules:
            return 0
        values = []
        for rule in rules:
            values.append(
                "("
                f"{sql_quote(self._tenant_code)}, "
                f"{sql_quote(rule.rule_id)}, "
                f"{sql_quote(rule.version)}, "
                "'active', "
                f"{sql_quote(rule.item_name_contains)}, "
                f"{sql_quote(rule.unit)}, "
                f"CAST({sql_quote(json.dumps(rule.feature_conditions, ensure_ascii=False))} AS JSON), "
                f"{rule.unit_price}, "
                "'fixed_unit_price', "
                "100, "
                f"{sql_quote(rule.source)}, "
                "1"
                ")"
            )
        sql = f"""
            INSERT INTO price_rule
              (
                tenant_code, rule_code, version, status, item_name_contains,
                unit, feature_conditions_json, unit_price, pricing_method,
                match_priority, source, active
              )
            VALUES {', '.join(values)}
            ON DUPLICATE KEY UPDATE
              status = VALUES(status),
              item_name_contains = VALUES(item_name_contains),
              unit = VALUES(unit),
              feature_conditions_json = VALUES(feature_conditions_json),
              unit_price = VALUES(unit_price),
              pricing_method = VALUES(pricing_method),
              match_priority = VALUES(match_priority),
              source = VALUES(source),
              active = VALUES(active)
        """
        self._client.execute(sql)
        self._sync_conditions(rules)
        return len(rules)

    def _sync_conditions(self, rules: list[PriceRule]) -> None:
        for rule in rules:
            rows = self._client.query_rows(
                """
                SELECT id
                FROM price_rule
                WHERE tenant_code = """
                + sql_quote(self._tenant_code)
                + """
                  AND rule_code = """
                + sql_quote(rule.rule_id)
                + " AND version = "
                + sql_quote(rule.version)
                + " LIMIT 1"
            )
            if not rows:
                continue
            rule_id = rows[0]["id"]
            self._client.execute(f"DELETE FROM price_rule_condition WHERE price_rule_id = {rule_id}")
            if not rule.feature_conditions:
                continue
            values = [
                "("
                f"{rule_id}, "
                f"{sql_quote(key)}, "
                "'contains', "
                f"{sql_quote(value)}, "
                "1"
                ")"
                for key, value in rule.feature_conditions.items()
            ]
            self._client.execute(
                """
                INSERT INTO price_rule_condition
                  (price_rule_id, feature_key, operator, expected_value, weight)
                VALUES
                """
                + ", ".join(values)
            )
