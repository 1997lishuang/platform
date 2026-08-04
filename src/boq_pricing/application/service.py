from __future__ import annotations

from boq_pricing.domain import BillItem, IssueSeverity, PricingResult, ValidationIssue
from boq_pricing.infrastructure.item_mappings import ItemMappingRepository, MappingCandidate
from boq_pricing.parsing import FeatureParser
from boq_pricing.pricing import PricingEngine
from boq_pricing.validation import PricingValidator


class PricingApplicationService:
    def __init__(
        self,
        feature_parser: FeatureParser,
        pricing_engine: PricingEngine,
        validator: PricingValidator,
        item_mapping_repository: ItemMappingRepository | None = None,
    ) -> None:
        self._feature_parser = feature_parser
        self._pricing_engine = pricing_engine
        self._validator = validator
        self._item_mapping_repository = item_mapping_repository

    def process(self, items: list[BillItem]) -> list[PricingResult]:
        results: list[PricingResult] = []
        for item in items:
            item.features = self._feature_parser.parse(item.feature_text)
            mapping_issues = self._apply_item_mapping(item)
            quote = self._pricing_engine.quote(item)
            issues = mapping_issues + self._validator.validate(item, quote)
            results.append(PricingResult(item=item, quote=quote, issues=issues))
        return results

    def _apply_item_mapping(self, item: BillItem) -> list[ValidationIssue]:
        if self._item_mapping_repository is None:
            return []

        decision = self._item_mapping_repository.resolve(item)
        item.item_mapping_status = decision.status
        item.item_mapping_candidates = [candidate.to_dict() for candidate in decision.candidates]
        if decision.status == "mapped":
            item.standard_item_name = decision.standard_item_name
            return []

        if decision.status == "unmapped":
            rule_candidates = [
                MappingCandidate(
                    mapping_code=mapping_code,
                    standard_item_name=standard_item_name,
                    score=score,
                    reason=reason,
                )
                for mapping_code, standard_item_name, score, reason in self._pricing_engine.suggest_rule_mappings(item)
            ]
            if rule_candidates:
                threshold = float(self._item_mapping_repository.get_setting().confidence_threshold)
                decision_status = (
                    "ambiguous"
                    if len(rule_candidates) > 1 and rule_candidates[0].score - rule_candidates[1].score <= 0.15
                    else "low_confidence"
                    if rule_candidates[0].score < threshold
                    else "mapped"
                )
                if decision_status == "mapped":
                    item.item_mapping_status = "mapped"
                    item.item_mapping_candidates = [candidate.to_dict() for candidate in rule_candidates]
                    item.standard_item_name = rule_candidates[0].standard_item_name
                    return []
                decision = type(decision)(decision_status, None, rule_candidates)
                item.item_mapping_status = decision.status
                item.item_mapping_candidates = [candidate.to_dict() for candidate in decision.candidates]

        if decision.status in {"ambiguous", "low_confidence"}:
            review = self._item_mapping_repository.create_ambiguity_review(item, decision.candidates)
            candidates = "、".join(candidate.standard_item_name for candidate in decision.candidates[:3])
            if decision.status == "low_confidence":
                best_score = decision.candidates[0].score if decision.candidates else 0
                message = f"清单项映射置信度不足，最佳候选：{candidates}，置信度 {best_score:.2%}；已生成校准单 {review.review_code}"
            else:
                message = f"清单项映射存在歧义，候选：{candidates}；已生成校准单 {review.review_code}"
            return [
                ValidationIssue(
                    severity=IssueSeverity.WARNING,
                    code="ITEM_MAPPING_AMBIGUOUS",
                    message=message,
                    source=item.source,
                )
            ]

        return []
