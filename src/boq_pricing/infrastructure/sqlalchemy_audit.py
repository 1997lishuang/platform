from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from boq_pricing.domain import PricingResult
from boq_pricing.infrastructure.db import session_scope
from boq_pricing.infrastructure.orm_models import PricingResultORM, PricingRunORM
from boq_pricing.pricing.calculations import calculate_total_price


class SqlAlchemyPricingAuditWriter:
    def __init__(self, session_factory: sessionmaker[Session], tenant_code: str = "default") -> None:
        self._session_factory = session_factory
        self._tenant_code = tenant_code

    def write_run(
        self,
        workbook_path: str | Path,
        rule_source: str,
        results: list[PricingResult],
        project_name: str | None = None,
        region_code: str | None = None,
    ) -> str:
        priced_count = sum(1 for result in results if result.quote.unit_price is not None)
        versions = sorted({result.quote.rule_version for result in results if result.quote.rule_version})
        rule_version = ",".join(versions) if versions else None
        workbook_name = normalize_workbook_name(Path(workbook_path).name)

        with session_scope(self._session_factory) as session:
            run = session.scalar(
                select(PricingRunORM).where(
                    PricingRunORM.tenant_code == self._tenant_code,
                    PricingRunORM.workbook_name == workbook_name,
                    PricingRunORM.project_name == project_name,
                    PricingRunORM.region_code == region_code,
                    PricingRunORM.rule_source == rule_source,
                )
            )
            if run is None:
                run = PricingRunORM(
                    tenant_code=self._tenant_code,
                    run_code=stable_run_code(
                        self._tenant_code,
                        workbook_name,
                        project_name,
                        region_code,
                        rule_source,
                    ),
                    workbook_name=workbook_name,
                    project_name=project_name,
                    region_code=region_code,
                    rule_source=rule_source,
                )
                session.add(run)
            run.rule_version = rule_version
            run.item_count = len(results)
            run.priced_count = priced_count
            run.unpriced_count = len(results) - priced_count
            session.flush()
            session.execute(delete(PricingResultORM).where(PricingResultORM.run_id == run.id))
            session.add_all([to_result_orm(run.id, result) for result in results])
            return str(run.run_code)


def normalize_workbook_name(workbook_name: str) -> str:
    parts = workbook_name.split(".", 1)
    if len(parts) == 2 and is_upload_task_prefix(parts[0]):
        return parts[1]
    return workbook_name


def is_upload_task_prefix(value: str) -> bool:
    lowered = value.lower()
    if len(value) == 32 and all(ch in "0123456789abcdef" for ch in lowered):
        return True
    return lowered.startswith("task-")


def stable_run_code(
    tenant_code: str,
    workbook_name: str,
    project_name: str | None,
    region_code: str | None,
    rule_source: str,
) -> str:
    import hashlib

    key = "|".join([tenant_code, workbook_name, project_name or "", region_code or "", rule_source])
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:32]


def to_result_orm(run_id: int, result: PricingResult) -> PricingResultORM:
    item = result.item
    quote = result.quote
    return PricingResultORM(
        run_id=run_id,
        source_sheet=item.source.sheet,
        source_row_number=item.source.row_number,
        sequence_no=item.sequence,
        item_code=item.item_code,
        item_name=item.item_name,
        unit=item.unit,
        quantity=item.quantity,
        unit_price=quote.unit_price,
        total_price=calculate_total_price(item.quantity, quote.unit_price),
        rule_code=quote.rule_id,
        rule_version=quote.rule_version,
        price_source=quote.source,
        confidence=Decimal(str(quote.confidence)),
        features_json=item.features.values if item.features else {},
        issues_json=[issue.message for issue in result.issues],
    )
