from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import and_, delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from boq_pricing.domain import PriceComponent
from boq_pricing.infrastructure.db import session_scope
from boq_pricing.infrastructure.orm_models import MaterialPriceORM, PriceRuleComponentORM, PriceRuleORM


@dataclass(frozen=True)
class MaterialPriceInput:
    material_code: str | None
    material_name: str
    specification: str | None
    region_code: str | None
    unit: str
    unit_price: Decimal
    price_month: str
    source: str


@dataclass(frozen=True)
class PriceComponentInput:
    component_type: str
    component_name: str
    unit: str | None
    quantity: Decimal
    unit_price: Decimal | None = None
    material_code: str | None = None
    quota_code: str | None = None
    price_source_type: str = "manual"
    source: str | None = None


class ComponentPricingRepository:
    def __init__(self, session_factory: sessionmaker[Session], tenant_code: str = "default") -> None:
        self._session_factory = session_factory
        self._tenant_code = tenant_code

    def upsert_material_prices(self, prices: list[MaterialPriceInput]) -> int:
        with session_scope(self._session_factory) as session:
            for price in prices:
                existing = session.scalar(
                    select(MaterialPriceORM).where(
                        MaterialPriceORM.tenant_code == self._tenant_code,
                        MaterialPriceORM.material_code == price.material_code,
                        MaterialPriceORM.material_name == price.material_name,
                        MaterialPriceORM.specification == price.specification,
                        MaterialPriceORM.region_code == price.region_code,
                        MaterialPriceORM.price_month == price.price_month,
                    )
                )
                if existing is None:
                    existing = MaterialPriceORM(tenant_code=self._tenant_code)
                    session.add(existing)
                existing.material_code = price.material_code
                existing.material_name = price.material_name
                existing.specification = price.specification
                existing.region_code = price.region_code
                existing.unit = price.unit
                existing.unit_price = price.unit_price
                existing.price_month = price.price_month
                existing.source = price.source
        return len(prices)

    def replace_rule_components(
        self,
        rule_code: str,
        version: str,
        components: list[PriceComponentInput],
        region_code: str | None = None,
        price_month: str | None = None,
    ) -> int:
        with session_scope(self._session_factory) as session:
            rule = session.scalar(
                select(PriceRuleORM).where(
                    PriceRuleORM.tenant_code == self._tenant_code,
                    PriceRuleORM.rule_code == rule_code,
                    PriceRuleORM.version == version,
                )
            )
            if rule is None:
                raise ValueError("Rule was not found.")
            session.execute(delete(PriceRuleComponentORM).where(PriceRuleComponentORM.price_rule_id == rule.id))
            total = Decimal("0")
            for component in components:
                unit_price = component.unit_price
                source = component.source
                if component.price_source_type == "material_latest":
                    material = self._latest_material_price(
                        session,
                        material_code=component.material_code,
                        region_code=region_code or rule.region_code,
                        price_month=price_month,
                    )
                    if material is None:
                        raise ValueError(f"Material price was not found: {component.material_code}")
                    unit_price = Decimal(material.unit_price)
                    source = material.source
                if unit_price is None:
                    raise ValueError(f"Component unit price is required: {component.component_name}")
                amount = component.quantity * unit_price
                total += amount
                session.add(
                    PriceRuleComponentORM(
                        price_rule_id=rule.id,
                        component_type=component.component_type,
                        component_name=component.component_name,
                        material_code=component.material_code,
                        quota_code=component.quota_code,
                        unit=component.unit,
                        quantity=component.quantity,
                        unit_price=unit_price,
                        price_source_type=component.price_source_type,
                        source=source,
                    )
                )
            rule.pricing_method = "component_sum"
            rule.unit_price = total
        return len(components)

    def load_components(self, rule_ids: list[int]) -> dict[int, tuple[PriceComponent, ...]]:
        if not rule_ids:
            return {}
        with session_scope(self._session_factory) as session:
            rows = session.scalars(
                select(PriceRuleComponentORM).where(PriceRuleComponentORM.price_rule_id.in_(rule_ids))
            ).all()
            grouped: dict[int, list[PriceComponent]] = {}
            for row in rows:
                quantity = Decimal(row.quantity)
                unit_price = Decimal(row.unit_price)
                grouped.setdefault(row.price_rule_id, []).append(
                    PriceComponent(
                        component_type=row.component_type,
                        component_name=row.component_name,
                        unit=row.unit,
                        quantity=quantity,
                        unit_price=unit_price,
                        amount=quantity * unit_price,
                        source=row.source,
                    )
                )
            return {key: tuple(value) for key, value in grouped.items()}

    def _latest_material_price(
        self,
        session: Session,
        material_code: str | None,
        region_code: str | None,
        price_month: str | None,
    ) -> MaterialPriceORM | None:
        filters = [
            MaterialPriceORM.tenant_code == self._tenant_code,
            MaterialPriceORM.material_code == material_code,
        ]
        if region_code:
            filters.append(MaterialPriceORM.region_code == region_code)
        if price_month:
            filters.append(MaterialPriceORM.price_month <= price_month)
        return session.scalar(
            select(MaterialPriceORM)
            .where(and_(*filters))
            .order_by(MaterialPriceORM.price_month.desc(), MaterialPriceORM.id.desc())
            .limit(1)
        )

