from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import and_, delete, select
from sqlalchemy.orm import Session, sessionmaker

from boq_pricing.domain import PriceRule
from boq_pricing.infrastructure.db import session_scope
from boq_pricing.infrastructure.orm_models import PriceRuleConditionORM, PriceRuleORM


class RuleApprovalRepository:
    def __init__(self, session_factory: sessionmaker[Session], tenant_code: str = "default") -> None:
        self._session_factory = session_factory
        self._tenant_code = tenant_code

    def create_draft(self, rule: PriceRule, username: str) -> PriceRuleORM:
        with session_scope(self._session_factory) as session:
            existing = self._find(session, rule.rule_id, rule.version)
            if existing is None:
                existing = PriceRuleORM(
                    tenant_code=self._tenant_code,
                    rule_code=rule.rule_id,
                    version=rule.version,
                    created_by=username,
                )
                session.add(existing)
            existing.status = "draft"
            existing.active = False
            existing.item_name_contains = rule.item_name_contains
            existing.unit = rule.unit
            existing.feature_conditions_json = rule.feature_conditions
            existing.unit_price = rule.unit_price
            existing.pricing_method = "fixed_unit_price"
            existing.match_priority = 100
            existing.source = rule.source
            existing.review_comment = None
            existing.submitted_by = None
            existing.reviewed_by = None
            existing.reviewed_at = None
            session.flush()
            self._replace_conditions(session, existing.id, rule.feature_conditions)
            session.expunge(existing)
            return existing

    def submit(self, rule_code: str, version: str, username: str) -> PriceRuleORM:
        with session_scope(self._session_factory) as session:
            rule = self._require_rule(session, rule_code, version)
            if rule.status not in {"draft", "rejected"}:
                raise ValueError(f"Only draft or rejected rules can be submitted, got {rule.status}.")
            rule.status = "reviewing"
            rule.active = False
            rule.submitted_by = username
            rule.review_comment = None
            session.flush()
            session.expunge(rule)
            return rule

    def approve(self, rule_code: str, version: str, username: str, comment: str | None = None) -> PriceRuleORM:
        with session_scope(self._session_factory) as session:
            rule = self._require_rule(session, rule_code, version)
            if rule.status != "reviewing":
                raise ValueError(f"Only reviewing rules can be approved, got {rule.status}.")
            rule.status = "active"
            rule.active = True
            self._deactivate_other_versions(session, rule.rule_code, rule.version)
            rule.reviewed_by = username
            rule.reviewed_at = datetime.now(UTC)
            rule.review_comment = comment
            session.flush()
            session.expunge(rule)
            return rule

    def reject(self, rule_code: str, version: str, username: str, comment: str | None = None) -> PriceRuleORM:
        with session_scope(self._session_factory) as session:
            rule = self._require_rule(session, rule_code, version)
            if rule.status != "reviewing":
                raise ValueError(f"Only reviewing rules can be rejected, got {rule.status}.")
            rule.status = "rejected"
            rule.active = False
            rule.reviewed_by = username
            rule.reviewed_at = datetime.now(UTC)
            rule.review_comment = comment
            session.flush()
            session.expunge(rule)
            return rule

    def list_rules(self, status: str | None = None, limit: int = 100) -> list[PriceRuleORM]:
        with session_scope(self._session_factory) as session:
            filters = [PriceRuleORM.tenant_code == self._tenant_code]
            if status:
                filters.append(PriceRuleORM.status == status)
            rows = session.scalars(
                select(PriceRuleORM)
                .where(and_(*filters))
                .order_by(PriceRuleORM.updated_at.desc(), PriceRuleORM.id.desc())
                .limit(limit)
            ).all()
            for row in rows:
                session.expunge(row)
            return list(rows)

    def _find(self, session: Session, rule_code: str, version: str) -> PriceRuleORM | None:
        return session.scalar(
            select(PriceRuleORM).where(
                PriceRuleORM.tenant_code == self._tenant_code,
                PriceRuleORM.rule_code == rule_code,
                PriceRuleORM.version == version,
            )
        )

    def _require_rule(self, session: Session, rule_code: str, version: str) -> PriceRuleORM:
        rule = self._find(session, rule_code, version)
        if rule is None:
            raise ValueError("Rule was not found.")
        return rule

    def _replace_conditions(self, session: Session, rule_id: int, conditions: dict[str, str]) -> None:
        session.execute(delete(PriceRuleConditionORM).where(PriceRuleConditionORM.price_rule_id == rule_id))
        for key, value in conditions.items():
            session.add(
                PriceRuleConditionORM(
                    price_rule_id=rule_id,
                    feature_key=key,
                    operator="contains",
                    expected_value=value,
                    weight=Decimal("1"),
                )
            )

    def _deactivate_other_versions(self, session: Session, rule_code: str, version: str) -> None:
        rows = session.scalars(
            select(PriceRuleORM).where(
                PriceRuleORM.tenant_code == self._tenant_code,
                PriceRuleORM.rule_code == rule_code,
                PriceRuleORM.version != version,
                PriceRuleORM.status == "active",
                PriceRuleORM.active.is_(True),
            )
        ).all()
        for row in rows:
            row.active = False
