from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any


class IssueSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class SourceRef:
    workbook: str
    sheet: str
    row_number: int


@dataclass
class FeatureSet:
    raw_text: str
    values: dict[str, str] = field(default_factory=dict)


@dataclass
class BillItem:
    sequence: str | None
    item_code: str | None
    item_name: str
    feature_text: str
    unit: str | None
    quantity: Decimal | None
    original_unit_price: Decimal | None
    original_total_price: Decimal | None
    work_content: str | None
    remark: str | None
    source: SourceRef
    features: FeatureSet | None = None
    standard_item_name: str | None = None
    item_mapping_status: str | None = None
    item_mapping_candidates: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class PriceComponent:
    component_type: str
    component_name: str
    unit: str | None
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal
    source: str | None = None


@dataclass(frozen=True)
class PriceRule:
    rule_id: str
    item_name_contains: str
    unit: str | None
    feature_conditions: dict[str, str]
    unit_price: Decimal
    source: str
    version: str
    pricing_method: str = "fixed_unit_price"
    components: tuple[PriceComponent, ...] = ()


@dataclass(frozen=True)
class PriceQuote:
    unit_price: Decimal | None
    total_price: Decimal | None
    rule_id: str | None
    rule_version: str | None
    source: str | None
    confidence: float
    matched_conditions: dict[str, str]
    components: tuple[PriceComponent, ...] = ()


@dataclass(frozen=True)
class ValidationIssue:
    severity: IssueSeverity
    code: str
    message: str
    source: SourceRef | None = None


@dataclass
class PricingResult:
    item: BillItem
    quote: PriceQuote
    issues: list[ValidationIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sheet": self.item.source.sheet,
            "row_number": self.item.source.row_number,
            "sequence": self.item.sequence,
            "item_code": self.item.item_code,
            "item_name": self.item.item_name,
            "unit": self.item.unit,
            "quantity": str(self.item.quantity) if self.item.quantity is not None else None,
            "unit_price": str(self.quote.unit_price) if self.quote.unit_price is not None else None,
            "total_price": str(self.quote.total_price) if self.quote.total_price is not None else None,
            "rule_id": self.quote.rule_id,
            "rule_version": self.quote.rule_version,
            "price_source": self.quote.source,
            "confidence": self.quote.confidence,
            "pricing_method": "component_sum" if self.quote.components else "fixed_unit_price",
            "components": [
                {
                    "component_type": component.component_type,
                    "component_name": component.component_name,
                    "unit": component.unit,
                    "quantity": str(component.quantity),
                    "unit_price": str(component.unit_price),
                    "amount": str(component.amount),
                    "source": component.source,
                }
                for component in self.quote.components
            ],
            "features": self.item.features.values if self.item.features else {},
            "issues": [
                {
                    "severity": issue.severity.value,
                    "code": issue.code,
                    "message": issue.message,
                }
                for issue in self.issues
            ],
        }
