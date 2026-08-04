from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from boq_pricing.application import PricingApplicationService
from boq_pricing.domain import BillItem, PriceRule, SourceRef
from boq_pricing.infrastructure.db import Base
from boq_pricing.infrastructure.item_mappings import ItemMappingRepository
from boq_pricing.parsing import FeatureParser
from boq_pricing.pricing import PricingEngine
from boq_pricing.validation import PricingValidator


def test_unmapped_item_uses_price_rule_candidate_for_mapping_review():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    mapping_repository = ItemMappingRepository(session_factory, pricing_task_code="TASK-GNSS")
    mapping_repository.update_setting(Decimal("0.7000"), username="admin")

    item = BillItem(
        sequence="1.1",
        item_code=None,
        item_name="设GNSS",
        feature_text="",
        unit="套",
        quantity=Decimal("10"),
        original_unit_price=None,
        original_total_price=None,
        work_content=None,
        remark=None,
        source=SourceRef("sample.xlsx", "Sheet1", 5),
    )

    service = PricingApplicationService(
        feature_parser=FeatureParser(),
        pricing_engine=PricingEngine(
            [
                PriceRule(
                    rule_id="R-GNSS",
                    item_name_contains="GNSS设备",
                    unit="套",
                    feature_conditions={},
                    unit_price=Decimal("13950"),
                    source="test",
                    version="v1",
                )
            ]
        ),
        validator=PricingValidator(),
        item_mapping_repository=mapping_repository,
    )

    result = service.process([item])[0]

    assert result.item.item_mapping_status == "low_confidence"
    assert result.quote.unit_price is None
    assert result.issues[0].code == "ITEM_MAPPING_AMBIGUOUS"
    assert result.item.item_mapping_candidates[0]["standard_item_name"] == "GNSS设备"
    assert mapping_repository.has_pending_reviews_for_task("TASK-GNSS")
