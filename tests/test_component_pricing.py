from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from boq_pricing.domain import BillItem, PriceRule, SourceRef
from boq_pricing.infrastructure.component_pricing import (
    ComponentPricingRepository,
    MaterialPriceInput,
    PriceComponentInput,
)
from boq_pricing.infrastructure.db import Base
from boq_pricing.infrastructure.sqlalchemy_rules import SqlAlchemyPriceRuleRepository
from boq_pricing.pricing import PricingEngine


def test_component_pricing_sums_components_into_unit_price():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    rules = SqlAlchemyPriceRuleRepository(session_factory)
    components = ComponentPricingRepository(session_factory)

    rules.upsert_many(
        [
            PriceRule(
                rule_id="COMP-1",
                item_name_contains="测试组成价",
                unit="m",
                feature_conditions={},
                unit_price=Decimal("0"),
                source="test",
                version="v1",
            )
        ]
    )
    components.upsert_material_prices(
        [
            MaterialPriceInput(
                material_code="MAT-1",
                material_name="测试材料",
                specification=None,
                region_code="AH-LA",
                unit="kg",
                unit_price=Decimal("5"),
                price_month="2026-07",
                source="material-test",
            )
        ]
    )
    components.replace_rule_components(
        "COMP-1",
        "v1",
        [
            PriceComponentInput(
                component_type="material",
                component_name="测试材料",
                unit="kg",
                quantity=Decimal("2"),
                material_code="MAT-1",
                price_source_type="material_latest",
            ),
            PriceComponentInput(
                component_type="labor",
                component_name="人工",
                unit="工日",
                quantity=Decimal("0.5"),
                unit_price=Decimal("100"),
                source="labor-test",
            ),
        ],
        region_code="AH-LA",
        price_month="2026-07",
    )

    loaded = rules.load()
    quote = PricingEngine(loaded).quote(
        BillItem(
            sequence="1",
            item_code=None,
            item_name="测试组成价",
            feature_text="",
            unit="m",
            quantity=Decimal("3"),
            original_unit_price=None,
            original_total_price=None,
            work_content=None,
            remark=None,
            source=SourceRef("test.xlsx", "Sheet1", 1),
        )
    )

    assert quote.unit_price == Decimal("60.0000")
    assert quote.total_price == Decimal("180.00")
    assert len(quote.components) == 2

