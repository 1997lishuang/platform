from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from boq_pricing.domain import PriceRule
from boq_pricing.infrastructure.db import session_scope
from boq_pricing.infrastructure.component_pricing import ComponentPricingRepository
from boq_pricing.infrastructure.orm_models import PriceRuleConditionORM, PriceRuleORM


class SqlAlchemyPriceRuleRepository:
    def __init__(self, session_factory: sessionmaker[Session], tenant_code: str = "default") -> None:
        self._session_factory = session_factory
        self._tenant_code = tenant_code

    def load(
        self,
        version: str | None = None,
        region_code: str | None = None,
        specialty: str | None = None,
        cost_category: str | None = None,
    ) -> list[PriceRule]:
        filters = [
            PriceRuleORM.tenant_code == self._tenant_code,
            PriceRuleORM.active.is_(True),
            PriceRuleORM.status == "active",
        ]
        if version:
            filters.append(PriceRuleORM.version == version)
        if region_code:
            filters.append(or_(PriceRuleORM.region_code.is_(None), PriceRuleORM.region_code == region_code))
        if specialty:
            filters.append(or_(PriceRuleORM.specialty.is_(None), PriceRuleORM.specialty == specialty))
        if cost_category:
            filters.append(or_(PriceRuleORM.cost_category.is_(None), PriceRuleORM.cost_category == cost_category))

        with session_scope(self._session_factory) as session:
            rows = session.scalars(
                select(PriceRuleORM)
                .where(and_(*filters))
                .order_by(PriceRuleORM.match_priority.asc(), PriceRuleORM.version.desc(), PriceRuleORM.id.asc())
            ).all()
            components_by_rule = ComponentPricingRepository(
                self._session_factory,
                tenant_code=self._tenant_code,
            ).load_components([row.id for row in rows])
            return [
                PriceRule(
                    rule_id=row.rule_code,
                    item_name_contains=row.item_name_contains,
                    unit=row.unit,
                    feature_conditions=dict(row.feature_conditions_json or {}),
                    unit_price=Decimal(row.unit_price),
                    source=row.source,
                    version=row.version,
                    pricing_method=row.pricing_method,
                    components=components_by_rule.get(row.id, ()),
                )
                for row in rows
            ]

    def list_page(
        self,
        status: str | None = None,
        version: str | None = None,
        region_code: str | None = None,
        specialty: str | None = None,
        cost_category: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[PriceRuleORM], int]:
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        filters = [PriceRuleORM.tenant_code == self._tenant_code]
        if status:
            filters.append(PriceRuleORM.status == status)
        if version:
            filters.append(PriceRuleORM.version == version)
        if region_code:
            filters.append(or_(PriceRuleORM.region_code.is_(None), PriceRuleORM.region_code == region_code))
        if specialty:
            filters.append(or_(PriceRuleORM.specialty.is_(None), PriceRuleORM.specialty == specialty))
        if cost_category:
            filters.append(or_(PriceRuleORM.cost_category.is_(None), PriceRuleORM.cost_category == cost_category))
        if keyword:
            like = f"%{keyword}%"
            filters.append(
                or_(
                    PriceRuleORM.rule_code.like(like),
                    PriceRuleORM.item_name_contains.like(like),
                    PriceRuleORM.unit.like(like),
                    PriceRuleORM.source.like(like),
                    PriceRuleORM.specialty.like(like),
                    PriceRuleORM.cost_category.like(like),
                )
            )

        with session_scope(self._session_factory) as session:
            total = session.scalar(select(func.count()).select_from(PriceRuleORM).where(and_(*filters))) or 0
            rows = session.scalars(
                select(PriceRuleORM)
                .where(and_(*filters))
                .order_by(PriceRuleORM.updated_at.desc(), PriceRuleORM.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            for row in rows:
                session.expunge(row)
            return list(rows), int(total)

    def list_versions(self, status: str | None = None) -> list[tuple[str, str, int]]:
        filters = [PriceRuleORM.tenant_code == self._tenant_code]
        if status:
            filters.append(PriceRuleORM.status == status)
        with session_scope(self._session_factory) as session:
            rows = session.execute(
                select(
                    PriceRuleORM.version,
                    PriceRuleORM.status,
                    func.count(PriceRuleORM.id),
                )
                .where(and_(*filters))
                .group_by(PriceRuleORM.version, PriceRuleORM.status)
                .order_by(PriceRuleORM.version.desc(), PriceRuleORM.status.asc())
            ).all()
            return [(str(version), str(row_status), int(count)) for version, row_status, count in rows]

    def list_identities(
        self,
        *,
        status: str | None = None,
        version: str | None = None,
        region_code: str | None = None,
        specialty: str | None = None,
        cost_category: str | None = None,
        keyword: str | None = None,
        allowed_statuses: set[str] | None = None,
    ) -> list[tuple[str, str]]:
        filters = self._build_filters(
            status=status,
            version=version,
            region_code=region_code,
            specialty=specialty,
            cost_category=cost_category,
            keyword=keyword,
        )
        if allowed_statuses:
            filters.append(PriceRuleORM.status.in_(allowed_statuses))
        with session_scope(self._session_factory) as session:
            rows = session.execute(
                select(PriceRuleORM.rule_code, PriceRuleORM.version)
                .where(and_(*filters))
                .order_by(PriceRuleORM.updated_at.desc(), PriceRuleORM.id.desc())
            ).all()
            return [(str(rule_code), str(row_version)) for rule_code, row_version in rows]

    def get(self, rule_code: str, version: str) -> PriceRuleORM | None:
        with session_scope(self._session_factory) as session:
            row = session.scalar(
                select(PriceRuleORM).where(
                    PriceRuleORM.tenant_code == self._tenant_code,
                    PriceRuleORM.rule_code == rule_code,
                    PriceRuleORM.version == version,
                )
            )
            if row is not None:
                session.expunge(row)
            return row

    def upsert_rule(
        self,
        *,
        rule_code: str,
        version: str,
        status: str,
        item_name_contains: str,
        unit: str | None,
        unit_price: Decimal,
        source: str,
        feature_conditions: dict[str, str],
        region_code: str | None = None,
        specialty: str | None = None,
        cost_category: str | None = None,
        match_priority: int = 100,
        active: bool = True,
        username: str | None = None,
    ) -> PriceRuleORM:
        with session_scope(self._session_factory) as session:
            row = session.scalar(
                select(PriceRuleORM).where(
                    PriceRuleORM.tenant_code == self._tenant_code,
                    PriceRuleORM.rule_code == rule_code,
                    PriceRuleORM.version == version,
                )
            )
            if row is None:
                row = PriceRuleORM(
                    tenant_code=self._tenant_code,
                    rule_code=rule_code,
                    version=version,
                    created_by=username,
                )
                session.add(row)
            row.status = status
            row.active = active
            row.region_code = region_code
            row.specialty = specialty
            row.cost_category = cost_category
            row.item_name_contains = item_name_contains
            row.unit = unit
            row.feature_conditions_json = feature_conditions
            row.unit_price = unit_price
            row.pricing_method = "fixed_unit_price"
            row.match_priority = match_priority
            row.source = source
            if status == "active" and active:
                self._deactivate_other_versions(session, row.rule_code, row.version)
            session.flush()
            session.execute(delete(PriceRuleConditionORM).where(PriceRuleConditionORM.price_rule_id == row.id))
            for key, value in feature_conditions.items():
                if value is None or str(value).strip() == "":
                    continue
                session.add(
                    PriceRuleConditionORM(
                        price_rule_id=row.id,
                        feature_key=str(key),
                        operator="contains",
                        expected_value=str(value),
                        weight=Decimal("1"),
                    )
                )
            session.flush()
            session.refresh(row)
            session.expunge(row)
            return row

    def delete_rules(self, identities: Iterable[tuple[str, str]]) -> tuple[int, int]:
        affected = 0
        skipped = 0
        with session_scope(self._session_factory) as session:
            for rule_code, version in identities:
                row = session.scalar(
                    select(PriceRuleORM).where(
                        PriceRuleORM.tenant_code == self._tenant_code,
                        PriceRuleORM.rule_code == rule_code,
                        PriceRuleORM.version == version,
                    )
                )
                if row is None:
                    skipped += 1
                    continue
                session.delete(row)
                affected += 1
        return affected, skipped

    def delete_rule(self, rule_code: str, version: str) -> bool:
        with session_scope(self._session_factory) as session:
            row = session.scalar(
                select(PriceRuleORM).where(
                    PriceRuleORM.tenant_code == self._tenant_code,
                    PriceRuleORM.rule_code == rule_code,
                    PriceRuleORM.version == version,
                )
            )
            if row is None:
                return False
            session.delete(row)
            return True

    def upsert_many(self, rules: list[PriceRule]) -> int:
        if not rules:
            return 0
        with session_scope(self._session_factory) as session:
            for rule in rules:
                persisted = session.scalar(
                    select(PriceRuleORM).where(
                        PriceRuleORM.tenant_code == self._tenant_code,
                        PriceRuleORM.rule_code == rule.rule_id,
                        PriceRuleORM.version == rule.version,
                    )
                )
                if persisted is None:
                    persisted = PriceRuleORM(
                        tenant_code=self._tenant_code,
                        rule_code=rule.rule_id,
                        version=rule.version,
                    )
                    session.add(persisted)
                persisted.status = "active"
                persisted.item_name_contains = rule.item_name_contains
                persisted.unit = rule.unit
                persisted.feature_conditions_json = rule.feature_conditions
                persisted.unit_price = rule.unit_price
                persisted.pricing_method = rule.pricing_method
                persisted.match_priority = 100
                persisted.source = rule.source
                self._deactivate_other_versions(session, persisted.rule_code, persisted.version)
                persisted.active = True
                session.flush()
                session.execute(
                    delete(PriceRuleConditionORM).where(
                        PriceRuleConditionORM.price_rule_id == persisted.id
                    )
                )
                for key, value in rule.feature_conditions.items():
                    session.add(
                        PriceRuleConditionORM(
                            price_rule_id=persisted.id,
                            feature_key=key,
                            operator="contains",
                            expected_value=value,
                            weight=Decimal("1"),
                        )
                    )
        return len(rules)

    def _build_filters(
        self,
        *,
        status: str | None = None,
        version: str | None = None,
        region_code: str | None = None,
        specialty: str | None = None,
        cost_category: str | None = None,
        keyword: str | None = None,
    ) -> list:
        filters = [PriceRuleORM.tenant_code == self._tenant_code]
        if status:
            filters.append(PriceRuleORM.status == status)
        if version:
            filters.append(PriceRuleORM.version == version)
        if region_code:
            filters.append(or_(PriceRuleORM.region_code.is_(None), PriceRuleORM.region_code == region_code))
        if specialty:
            filters.append(or_(PriceRuleORM.specialty.is_(None), PriceRuleORM.specialty == specialty))
        if cost_category:
            filters.append(or_(PriceRuleORM.cost_category.is_(None), PriceRuleORM.cost_category == cost_category))
        if keyword:
            like = f"%{keyword}%"
            filters.append(
                or_(
                    PriceRuleORM.rule_code.like(like),
                    PriceRuleORM.item_name_contains.like(like),
                    PriceRuleORM.unit.like(like),
                    PriceRuleORM.source.like(like),
                    PriceRuleORM.specialty.like(like),
                    PriceRuleORM.cost_category.like(like),
                )
            )
        return filters

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
