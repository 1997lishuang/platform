from __future__ import annotations

from difflib import SequenceMatcher
from decimal import Decimal
import re

from boq_pricing.domain import BillItem, PriceQuote, PriceRule
from boq_pricing.pricing.calculations import calculate_total_price


class PricingEngine:
    def __init__(self, rules: list[PriceRule]) -> None:
        self._rules = rules

    def quote(self, item: BillItem) -> PriceQuote:
        if item.item_mapping_status in {"ambiguous", "low_confidence"}:
            return empty_quote()

        best_rule, confidence, matched = self._find_best_rule(item)
        if best_rule is None or item.quantity is None:
            return empty_quote()

        total = calculate_total_price(item.quantity, best_rule.unit_price)
        return PriceQuote(
            unit_price=best_rule.unit_price,
            total_price=total,
            rule_id=best_rule.rule_id,
            rule_version=best_rule.version,
            source=best_rule.source,
            confidence=confidence,
            matched_conditions=matched,
            components=best_rule.components,
        )

    def _find_best_rule(
        self, item: BillItem
    ) -> tuple[PriceRule | None, float, dict[str, str]]:
        candidates: list[tuple[float, PriceRule, dict[str, str]]] = []
        features = item.features.values if item.features else {}
        item_name = item.standard_item_name or item.item_name

        for rule in self._rules:
            name_similarity = score_name_match(item_name, rule.item_name_contains)
            if rule.item_name_contains and name_similarity < 0.75:
                continue
            if rule.unit and item.unit and normalize_unit(rule.unit) != normalize_unit(item.unit):
                continue

            matched: dict[str, str] = {}
            condition_count = len(rule.feature_conditions)
            for key, expected in rule.feature_conditions.items():
                actual = features.get(key, "")
                if value_matches(actual, expected):
                    matched[key] = actual

            if condition_count and len(matched) != condition_count:
                continue

            name_score = Decimal("0.55") * Decimal(str(name_similarity))
            unit_score = Decimal("0.20") if rule.unit else Decimal("0")
            feature_score = Decimal("0.25")
            confidence = float(min(Decimal("1.0"), name_score + unit_score + feature_score))
            if item.standard_item_name:
                matched["标准计价对象"] = item.standard_item_name
            candidates.append((confidence, rule, matched))

        if not candidates:
            return None, 0.0, {}

        candidates.sort(key=lambda item_: (item_[0], len(item_[1].feature_conditions)), reverse=True)
        confidence, rule, matched = candidates[0]
        return rule, confidence, matched

    def suggest_rule_mappings(self, item: BillItem, min_score: float = 0.45) -> list[tuple[str, str, float, str]]:
        suggestions: list[tuple[str, str, float, str]] = []
        features = item.features.values if item.features else {}
        for rule in self._rules:
            name_similarity = score_name_match(item.item_name, rule.item_name_contains)
            if name_similarity < min_score:
                continue
            if rule.unit and item.unit and normalize_unit(rule.unit) != normalize_unit(item.unit):
                continue

            reasons = [f"规则名称相似度 {name_similarity:.0%}"]
            score = Decimal("0.65") * Decimal(str(name_similarity))
            if rule.unit and item.unit:
                score += Decimal("0.15")
                reasons.append("单位匹配")

            if rule.feature_conditions:
                matched = sum(
                    1
                    for key, expected in rule.feature_conditions.items()
                    if value_matches(features.get(key, ""), str(expected))
                )
                if matched != len(rule.feature_conditions):
                    continue
                score += Decimal("0.20")
                reasons.append("特征条件匹配")

            suggestions.append((
                f"RULE:{rule.rule_id}:{rule.version}",
                rule.item_name_contains,
                float(min(Decimal("1.0"), score)),
                "；".join(reasons),
            ))
        suggestions.sort(key=lambda item_: item_[2], reverse=True)
        return suggestions[:5]


def empty_quote() -> PriceQuote:
    return PriceQuote(
        unit_price=None,
        total_price=None,
        rule_id=None,
        rule_version=None,
        source=None,
        confidence=0.0,
        matched_conditions={},
        components=(),
    )


def value_matches(actual: str, expected: str) -> bool:
    actual_norm = compact(actual).lower()
    expected_norm = compact(expected).lower()
    return bool(actual_norm and expected_norm and expected_norm in actual_norm)


def score_name_match(item_name: str, rule_name: str) -> float:
    item_norm = compact(item_name).lower()
    rule_norm = compact(rule_name).lower()
    if not rule_norm:
        return 1.0
    if item_norm == rule_norm:
        return 1.0
    if rule_norm in item_norm or item_norm in rule_norm:
        return 0.95

    item_tokens = name_tokens(item_norm)
    rule_tokens = name_tokens(rule_norm)
    if item_tokens and rule_tokens:
        intersection = set(item_tokens) & set(rule_tokens)
        union = set(item_tokens) | set(rule_tokens)
        token_score = len(intersection) / len(union) if union else 0.0
    else:
        token_score = 0.0

    sorted_score = 0.95 if sorted(item_norm) == sorted(rule_norm) else 0.0
    sequence_score = SequenceMatcher(None, item_norm, rule_norm).ratio()
    return max(token_score, sorted_score, sequence_score)


def name_tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", value)


def compact(value: str | None) -> str:
    return str(value or "").replace(" ", "").replace("\u3000", "").strip()


def normalize_unit(unit: str | None) -> str:
    normalized = compact(unit).lower()
    return (
        normalized
        .replace("㎡", "m2")
        .replace("m²", "m2")
        .replace("平方米", "m2")
        .replace("m³", "m3")
        .replace("立方米", "m3")
        .replace("套", "set")
    )
