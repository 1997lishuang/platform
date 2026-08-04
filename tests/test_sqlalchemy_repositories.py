from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from boq_pricing.domain import BillItem, FeatureSet, PriceQuote, PriceRule, PricingResult, SourceRef
from boq_pricing.infrastructure.db import Base
from boq_pricing.infrastructure.orm_models import PriceRuleORM, PricingResultORM, PricingRunORM  # noqa: F401
from boq_pricing.infrastructure.item_mappings import ItemMappingInput, ItemMappingRepository
from boq_pricing.infrastructure.platform_configs import PlatformConfigInput, PlatformConfigRepository
from boq_pricing.infrastructure.pricing_tasks import PricingTaskCreate, PricingTaskRepository
from boq_pricing.infrastructure.sqlalchemy_audit import SqlAlchemyPricingAuditWriter
from boq_pricing.infrastructure.sqlalchemy_rules import SqlAlchemyPriceRuleRepository


def test_sqlalchemy_price_rule_repository_upserts_and_loads_rules():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    repository = SqlAlchemyPriceRuleRepository(session_factory)

    repository.upsert_many(
        [
            PriceRule(
                rule_id="R-SQLA",
                item_name_contains="光伏组件安装",
                unit="块",
                feature_conditions={"组件型号": "730Wp"},
                unit_price=Decimal("7.5"),
                source="test",
                version="v1",
            )
        ]
    )

    rules = repository.load()

    assert len(rules) == 1
    assert rules[0].rule_id == "R-SQLA"
    assert rules[0].feature_conditions == {"组件型号": "730Wp"}


def test_item_mapping_repository_detects_ambiguity_and_resolves_review():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    repository = ItemMappingRepository(session_factory, pricing_task_code="TASK-MAP-1")
    item = BillItem(
        sequence="1.1",
        item_code=None,
        item_name="预制钢筋混凝土桩",
        feature_text="桩型：PHC-300-AB-70",
        unit="m",
        quantity=Decimal("10"),
        original_unit_price=None,
        original_total_price=None,
        work_content=None,
        remark=None,
        source=SourceRef("sample.xlsx", "Sheet1", 2),
    )

    repository.upsert(ItemMappingInput("MAP-1", "预制钢筋混凝土桩", "PHC管桩", ["PHC"], "m", {}, "active"))
    repository.upsert(ItemMappingInput("MAP-2", "预制钢筋混凝土桩", "方桩", ["预制"], "m", {}, "active"))

    decision = repository.resolve(item)
    review = repository.create_ambiguity_review(item, decision.candidates)
    assert repository.has_pending_reviews_for_task("TASK-MAP-1")
    resolved = repository.resolve_review(review.review_code, "PHC管桩", "reviewer", create_mapping=True)

    assert decision.status == "ambiguous"
    assert len(decision.candidates) == 2
    assert review.pricing_task_code == "TASK-MAP-1"
    assert resolved.status == "resolved"
    assert not repository.has_pending_reviews_for_task("TASK-MAP-1")


def test_item_mapping_repository_uses_configurable_confidence_threshold():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    repository = ItemMappingRepository(session_factory)
    item = BillItem(
        sequence="1.1",
        item_code=None,
        item_name="PHC桩",
        feature_text="",
        unit="m",
        quantity=Decimal("10"),
        original_unit_price=None,
        original_total_price=None,
        work_content=None,
        remark=None,
        source=SourceRef("sample.xlsx", "Sheet1", 2),
    )
    repository.upsert(ItemMappingInput("MAP-LOW", "预制钢筋混凝土桩", "PHC管桩", ["PHC"], "m", {}, "active"))

    assert repository.resolve(item).status == "low_confidence"

    repository.update_setting(Decimal("0.1000"), username="admin")

    decision = repository.resolve(item)
    assert decision.status == "mapped"
    assert decision.standard_item_name == "PHC管桩"


def test_item_mapping_repository_uses_feature_text_for_candidate_score():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    repository = ItemMappingRepository(session_factory)
    repository.update_setting(Decimal("0.7000"), username="admin")
    item = BillItem(
        sequence="1.1",
        item_code=None,
        item_name="保护管",
        feature_text="用于电力电缆保护",
        unit="m",
        quantity=Decimal("10"),
        original_unit_price=None,
        original_total_price=None,
        work_content=None,
        remark=None,
        source=SourceRef("sample.xlsx", "Sheet1", 2),
    )
    item.features = FeatureSet(item.feature_text, {"用途": "电力电缆保护"})

    repository.upsert(ItemMappingInput("MAP-CABLE", "保护管", "电缆保护管", ["电力", "电缆"], "m", {}, "active"))
    repository.upsert(ItemMappingInput("MAP-COMM", "保护管", "通讯保护管", ["通讯"], "m", {}, "active"))

    decision = repository.resolve(item)

    assert decision.status == "mapped"
    assert decision.standard_item_name == "电缆保护管"
    assert "特征关键词命中" in decision.candidates[0].reason


def test_sqlalchemy_price_rule_repository_crud_and_pagination():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    repository = SqlAlchemyPriceRuleRepository(session_factory)

    for index in range(3):
        repository.upsert_rule(
            rule_code=f"RULE-{index}",
            version="v1",
            status="active",
            item_name_contains=f"预制钢筋混凝土桩{index}",
            unit="m",
            unit_price=Decimal("85") + index,
            source="manual",
            feature_conditions={"桩型": "PHC-300-AB-70"},
            region_code="CN",
            match_priority=20,
            active=True,
            username="admin",
        )

    rows, total = repository.list_page(keyword="预制", page=1, page_size=2)
    assert total == 3
    assert len(rows) == 2

    updated = repository.upsert_rule(
        rule_code="RULE-1",
        version="v1",
        status="active",
        item_name_contains="预制钢筋混凝土桩",
        unit="m",
        unit_price=Decimal("99"),
        source="manual-update",
        feature_conditions={"桩型": "PHC-400-AB-95"},
        region_code="CN",
        match_priority=10,
        active=True,
        username="admin",
    )
    assert updated.unit_price == Decimal("99")
    assert repository.get("RULE-1", "v1") is not None
    assert repository.delete_rule("RULE-1", "v1") is True
    assert repository.get("RULE-1", "v1") is None


def test_sqlalchemy_price_rule_repository_lists_versions():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    repository = SqlAlchemyPriceRuleRepository(session_factory)

    repository.upsert_rule(
        rule_code="RULE-A",
        version="market-adopted",
        status="active",
        item_name_contains="预制钢筋混凝土桩",
        unit="m",
        unit_price=Decimal("85"),
        source="market",
        feature_conditions={},
        active=True,
    )
    repository.upsert_rule(
        rule_code="RULE-B",
        version="excel-import",
        status="draft",
        item_name_contains="水尺",
        unit="m",
        unit_price=Decimal("25"),
        source="excel",
        feature_conditions={},
        active=False,
    )

    assert repository.list_versions(status="active") == [("market-adopted", "active", 1)]
    assert sorted(repository.list_versions()) == [
        ("excel-import", "draft", 1),
        ("market-adopted", "active", 1),
    ]


def test_sqlalchemy_price_rule_repository_lists_identities_and_bulk_deletes():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    repository = SqlAlchemyPriceRuleRepository(session_factory)

    for index in range(3):
        repository.upsert_rule(
            rule_code=f"BULK-{index}",
            version="excel-import-1",
            status="draft" if index < 2 else "active",
            item_name_contains=f"bulk item {index}",
            unit="m",
            unit_price=Decimal("10"),
            source="excel",
            feature_conditions={},
            active=index == 2,
        )

    identities = repository.list_identities(allowed_statuses={"draft"})
    assert sorted(identities) == [("BULK-0", "excel-import-1"), ("BULK-1", "excel-import-1")]

    affected, skipped = repository.delete_rules(identities + [("MISSING", "v1")])
    assert affected == 2
    assert skipped == 1
    rows, total = repository.list_page(page=1, page_size=10)
    assert total == 1
    assert rows[0].rule_code == "BULK-2"


def test_pricing_task_repository_tracks_status():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    repository = PricingTaskRepository(session_factory)

    repository.create(
        PricingTaskCreate(
            tenant_code="default",
            task_code="TASK-1",
            workbook_name="sample.xlsx",
            upload_path="uploads/sample.xlsx",
        )
    )
    repository.mark_running("default", "TASK-1")
    repository.mark_succeeded(
        tenant_code="default",
        task_code="TASK-1",
        item_count=10,
        priced_count=8,
        unpriced_count=2,
        excel_path="outputs/result.xlsx",
        missing_rules_path="outputs/missing.xlsx",
        audit_path="outputs/audit.json",
        mysql_run_code="RUN-1",
    )

    task = repository.get("default", "TASK-1")

    assert task is not None
    assert task.status == "succeeded"
    assert task.progress == 100
    assert task.priced_count == 8
    assert task.mysql_run_code == "RUN-1"

    repository.mark_canceled("default", "TASK-1")
    repository.mark_pending("default", "TASK-1")
    task = repository.get("default", "TASK-1")
    assert task is not None
    assert task.status == "pending"
    assert task.progress == 0

    repository.mark_waiting_market_quote(
        tenant_code="default",
        task_code="TASK-1",
        item_count=10,
        priced_count=6,
        unpriced_count=4,
        excel_path="out.xlsx",
        missing_rules_path="missing.xlsx",
        audit_path="audit.json",
        mysql_run_code="RUN-1",
        quote_count=0,
        error_message="BOQ_AUTO_MARKET_QUOTE_LIMIT=0",
    )
    repository.mark_pending("default", "TASK-1")
    task = repository.get("default", "TASK-1")
    assert task is not None
    assert task.status == "pending"


def test_sqlalchemy_pricing_audit_writer_reuses_same_workbook_run():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    writer = SqlAlchemyPricingAuditWriter(session_factory)

    first_code = writer.write_run(
        workbook_path="uploads/TASK-1.工程招标工程量清单.xlsx",
        rule_source="mysql",
        results=[pricing_result("水尺", Decimal("25"))],
        project_name="中广核叶集区集安200MW光伏项目",
        region_code="CN",
    )
    second_code = writer.write_run(
        workbook_path="uploads/TASK-2.工程招标工程量清单.xlsx",
        rule_source="mysql",
        results=[pricing_result("水尺", Decimal("30"))],
        project_name="中广核叶集区集安200MW光伏项目",
        region_code="CN",
    )

    with session_factory() as session:
        runs = session.scalars(select(PricingRunORM)).all()
        results = session.scalars(select(PricingResultORM)).all()

    assert first_code == second_code
    assert len(runs) == 1
    assert runs[0].workbook_name == "工程招标工程量清单.xlsx"
    assert len(results) == 1
    assert results[0].unit_price == Decimal("30.0000")


def test_platform_config_repository_returns_loaded_row_after_upsert():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    repository = PlatformConfigRepository(session_factory)

    row = repository.upsert(
        PlatformConfigInput(
            provider="doubao",
            display_name="豆包/火山方舟",
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            model="doubao-seed-1-6",
            api_key="secret",
            timeout_seconds=60,
            active=True,
        ),
        username="admin",
    )

    assert row.provider == "doubao"
    assert row.api_key == "secret"
    assert row.updated_at is not None


def pricing_result(item_name: str, unit_price: Decimal) -> PricingResult:
    item = BillItem(
        sequence="1",
        item_code="1.1",
        item_name=item_name,
        feature_text="材质：不锈钢",
        unit="m",
        quantity=Decimal("2"),
        original_unit_price=None,
        original_total_price=None,
        work_content=None,
        remark=None,
        source=SourceRef("工程招标工程量清单.xlsx", "Sheet1", 2),
        features=FeatureSet("材质：不锈钢", {"材质": "不锈钢"}),
    )
    return PricingResult(
        item=item,
        quote=PriceQuote(
            unit_price=unit_price,
            total_price=unit_price * Decimal("2"),
            rule_id="R-1",
            rule_version="v1",
            source="test",
            confidence=0.9,
            matched_conditions={},
        ),
    )


def test_platform_config_repository_forces_responses_when_web_search_enabled():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    repository = PlatformConfigRepository(session_factory)

    repository.upsert(
        PlatformConfigInput(
            provider="doubao",
            display_name="豆包/火山方舟",
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            model="doubao-seed-evolving",
            api_key="secret",
            endpoint_type="chat_completions",
            enable_web_search=True,
            search_tool_type="web_search_preview",
            timeout_seconds=180,
            active=True,
        ),
        username="admin",
    )

    config = repository.get_active_provider_config("doubao")

    assert config is not None
    assert config.endpoint_type == "responses"
    assert config.search_tool_type == "web_search"
