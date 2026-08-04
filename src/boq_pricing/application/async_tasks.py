from __future__ import annotations

import os
import time
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from boq_pricing.application.batch import PricingBatchRequest, PricingBatchService
from boq_pricing.domain import PriceRule, PricingResult
from boq_pricing.infrastructure import (
    MarketQuoteProviderError,
    MarketQuoteRepository,
    MarketQuoteRequest,
    ModelCallLogRepository,
    MySqlCliClient,
    PlatformConfigRepository,
    SqlAlchemyPriceRuleRepository,
    create_market_quote_provider,
)
from boq_pricing.infrastructure.market_quote_excel import (
    supplier_result_to_market_quote_result,
    validate_supplier_quote_result,
)
from boq_pricing.infrastructure.pricing_tasks import PricingTaskRepository

AUTO_MARKET_QUOTE_LIMIT = max(0, int(os.getenv("BOQ_AUTO_MARKET_QUOTE_LIMIT", "0")))


class PricingTaskRunner:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        mysql_client: MySqlCliClient,
        output_dir: Path,
    ) -> None:
        self._session_factory = session_factory
        self._mysql_client = mysql_client
        self._output_dir = output_dir

    def run(self, tenant_code: str, task_code: str) -> None:
        repository = PricingTaskRepository(self._session_factory)
        task = repository.get(tenant_code, task_code)
        if task is None:
            return
        if task.status == "canceled":
            return
        try:
            repository.mark_running(tenant_code, task_code)
            rules = self._load_rules(task, tenant_code)
            response = PricingBatchService().run(
                PricingBatchRequest(
                    input_path=Path(task.upload_path),
                    output_dir=self._output_dir,
                    rules=rules,
                    rule_source="mysql",
                    tenant_code=tenant_code,
                    task_code=task_code,
                    project_name=task.project_name,
                    region_code=task.region_code,
                    write_mysql_audit=True,
                    mysql_client=self._mysql_client,
                    session_factory=self._session_factory,
                )
            )
            if repository.is_canceled(tenant_code, task_code):
                return

            if response.issue_counts.get("ITEM_MAPPING_AMBIGUOUS"):
                repository.mark_waiting_mapping(
                    tenant_code=tenant_code,
                    task_code=task_code,
                    item_count=response.item_count,
                    priced_count=response.priced_count,
                    unpriced_count=response.unpriced_count,
                    excel_path=str(response.excel_path),
                    missing_rules_path=str(response.missing_rules_path),
                    audit_path=str(response.audit_path),
                    mysql_run_code=response.mysql_run_code,
                )
                return

            if response.issue_counts.get("NO_PRICE_RULE"):
                repository.update_progress(
                    tenant_code,
                    task_code,
                    progress=70,
                    message="规则库缺少价格，正在进入市场询价支路",
                    item_count=response.item_count,
                    priced_count=response.priced_count,
                    unpriced_count=response.unpriced_count,
                )
                if repository.is_canceled(tenant_code, task_code):
                    return
                quote_count, quote_errors = self._create_market_quote_reviews(
                    tenant_code,
                    task_code,
                    task,
                    response.results,
                    repository,
                    response.item_count,
                    response.priced_count,
                    response.unpriced_count,
                )
                if repository.is_canceled(tenant_code, task_code):
                    return
                repository.mark_waiting_market_quote(
                    tenant_code=tenant_code,
                    task_code=task_code,
                    item_count=response.item_count,
                    priced_count=response.priced_count,
                    unpriced_count=response.unpriced_count,
                    excel_path=str(response.excel_path),
                    missing_rules_path=str(response.missing_rules_path),
                    audit_path=str(response.audit_path),
                    mysql_run_code=response.mysql_run_code,
                    quote_count=quote_count,
                    error_message=quote_errors[-1] if quote_errors else None,
                )
                return

            repository.mark_succeeded(
                tenant_code=tenant_code,
                task_code=task_code,
                item_count=response.item_count,
                priced_count=response.priced_count,
                unpriced_count=response.unpriced_count,
                excel_path=str(response.excel_path),
                missing_rules_path=str(response.missing_rules_path),
                audit_path=str(response.audit_path),
                mysql_run_code=response.mysql_run_code,
            )
        except Exception as exc:
            repository.mark_failed(tenant_code, task_code, str(exc))

    def _load_rules(self, task, tenant_code: str) -> list[PriceRule]:
        repository = SqlAlchemyPriceRuleRepository(
            self._session_factory,
            tenant_code=tenant_code,
        )
        rules = repository.load(
            version=task.rule_version,
            region_code=task.region_code,
            specialty=task.specialty,
            cost_category=task.cost_category,
        )
        if task.rule_version:
            market_rules = repository.load(
                version="market-adopted",
                region_code=task.region_code,
                specialty=task.specialty,
                cost_category=task.cost_category,
            )
            seen = {(rule.rule_id, rule.version) for rule in rules}
            rules.extend(rule for rule in market_rules if (rule.rule_id, rule.version) not in seen)
        return rules

    def _create_market_quote_reviews(
        self,
        tenant_code: str,
        task_code: str,
        task,
        results: list[PricingResult],
        task_repository: PricingTaskRepository,
        item_count: int,
        priced_count: int,
        unpriced_count: int,
    ) -> tuple[int, list[str]]:
        provider = "doubao"
        provider_config = PlatformConfigRepository(
            self._session_factory,
            tenant_code=tenant_code,
        ).get_active_provider_config(provider)
        quote_provider = create_market_quote_provider(provider, config=provider_config)
        repository = MarketQuoteRepository(
            self._session_factory,
            tenant_code=tenant_code,
            pricing_task_code=task_code,
        )
        call_logs = ModelCallLogRepository(self._session_factory, tenant_code=tenant_code)
        created = 0
        errors: list[str] = []
        seen_keys: set[tuple[str, str | None, str | None, tuple[tuple[str, str], ...]]] = set()
        quote_targets: list[tuple[PricingResult, str, dict[str, str]]] = []
        for result in results:
            if result.quote.unit_price is not None:
                continue
            if not any(issue.code == "NO_PRICE_RULE" for issue in result.issues):
                continue
            if any(issue.code == "ITEM_MAPPING_AMBIGUOUS" for issue in result.issues):
                continue
            item = result.item
            features = dict(item.features.values if item.features else {})
            quote_item_name = item.standard_item_name or item.item_name
            key = (quote_item_name, item.unit, task.region_code, tuple(sorted(features.items())))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            quote_targets.append((result, quote_item_name, features))

        if not quote_targets:
            return 0, errors
        if AUTO_MARKET_QUOTE_LIMIT <= 0:
            return 0, [f"已进入市场询价支路；当前 BOQ_AUTO_MARKET_QUOTE_LIMIT=0，未自动调用模型。"]

        limited_targets = quote_targets[:AUTO_MARKET_QUOTE_LIMIT]
        skipped_count = len(quote_targets) - len(limited_targets)
        if skipped_count > 0:
            errors.append(f"工作台自动询价最多尝试 {AUTO_MARKET_QUOTE_LIMIT} 项，剩余 {skipped_count} 项请在市场询价页面批量处理。")

        for index, (result, quote_item_name, features) in enumerate(limited_targets, start=1):
            item = result.item
            if task_repository.is_canceled(tenant_code, task_code):
                return created, errors
            task_repository.update_progress(
                tenant_code,
                task_code,
                progress=min(88, 70 + int(index / max(len(limited_targets), 1) * 18)),
                message=f"正在自动询价第 {index}/{len(limited_targets)} 项：{quote_item_name}",
                item_count=item_count,
                priced_count=priced_count,
                unpriced_count=unpriced_count,
            )
            call_code = None
            call_finished = False
            started = time.monotonic()
            try:
                call_code = call_logs.start(
                    provider=quote_provider.provider_name,
                    model=quote_provider.model,
                    scenario="pricing_auto_market_quote",
                    task_code=task_code,
                    item_name=quote_item_name,
                    username="system",
                )
                supplier_result = quote_provider.quote_suppliers(
                    MarketQuoteRequest(
                        item_name=quote_item_name,
                        unit=item.unit,
                        features=features,
                        region=task.region_code,
                        item_code=item.item_code,
                        quantity=str(item.quantity) if item.quantity is not None else None,
                        work_content=item.work_content,
                        remark=item.remark,
                    )
                )
                if task_repository.is_canceled(tenant_code, task_code):
                    if call_code is not None:
                        call_logs.fail(
                            call_code,
                            duration_ms=int((time.monotonic() - started) * 1000),
                            error_message="pricing task canceled after model response",
                            response_excerpt=supplier_result.raw_response,
                        )
                    return created, errors
                validate_supplier_quote_result(supplier_result)
                call_logs.succeed(
                    call_code,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    token_usage=supplier_result.assumptions.get("token_usage"),
                    response_excerpt=supplier_result.raw_response,
                )
                call_finished = True
                repository.save(
                    supplier_result_to_market_quote_result(supplier_result),
                    username="system",
                )
                created += 1
            except MarketQuoteProviderError as exc:
                if call_code is not None and not call_finished:
                    call_logs.fail(
                        call_code,
                        duration_ms=int((time.monotonic() - started) * 1000),
                        error_message=str(exc),
                    )
                errors.append(f"{quote_item_name}: {exc}")
                continue
            except Exception as exc:
                if call_code is not None and not call_finished:
                    call_logs.fail(
                        call_code,
                        duration_ms=int((time.monotonic() - started) * 1000),
                        error_message=str(exc),
                    )
                errors.append(f"{quote_item_name}: {exc}")
                continue
        return created, errors
