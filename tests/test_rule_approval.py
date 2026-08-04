from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from boq_pricing.domain import PriceRule
from boq_pricing.infrastructure.db import Base
from boq_pricing.infrastructure.rule_approval import RuleApprovalRepository
from boq_pricing.infrastructure.sqlalchemy_rules import SqlAlchemyPriceRuleRepository


def test_rule_approval_flow_controls_active_rules():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    approval = RuleApprovalRepository(session_factory)

    approval.create_draft(
        PriceRule(
            rule_id="APPROVAL-1",
            item_name_contains="测试清单",
            unit="m",
            feature_conditions={"规格": "A"},
            unit_price=Decimal("12.3"),
            source="test",
            version="v1",
        ),
        username="estimator",
    )

    assert SqlAlchemyPriceRuleRepository(session_factory).load() == []

    approval.submit("APPROVAL-1", "v1", "estimator")
    approval.approve("APPROVAL-1", "v1", "reviewer", "ok")

    active_rules = SqlAlchemyPriceRuleRepository(session_factory).load()
    assert len(active_rules) == 1
    assert active_rules[0].rule_id == "APPROVAL-1"


def test_approving_new_version_deactivates_previous_active_version():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    approval = RuleApprovalRepository(session_factory)

    for version, price in [("v1", "10"), ("v2", "12")]:
        approval.create_draft(
            PriceRule(
                rule_id="SAME-RULE",
                item_name_contains="test item",
                unit="m",
                feature_conditions={},
                unit_price=Decimal(price),
                source="test",
                version=version,
            ),
            username="estimator",
        )
        approval.submit("SAME-RULE", version, "estimator")
        approval.approve("SAME-RULE", version, "reviewer", "ok")

    active_rules = SqlAlchemyPriceRuleRepository(session_factory).load()
    assert len(active_rules) == 1
    assert active_rules[0].rule_id == "SAME-RULE"
    assert active_rules[0].version == "v2"
    assert active_rules[0].unit_price == Decimal("12")


def test_bulk_review_supports_multiple_reviewing_rules():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    approval = RuleApprovalRepository(session_factory)

    for index in range(3):
        approval.create_draft(
            PriceRule(
                rule_id=f"BULK-APPROVAL-{index}",
                item_name_contains=f"item {index}",
                unit="m",
                feature_conditions={},
                unit_price=Decimal("10") + index,
                source="test",
                version="v1",
            ),
            username="estimator",
        )
        approval.submit(f"BULK-APPROVAL-{index}", "v1", "estimator")

    approval.approve("BULK-APPROVAL-0", "v1", "reviewer", "ok")
    approval.reject("BULK-APPROVAL-1", "v1", "reviewer", "missing source")

    rows = approval.list_rules()
    statuses = {row.rule_code: row.status for row in rows}
    assert statuses["BULK-APPROVAL-0"] == "active"
    assert statuses["BULK-APPROVAL-1"] == "rejected"
    assert statuses["BULK-APPROVAL-2"] == "reviewing"
