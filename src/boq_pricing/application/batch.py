from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from boq_pricing.application import PricingApplicationService
from boq_pricing.domain import PriceRule, PricingResult
from boq_pricing.infrastructure import (
    ExcelBillReader,
    ExcelMissingRuleTemplateWriter,
    ExcelResultWriter,
    JsonAuditWriter,
    MySqlCliClient,
    MySqlPricingAuditWriter,
    ItemMappingRepository,
    SqlAlchemyPricingAuditWriter,
)
from boq_pricing.parsing import FeatureParser
from boq_pricing.pricing import PricingEngine
from boq_pricing.validation import PricingValidator
from sqlalchemy.orm import Session, sessionmaker


@dataclass(frozen=True)
class PricingBatchRequest:
    input_path: Path
    output_dir: Path
    rules: list[PriceRule]
    rule_source: str
    tenant_code: str = "default"
    task_code: str | None = None
    project_name: str | None = None
    region_code: str | None = None
    write_mysql_audit: bool = False
    mysql_client: MySqlCliClient | None = None
    session_factory: sessionmaker[Session] | None = None


@dataclass(frozen=True)
class PricingBatchResponse:
    item_count: int
    priced_count: int
    unpriced_count: int
    issue_counts: dict[str, int]
    excel_path: Path
    missing_rules_path: Path
    audit_path: Path
    mysql_run_code: str | None
    results: list[PricingResult]


class PricingBatchService:
    def run(self, request: PricingBatchRequest) -> PricingBatchResponse:
        request.output_dir.mkdir(parents=True, exist_ok=True)
        items = ExcelBillReader().read(request.input_path)
        item_mapping_repository = None
        if request.session_factory is not None:
            item_mapping_repository = ItemMappingRepository(
                request.session_factory,
                tenant_code=request.tenant_code,
                pricing_task_code=request.task_code,
            )

        service = PricingApplicationService(
            feature_parser=FeatureParser(),
            pricing_engine=PricingEngine(request.rules),
            validator=PricingValidator(),
            item_mapping_repository=item_mapping_repository,
        )
        results = service.process(items)

        stem = request.input_path.stem
        excel_path = request.output_dir / f"{stem}.priced.xlsx"
        audit_path = request.output_dir / f"{stem}.audit.json"
        missing_rules_path = request.output_dir / f"{stem}.missing_rules.xlsx"
        ExcelResultWriter().write(results, excel_path, source_path=request.input_path)
        ExcelMissingRuleTemplateWriter().write(results, missing_rules_path)
        JsonAuditWriter().write([result.to_dict() for result in results], audit_path)

        mysql_run_code = None
        if request.write_mysql_audit:
            if request.session_factory is not None:
                mysql_run_code = SqlAlchemyPricingAuditWriter(
                    request.session_factory,
                    tenant_code=request.tenant_code,
                ).write_run(
                    workbook_path=request.input_path,
                    rule_source=request.rule_source,
                    results=results,
                    project_name=request.project_name,
                    region_code=request.region_code,
                )
            else:
                if request.mysql_client is None:
                    raise ValueError("mysql_client or session_factory is required when write_mysql_audit is true")
                mysql_run_code = MySqlPricingAuditWriter(
                    request.mysql_client,
                    tenant_code=request.tenant_code,
                ).write_run(
                    workbook_path=request.input_path,
                    rule_source=request.rule_source,
                    results=results,
                    project_name=request.project_name,
                    region_code=request.region_code,
                )

        issue_counts: dict[str, int] = {}
        for result in results:
            for issue in result.issues:
                issue_counts[issue.code] = issue_counts.get(issue.code, 0) + 1

        priced_count = sum(1 for result in results if result.quote.unit_price is not None)
        return PricingBatchResponse(
            item_count=len(results),
            priced_count=priced_count,
            unpriced_count=len(results) - priced_count,
            issue_counts=issue_counts,
            excel_path=excel_path,
            missing_rules_path=missing_rules_path,
            audit_path=audit_path,
            mysql_run_code=mysql_run_code,
            results=results,
        )
