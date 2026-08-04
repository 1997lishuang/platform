from __future__ import annotations

from decimal import Decimal

from boq_pricing.domain import BillItem, IssueSeverity, PriceQuote, ValidationIssue


class PricingValidator:
    def validate(self, item: BillItem, quote: PriceQuote) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if item.quantity is None:
            issues.append(error("MISSING_QUANTITY", "工程量为空，无法计算合价", item))
        elif item.quantity < Decimal("0"):
            issues.append(error("NEGATIVE_QUANTITY", "工程量为负数，请复核", item))

        if not item.unit:
            issues.append(warning("MISSING_UNIT", "计量单位为空，无法严格匹配价格规则", item))

        if quote.unit_price is None and item.item_mapping_status not in {"ambiguous", "low_confidence"}:
            issues.append(warning("NO_PRICE_RULE", "未匹配到综合单价规则，需要人工取价或补充规则库", item))

        if (
            item.original_total_price is not None
            and quote.total_price is not None
            and abs(item.original_total_price - quote.total_price) > Decimal("0.01")
        ):
            issues.append(
                warning(
                    "TOTAL_PRICE_DIFF",
                    f"原表合价 {item.original_total_price} 与计算合价 {quote.total_price} 不一致",
                    item,
                )
            )

        if item.features is not None and not item.features.values and item.feature_text:
            issues.append(
                warning("FEATURE_PARSE_EMPTY", "项目特征未解析出结构化指标，需要补充解析规则", item)
            )
        return issues


def error(code: str, message: str, item: BillItem) -> ValidationIssue:
    return ValidationIssue(IssueSeverity.ERROR, code, message, item.source)


def warning(code: str, message: str, item: BillItem) -> ValidationIssue:
    return ValidationIssue(IssueSeverity.WARNING, code, message, item.source)
