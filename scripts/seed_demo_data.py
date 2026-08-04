from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import delete, select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from boq_pricing.config import load_settings  # noqa: E402
from boq_pricing.infrastructure.db import DatabaseConfig, create_session_factory, session_scope  # noqa: E402
from boq_pricing.infrastructure.item_mappings import ItemMappingInput, ItemMappingRepository  # noqa: E402
from boq_pricing.infrastructure.orm_models import (  # noqa: E402
    ItemMappingORM,
    ItemMappingReviewORM,
    PriceRuleORM,
)
from boq_pricing.infrastructure.sqlalchemy_rules import SqlAlchemyPriceRuleRepository  # noqa: E402


TENANT = "default"
DEMO_DIR = ROOT / "outputs" / "demo"
DEMO_WORKBOOK = DEMO_DIR / "计价工作台模拟清单.xlsx"


def main() -> None:
    settings = load_settings()
    session_factory = create_session_factory(DatabaseConfig.from_settings(settings))
    cleanup_demo_data(session_factory)

    rule_repository = SqlAlchemyPriceRuleRepository(session_factory, tenant_code=TENANT)
    seed_price_rules(rule_repository)

    mapping_repository = ItemMappingRepository(session_factory, tenant_code=TENANT)
    mapping_repository.update_setting(Decimal("0.8500"), username="demo-seed")
    seed_mapping_results(mapping_repository)
    seed_pending_reviews(session_factory)
    create_demo_workbook()

    print("演示数据已准备完成：")
    print("  1. 价格规则版本：DEMO-2026-07")
    print("  2. 自动映射阈值：85%")
    print("  3. 映射校准页面：包含待校准和已沉淀数据")
    print(f"  4. 计价工作台样例 Excel：{DEMO_WORKBOOK}")
    print("建议测试顺序：")
    print("  - 登录 admin / admin123")
    print("  - 打开 映射校准 页面查看待校准记录")
    print("  - 打开 计价工作台 上传样例 Excel，价库规则版本选择 DEMO-2026-07")
    print("  - 低置信度项会进入人工校准，校准后重新计价")


def cleanup_demo_data(session_factory) -> None:
    with session_scope(session_factory) as session:
        demo_rule_ids = ["DEMO-PHC-300", "DEMO-GALVANIZED-PIPE", "DEMO-WATER-GAUGE"]
        demo_mapping_codes = ["DEMO-MAP-PHC-PIPE", "DEMO-MAP-WATER-GAUGE"]
        session.execute(delete(PriceRuleORM).where(PriceRuleORM.tenant_code == TENANT, PriceRuleORM.rule_code.in_(demo_rule_ids)))
        session.execute(delete(ItemMappingORM).where(ItemMappingORM.tenant_code == TENANT, ItemMappingORM.mapping_code.like("DEMO-%")))
        session.execute(delete(ItemMappingORM).where(ItemMappingORM.tenant_code == TENANT, ItemMappingORM.mapping_code.in_(demo_mapping_codes)))
        session.execute(delete(ItemMappingReviewORM).where(ItemMappingReviewORM.tenant_code == TENANT, ItemMappingReviewORM.review_code.like("DEMO-%")))


def seed_price_rules(repository: SqlAlchemyPriceRuleRepository) -> None:
    repository.upsert_rule(
        rule_code="DEMO-PHC-300",
        version="DEMO-2026-07",
        status="active",
        item_name_contains="PHC管桩",
        unit="m",
        unit_price=Decimal("88.00"),
        source="演示价库：PHC管桩含税到工地参考价",
        feature_conditions={
            "桩型": "PHC-300-AB-70",
            "混凝土种类与强度等级": "C80",
            "单节长度": "8-10m",
        },
        region_code="CN",
        specialty="桩基",
        cost_category="桩基工程",
        match_priority=10,
        active=True,
        username="demo-seed",
    )
    repository.upsert_rule(
        rule_code="DEMO-GALVANIZED-PIPE",
        version="DEMO-2026-07",
        status="active",
        item_name_contains="镀锌钢管",
        unit="m",
        unit_price=Decimal("58.35"),
        source="演示价库：DN80镀锌钢管综合单价",
        feature_conditions={"规格": "DN80", "技术标准编号": "GB/T3091-2015"},
        region_code="CN",
        specialty="安装",
        cost_category="设备安装",
        match_priority=20,
        active=True,
        username="demo-seed",
    )
    repository.upsert_rule(
        rule_code="DEMO-WATER-GAUGE",
        version="DEMO-2026-07",
        status="active",
        item_name_contains="水尺",
        unit="m",
        unit_price=Decimal("25.00"),
        source="演示价库：不锈钢水尺市场价",
        feature_conditions={"材质": "不锈钢"},
        region_code="CN",
        specialty="安装",
        cost_category="设备安装",
        match_priority=30,
        active=True,
        username="demo-seed",
    )


def seed_mapping_results(repository: ItemMappingRepository) -> None:
    repository.upsert(
        ItemMappingInput(
            mapping_code="DEMO-MAP-PHC-PIPE",
            source_item_name="预制管桩",
            standard_item_name="PHC管桩",
            match_keywords=["PHC", "管桩", "预制"],
            unit="m",
            feature_conditions={
                "桩型": "PHC-300-AB-70",
                "混凝土种类与强度等级": "C80",
                "单节长度": "8-10m",
            },
            status="active",
            priority=10,
            active=True,
        ),
        username="demo-seed",
    )
    repository.upsert(
        ItemMappingInput(
            mapping_code="DEMO-MAP-WATER-GAUGE",
            source_item_name="水尺",
            standard_item_name="水尺",
            match_keywords=["不锈钢", "水尺"],
            unit="m",
            feature_conditions={"材质": "不锈钢"},
            status="active",
            priority=20,
            active=True,
        ),
        username="demo-seed",
    )


def seed_pending_reviews(session_factory) -> None:
    with session_scope(session_factory) as session:
        session.add_all(
            [
                ItemMappingReviewORM(
                    tenant_code=TENANT,
                    review_code="DEMO-REVIEW-LOW-PHC",
                    workbook_name=DEMO_WORKBOOK.name,
                    source_sheet="建筑工程",
                    source_row_number=4,
                    source_item_name="PHC桩",
                    unit="m",
                    feature_json={
                        "桩型": "PHC-300-AB-70",
                        "混凝土种类与强度等级": "C80",
                        "单节长度": "8-10m",
                    },
                    candidate_json=[
                        {
                            "mapping_code": "DEMO-MAP-PHC-PIPE",
                            "standard_item_name": "PHC管桩",
                            "score": 0.25,
                            "reason": "关键词命中；单位匹配；低于85%阈值",
                        }
                    ],
                    status="pending",
                ),
                ItemMappingReviewORM(
                    tenant_code=TENANT,
                    review_code="DEMO-REVIEW-AMBIGUOUS-PILE",
                    workbook_name=DEMO_WORKBOOK.name,
                    source_sheet="建筑工程",
                    source_row_number=5,
                    source_item_name="预制钢筋混凝土桩",
                    unit="m",
                    feature_json={"桩型": "PHC-300-AB-70", "混凝土种类与强度等级": "C80"},
                    candidate_json=[
                        {
                            "mapping_code": "DEMO-MAP-PHC-PIPE",
                            "standard_item_name": "PHC管桩",
                            "score": 0.82,
                            "reason": "名称相近；特征接近",
                        },
                        {
                            "mapping_code": "DEMO-MAP-SQUARE-PILE",
                            "standard_item_name": "预制方桩",
                            "score": 0.78,
                            "reason": "名称相近；候选分数接近",
                        },
                    ],
                    status="pending",
                ),
            ]
        )


def create_demo_workbook() -> None:
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "建筑工程"
    headers = ["序号", "项目名称", "项目特征", "计量单位", "工程量", "综合单价", "合价", "备注"]
    sheet.append(headers)
    sheet.append(
        [
            "1.1",
            "预制管桩",
            "1.桩型：PHC-300-AB-70\n2.单节长度：8-10m\n3.混凝土种类与强度等级：C80",
            "m",
            1200,
            None,
            None,
            "应自动映射为PHC管桩并取价",
        ]
    )
    sheet.append(
        [
            "1.2",
            "PHC桩",
            "桩型：PHC-300-AB-70\n单节长度：8-10m\n混凝土种类与强度等级：C80",
            "m",
            300,
            None,
            None,
            "低置信度，进入人工校准",
        ]
    )
    sheet.append(
        [
            "2.1",
            "水尺",
            "材质：不锈钢；规格：100cm×8cm×1cm（长×宽×厚）。",
            "m",
            119,
            None,
            None,
            "应自动取价",
        ]
    )
    sheet.append(
        [
            "2.2",
            "镀锌钢管",
            "材质：镀锌钢管；规格：DN80×t3.25；技术规格应满足《低压流体输送用焊接钢管》GB/T3091-2015。",
            "m",
            90,
            None,
            None,
            "直接按规则命中",
        ]
    )
    for column in "ABCDEFGH":
        sheet.column_dimensions[column].width = 18
    sheet.column_dimensions["C"].width = 52
    sheet.column_dimensions["H"].width = 28
    workbook.save(DEMO_WORKBOOK)


if __name__ == "__main__":
    main()
