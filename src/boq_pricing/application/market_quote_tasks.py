from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from boq_pricing.infrastructure import (
    ExcelMarketQuoteService,
    MarketQuoteRepository,
    ModelCallLogRepository,
    PlatformConfigRepository,
    create_market_quote_provider,
)
from boq_pricing.infrastructure.pricing_tasks import PricingTaskRepository


class MarketQuoteExcelTaskRunner:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        output_dir: Path,
    ) -> None:
        self._session_factory = session_factory
        self._output_dir = output_dir

    def run(
        self,
        tenant_code: str,
        task_code: str,
        provider: str,
        region: str | None,
        price_month: str | None,
        standard: str | None,
        limit: int,
    ) -> None:
        repository = PricingTaskRepository(self._session_factory)
        task = repository.get(tenant_code, task_code)
        if task is None:
            return
        try:
            repository.mark_market_quote_running(tenant_code, task_code)
            provider_config = PlatformConfigRepository(
                self._session_factory,
                tenant_code=tenant_code,
            ).get_active_provider_config(provider)
            quote_provider = create_market_quote_provider(provider, config=provider_config)

            def on_progress(
                progress: int,
                item_count: int,
                quoted_count: int,
                failed_count: int,
                message: str,
            ) -> None:
                repository.update_progress(
                    tenant_code,
                    task_code,
                    progress=progress,
                    message=message,
                    item_count=item_count,
                    priced_count=quoted_count,
                    unpriced_count=failed_count,
                )

            summary = ExcelMarketQuoteService(
                provider=quote_provider,
                repository=MarketQuoteRepository(self._session_factory, tenant_code=tenant_code),
                output_dir=self._output_dir / "market-quotes",
                call_log_repository=ModelCallLogRepository(self._session_factory, tenant_code=tenant_code),
                task_code=task_code,
            ).quote_workbook(
                input_path=Path(task.upload_path),
                username="estimator",
                region=region,
                price_month=price_month,
                standard=standard,
                limit=limit,
                progress_callback=on_progress,
                cancel_checker=lambda: repository.is_canceled(tenant_code, task_code),
            )
            if repository.is_canceled(tenant_code, task_code):
                repository.update_progress(
                    tenant_code,
                    task_code,
                    progress=100,
                    message=f"任务已停止，已生成部分结果：{summary.output_path}",
                    item_count=summary.item_count,
                    priced_count=summary.quoted_count,
                    unpriced_count=summary.failed_count,
                )
                return
            repository.mark_succeeded(
                tenant_code=tenant_code,
                task_code=task_code,
                item_count=summary.item_count,
                priced_count=summary.quoted_count,
                unpriced_count=summary.failed_count,
                excel_path=summary.output_path,
                missing_rules_path="",
                audit_path="",
                mysql_run_code=None,
                message=(
                    f"询价完成：已入库 {summary.quoted_count} 条，失败 {summary.failed_count} 条。"
                    f"结果文件：{summary.output_path}"
                ),
            )
        except Exception as exc:
            repository.mark_failed(tenant_code, task_code, str(exc))
