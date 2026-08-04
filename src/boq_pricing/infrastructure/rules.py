from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from boq_pricing.domain import PriceRule


class JsonPriceRuleRepository:
    def load(self, path: str | Path) -> list[PriceRule]:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        version = str(payload.get("version", "unknown"))
        rules: list[PriceRule] = []
        for item in payload.get("rules", []):
            rules.append(
                PriceRule(
                    rule_id=str(item["id"]),
                    item_name_contains=str(item.get("item_name_contains", "")),
                    unit=item.get("unit"),
                    feature_conditions={
                        str(key): str(value)
                        for key, value in item.get("feature_conditions", {}).items()
                    },
                    unit_price=Decimal(str(item["unit_price"])),
                    source=str(item.get("source", "unknown")),
                    version=version,
                )
            )
        return rules


class JsonAuditWriter:
    def write(self, records: list[dict], path: str | Path) -> Path:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        return output

