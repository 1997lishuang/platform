from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from boq_pricing.infrastructure.db import session_scope
from boq_pricing.infrastructure.market_quote_provider import MarketQuoteResult
from boq_pricing.infrastructure.orm_models import MarketPriceQuoteORM, PriceRuleConditionORM, PriceRuleORM


class MarketQuoteRepository:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        tenant_code: str = "default",
        pricing_task_code: str | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._tenant_code = tenant_code
        self._pricing_task_code = pricing_task_code

    def save(self, result: MarketQuoteResult, username: str | None = None) -> MarketPriceQuoteORM:
        return self.upsert_pending_review(result, username=username)

    def upsert_pending_review(self, result: MarketQuoteResult, username: str | None = None) -> MarketPriceQuoteORM:
        with session_scope(self._session_factory) as session:
            row = self._find_pending_match(session, result)
            is_existing = row is not None
            if row is None:
                row = MarketPriceQuoteORM(
                    tenant_code=self._tenant_code,
                    quote_code=uuid.uuid4().hex,
                    status="pending_review",
                )
                session.add(row)

            previous_recommended_price = row.recommended_price if is_existing else None
            previous_price_min = row.price_min if is_existing else None
            previous_price_max = row.price_max if is_existing else None
            previous_confidence = row.confidence if is_existing else None

            if self._pricing_task_code:
                row.pricing_task_code = self._pricing_task_code
            row.provider = result.provider
            row.model = result.model
            row.item_name = result.item_name
            row.feature_json = result.features
            row.region_code = result.region_code
            row.unit = result.unit
            if previous_recommended_price is None:
                row.price_min = result.price_min
                row.price_max = result.price_max
                row.recommended_price = result.recommended_price
                row.confidence = result.confidence
            else:
                row.price_min = previous_price_min
                row.price_max = previous_price_max
                row.recommended_price = previous_recommended_price
                row.confidence = min(result.confidence, previous_confidence or result.confidence)
            row.tax_included = result.tax_included
            row.source_urls_json = unique_urls([*(row.source_urls_json or []), *result.source_urls])
            row.assumptions_json = stabilize_assumptions(
                existing=dict(row.assumptions_json or {}),
                incoming=result.assumptions,
                previous_recommended_price=previous_recommended_price,
                incoming_recommended_price=result.recommended_price,
            )
            row.raw_response = result.raw_response
            row.status = "pending_review"
            row.created_by = username
            row.reviewed_by = None
            row.review_comment = None
            row.reviewed_at = None
            session.flush()
            session.refresh(row)
            session.expunge(row)
            return row

    def list_recent(self, status: str | None = None, limit: int = 50) -> list[MarketPriceQuoteORM]:
        with session_scope(self._session_factory) as session:
            query = select(MarketPriceQuoteORM).where(MarketPriceQuoteORM.tenant_code == self._tenant_code)
            if status:
                query = query.where(MarketPriceQuoteORM.status == status)
            rows = session.scalars(query.order_by(MarketPriceQuoteORM.id.desc()).limit(limit)).all()
            for row in rows:
                session.expunge(row)
            return list(rows)

    def list_page(
        self,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[MarketPriceQuoteORM], int]:
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        offset = (page - 1) * page_size
        with session_scope(self._session_factory) as session:
            filters = [MarketPriceQuoteORM.tenant_code == self._tenant_code]
            if status:
                filters.append(MarketPriceQuoteORM.status == status)
            total = session.scalar(select(func.count()).select_from(MarketPriceQuoteORM).where(*filters)) or 0
            rows = session.scalars(
                select(MarketPriceQuoteORM)
                .where(*filters)
                .order_by(MarketPriceQuoteORM.id.desc())
                .offset(offset)
                .limit(page_size)
            ).all()
            for row in rows:
                session.expunge(row)
            return list(rows), int(total)

    def find_reusable(
        self,
        item_name: str,
        unit: str | None,
        features: dict[str, str],
        region_code: str | None,
        limit: int = 20,
    ) -> MarketPriceQuoteORM | None:
        with session_scope(self._session_factory) as session:
            query = (
                select(MarketPriceQuoteORM)
                .where(
                    MarketPriceQuoteORM.tenant_code == self._tenant_code,
                    MarketPriceQuoteORM.item_name == item_name,
                    MarketPriceQuoteORM.recommended_price.is_not(None),
                    MarketPriceQuoteORM.status == "adopted",
                )
                .order_by(MarketPriceQuoteORM.id.desc())
                .limit(limit)
            )
            if unit:
                query = query.where(MarketPriceQuoteORM.unit == unit)
            if region_code:
                query = query.where(MarketPriceQuoteORM.region_code == region_code)
            rows = session.scalars(query).all()
            for row in rows:
                if dict(row.feature_json or {}) == features:
                    session.expunge(row)
                    return row
            return None

    def has_pending_for_task(self, pricing_task_code: str) -> bool:
        with session_scope(self._session_factory) as session:
            count = session.scalar(
                select(func.count()).select_from(MarketPriceQuoteORM).where(
                    MarketPriceQuoteORM.tenant_code == self._tenant_code,
                    MarketPriceQuoteORM.pricing_task_code == pricing_task_code,
                    MarketPriceQuoteORM.status == "pending_review",
                )
            )
            return bool(count)

    def approve(self, quote_code: str, username: str, comment: str | None = None) -> MarketPriceQuoteORM:
        with session_scope(self._session_factory) as session:
            row = self._get_for_update(session, quote_code)
            if row.status != "pending_review":
                raise ValueError(f"Only pending_review market quotes can be approved, got {row.status}.")
            if row.recommended_price is None:
                raise ValueError("Market quote recommended price is required before approval.")
            row.status = "adopted"
            row.reviewed_by = username
            row.review_comment = comment
            row.reviewed_at = datetime.now(UTC)
            self._upsert_active_price_rule(session, row, username)
            session.flush()
            session.refresh(row)
            session.expunge(row)
            return row

    def reject(self, quote_code: str, username: str, comment: str | None = None) -> MarketPriceQuoteORM:
        with session_scope(self._session_factory) as session:
            row = self._get_for_update(session, quote_code)
            if row.status != "pending_review":
                raise ValueError(f"Only pending_review market quotes can be rejected, got {row.status}.")
            row.status = "rejected"
            row.reviewed_by = username
            row.review_comment = comment
            row.reviewed_at = datetime.now(UTC)
            session.flush()
            session.refresh(row)
            session.expunge(row)
            return row

    def publish_adopted_quotes_as_rules(self, username: str = "system") -> int:
        with session_scope(self._session_factory) as session:
            rows = session.scalars(
                select(MarketPriceQuoteORM).where(
                    MarketPriceQuoteORM.tenant_code == self._tenant_code,
                    MarketPriceQuoteORM.status == "adopted",
                    MarketPriceQuoteORM.recommended_price.is_not(None),
                )
            ).all()
            for row in rows:
                self._upsert_active_price_rule(session, row, row.reviewed_by or username)
            return len(rows)

    def _get_for_update(self, session: Session, quote_code: str) -> MarketPriceQuoteORM:
        row = session.scalar(
            select(MarketPriceQuoteORM).where(
                MarketPriceQuoteORM.tenant_code == self._tenant_code,
                MarketPriceQuoteORM.quote_code == quote_code,
            )
        )
        if row is None:
            raise ValueError("Market quote was not found.")
        return row

    def _find_pending_match(self, session: Session, result: MarketQuoteResult) -> MarketPriceQuoteORM | None:
        query = (
            select(MarketPriceQuoteORM)
            .where(
                MarketPriceQuoteORM.tenant_code == self._tenant_code,
                MarketPriceQuoteORM.status == "pending_review",
                MarketPriceQuoteORM.provider == result.provider,
                MarketPriceQuoteORM.model == result.model,
                MarketPriceQuoteORM.item_name == result.item_name,
            )
            .order_by(MarketPriceQuoteORM.id.desc())
            .limit(50)
        )
        if result.unit:
            query = query.where(MarketPriceQuoteORM.unit == result.unit)
        else:
            query = query.where(MarketPriceQuoteORM.unit.is_(None))
        if result.region_code:
            query = query.where(MarketPriceQuoteORM.region_code == result.region_code)
        else:
            query = query.where(MarketPriceQuoteORM.region_code.is_(None))
        for row in session.scalars(query).all():
            if dict(row.feature_json or {}) == dict(result.features or {}):
                return row
        return None

    def _upsert_active_price_rule(self, session: Session, row: MarketPriceQuoteORM, username: str) -> None:
        rule_code = f"MQ-{row.quote_code}"
        version = "market-adopted"
        rule = session.scalar(
            select(PriceRuleORM).where(
                PriceRuleORM.tenant_code == row.tenant_code,
                PriceRuleORM.rule_code == rule_code,
                PriceRuleORM.version == version,
            )
        )
        if rule is None:
            rule = PriceRuleORM(
                tenant_code=row.tenant_code,
                rule_code=rule_code,
                version=version,
            )
            session.add(rule)

        rule.status = "active"
        rule.project_type = None
        rule.region_code = row.region_code
        rule.specialty = None
        rule.cost_category = None
        rule.item_name_contains = row.item_name
        rule.unit = row.unit
        rule.feature_conditions_json = dict(row.feature_json or {})
        rule.unit_price = row.recommended_price
        rule.pricing_method = "fixed_unit_price"
        rule.match_priority = 20
        rule.source = f"market_quote:{row.quote_code}"
        rule.active = True
        rule.created_by = row.created_by
        rule.submitted_by = row.created_by
        rule.reviewed_by = username
        rule.reviewed_at = row.reviewed_at
        rule.review_comment = row.review_comment

        session.flush()
        session.query(PriceRuleConditionORM).filter(
            PriceRuleConditionORM.price_rule_id == rule.id
        ).delete(synchronize_session=False)
        for key, value in dict(row.feature_json or {}).items():
            if value is None or str(value).strip() == "":
                continue
            session.add(
                PriceRuleConditionORM(
                    price_rule_id=rule.id,
                    feature_key=str(key),
                    operator="contains",
                    expected_value=str(value),
                    weight=Decimal("1"),
                )
            )


def unique_urls(urls: list[str | None]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            continue
        if url in seen:
            continue
        seen.add(url)
        result.append(url)
    return result


def stabilize_assumptions(
    existing: dict,
    incoming: dict,
    previous_recommended_price: Decimal | None,
    incoming_recommended_price: Decimal | None,
) -> dict:
    observations = list(existing.get("quote_observations") or [])
    if previous_recommended_price is not None:
        observations.append(
            {
                "incoming_recommended_price": str(incoming_recommended_price) if incoming_recommended_price is not None else None,
                "incoming_supplier_quotes": incoming.get("supplier_quotes", []),
                "incoming_source_urls": incoming.get("source_urls") or incoming.get("verified_source_urls") or [],
                "policy": "same pending target keeps the first valid review price; later quotes are saved as observations only",
            }
        )
    merged = {
        **existing,
        **incoming,
        "quote_observations": observations[-10:],
        "stability_policy": (
            "For the same pending BOQ target, the first valid recommended price is locked. "
            "Later model calls append observations and evidence only. Human approval is required before adoption."
        ),
    }
    if previous_recommended_price is not None:
        merged["locked_recommended_price"] = str(previous_recommended_price)
        merged["latest_model_recommended_price"] = str(incoming_recommended_price) if incoming_recommended_price is not None else None
    return merged
