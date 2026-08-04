from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from boq_pricing.infrastructure.db import session_scope
from boq_pricing.infrastructure.orm_models import PricingTaskORM


@dataclass(frozen=True)
class PricingTaskCreate:
    tenant_code: str
    task_code: str
    workbook_name: str
    upload_path: str
    project_name: str | None = None
    region_code: str | None = None
    specialty: str | None = None
    cost_category: str | None = None
    rule_version: str | None = None


class PricingTaskRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create(self, payload: PricingTaskCreate) -> PricingTaskORM:
        with session_scope(self._session_factory) as session:
            task = PricingTaskORM(
                tenant_code=payload.tenant_code,
                task_code=payload.task_code,
                workbook_name=payload.workbook_name,
                upload_path=payload.upload_path,
                project_name=payload.project_name,
                region_code=payload.region_code,
                specialty=payload.specialty,
                cost_category=payload.cost_category,
                rule_version=payload.rule_version,
                status="pending",
                progress=0,
                message="任务已创建，等待处理",
            )
            session.add(task)
            session.flush()
            session.expunge(task)
            return task

    def get(self, tenant_code: str, task_code: str) -> PricingTaskORM | None:
        with session_scope(self._session_factory) as session:
            task = session.scalar(
                select(PricingTaskORM).where(
                    PricingTaskORM.tenant_code == tenant_code,
                    PricingTaskORM.task_code == task_code,
                )
            )
            if task is not None:
                session.expunge(task)
            return task

    def mark_running(self, tenant_code: str, task_code: str) -> None:
        self._update(
            tenant_code,
            task_code,
            status="running",
            progress=15,
            message="正在读取清单并匹配价格规则",
            started_at=datetime.now(UTC),
        )

    def mark_pending(self, tenant_code: str, task_code: str, message: str = "任务已恢复，等待重新计价") -> None:
        self._update(
            tenant_code,
            task_code,
            status="pending",
            progress=0,
            message=message[:512],
            started_at=None,
            finished_at=None,
        )

    def mark_market_quote_running(self, tenant_code: str, task_code: str) -> None:
        self._update(
            tenant_code,
            task_code,
            status="running",
            progress=5,
            message="正在读取询价表并准备调用模型",
            started_at=datetime.now(UTC),
        )

    def update_progress(
        self,
        tenant_code: str,
        task_code: str,
        progress: int,
        message: str,
        item_count: int = 0,
        priced_count: int = 0,
        unpriced_count: int = 0,
    ) -> None:
        self._update(
            tenant_code,
            task_code,
            progress=max(0, min(progress, 99)),
            message=message[:512],
            item_count=item_count,
            priced_count=priced_count,
            unpriced_count=unpriced_count,
        )

    def mark_succeeded(
        self,
        tenant_code: str,
        task_code: str,
        item_count: int,
        priced_count: int,
        unpriced_count: int,
        excel_path: str,
        missing_rules_path: str,
        audit_path: str,
        mysql_run_code: str | None,
        message: str = "计价完成",
    ) -> None:
        self._update(
            tenant_code,
            task_code,
            status="succeeded",
            progress=100,
            message=message[:512],
            item_count=item_count,
            priced_count=priced_count,
            unpriced_count=unpriced_count,
            excel_path=excel_path,
            missing_rules_path=missing_rules_path,
            audit_path=audit_path,
            mysql_run_code=mysql_run_code,
            finished_at=datetime.now(UTC),
        )

    def mark_waiting_mapping(
        self,
        tenant_code: str,
        task_code: str,
        item_count: int,
        priced_count: int,
        unpriced_count: int,
        excel_path: str,
        missing_rules_path: str,
        audit_path: str,
        mysql_run_code: str | None,
    ) -> None:
        self._update(
            tenant_code,
            task_code,
            status="waiting_mapping",
            progress=85,
            message="存在低置信度或歧义清单映射，已进入映射校准；校准完成后系统会自动继续计价。",
            item_count=item_count,
            priced_count=priced_count,
            unpriced_count=unpriced_count,
            excel_path=excel_path,
            missing_rules_path=missing_rules_path,
            audit_path=audit_path,
            mysql_run_code=mysql_run_code,
        )

    def mark_waiting_market_quote(
        self,
        tenant_code: str,
        task_code: str,
        item_count: int,
        priced_count: int,
        unpriced_count: int,
        excel_path: str,
        missing_rules_path: str,
        audit_path: str,
        mysql_run_code: str | None,
        quote_count: int,
        error_message: str | None = None,
    ) -> None:
        if quote_count > 0:
            message = f"规则库缺少 {unpriced_count} 个清单项价格，已生成 {quote_count} 条市场询价复核记录；复核通过后系统会自动继续计价。"
        else:
            message = "规则库缺少价格，自动市场询价暂未生成可复核报价；请检查平台模型配置/联网搜索/API Key，或先在市场询价页面手动询价后复核。"
        if error_message:
            message = f"{message} 最近错误：{error_message}"
        self._update(
            tenant_code,
            task_code,
            status="waiting_market_quote",
            progress=90,
            message=message[:512],
            item_count=item_count,
            priced_count=priced_count,
            unpriced_count=unpriced_count,
            excel_path=excel_path,
            missing_rules_path=missing_rules_path,
            audit_path=audit_path,
            mysql_run_code=mysql_run_code,
        )

    def mark_failed(self, tenant_code: str, task_code: str, message: str) -> None:
        self._update(
            tenant_code,
            task_code,
            status="failed",
            progress=100,
            message=message[:512],
            finished_at=datetime.now(UTC),
        )

    def mark_canceled(self, tenant_code: str, task_code: str, message: str = "任务已停止") -> None:
        self._update(
            tenant_code,
            task_code,
            status="canceled",
            progress=100,
            message=message[:512],
            finished_at=datetime.now(UTC),
        )

    def is_canceled(self, tenant_code: str, task_code: str) -> bool:
        task = self.get(tenant_code, task_code)
        return task is not None and task.status == "canceled"

    def list_recent(self, tenant_code: str, limit: int = 20) -> list[PricingTaskORM]:
        with session_scope(self._session_factory) as session:
            rows = session.scalars(
                select(PricingTaskORM)
                .where(PricingTaskORM.tenant_code == tenant_code)
                .order_by(PricingTaskORM.id.desc())
                .limit(limit)
            ).all()
            for row in rows:
                session.expunge(row)
            return list(rows)

    def _update(self, tenant_code: str, task_code: str, **values: object) -> None:
        with session_scope(self._session_factory) as session:
            task = session.scalar(
                select(PricingTaskORM).where(
                    PricingTaskORM.tenant_code == tenant_code,
                    PricingTaskORM.task_code == task_code,
                )
            )
            if task is None:
                return
            for key, value in values.items():
                setattr(task, key, value)
