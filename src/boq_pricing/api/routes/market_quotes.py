from __future__ import annotations

import shutil
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select

from boq_pricing.api.auth import CurrentUser, get_current_user, require_permission
from boq_pricing.api.dependencies import get_mysql_client, get_session_factory, get_settings
from boq_pricing.api.schemas import (
    ExcelMarketQuoteResponse,
    MarketQuotePage,
    MarketQuoteRequestPayload,
    MarketQuoteReviewRequest,
    MarketQuoteSummary,
    MarketQuoteTaskTarget,
    PricingTaskAccepted,
    PricingTaskStatus,
)
from boq_pricing.application.market_quote_tasks import MarketQuoteExcelTaskRunner
from boq_pricing.application.async_tasks import PricingTaskRunner
from boq_pricing.infrastructure.market_quote_excel import (
    supplier_result_to_market_quote_result,
    validate_supplier_quote_result,
)
from boq_pricing.infrastructure import (
    ExcelMarketQuoteService,
    MarketQuoteProviderError,
    MarketQuoteRepository,
    MarketQuoteRequest,
    ModelCallLogRepository,
    PlatformConfigRepository,
    PricingTaskCreate,
    PricingTaskRepository,
    create_market_quote_provider,
)
from boq_pricing.api.routes.pricing import to_task_status
from boq_pricing.infrastructure.db import session_scope
from boq_pricing.infrastructure.orm_models import PricingResultORM, PricingRunORM

router = APIRouter(prefix="/market-quotes", tags=["market-quotes"])


@router.post("/estimate", response_model=MarketQuoteSummary, status_code=201)
def estimate_market_quote(
    payload: MarketQuoteRequestPayload,
    tenant_code: str = Query("default"),
    provider: str | None = Query(None),
    user: CurrentUser = Depends(get_current_user),
) -> MarketQuoteSummary:
    require_permission(user, "rule:create")
    session_factory = get_session_factory()
    selected_provider = provider
    provider_config = None
    if selected_provider:
        provider_config = PlatformConfigRepository(
            session_factory,
            tenant_code=tenant_code,
        ).get_active_provider_config(selected_provider)
    quote_provider = create_market_quote_provider(selected_provider, config=provider_config)
    call_logs = ModelCallLogRepository(session_factory, tenant_code=tenant_code)
    call_code = call_logs.start(
        provider=quote_provider.provider_name,
        model=quote_provider.model,
        scenario="single_market_quote",
        item_name=payload.item_name,
        username=user.username,
    )
    started = time.monotonic()
    try:
        supplier_result = quote_provider.quote_suppliers(
            MarketQuoteRequest(
                item_name=payload.item_name,
                unit=payload.unit,
                features=payload.features,
                region=payload.region,
                price_month=payload.price_month,
                standard=payload.standard,
            )
        )
        validate_supplier_quote_result(supplier_result)
        call_logs.succeed(
            call_code,
            duration_ms=int((time.monotonic() - started) * 1000),
            token_usage=supplier_result.assumptions.get("token_usage"),
            response_excerpt=supplier_result.raw_response,
        )
        result = supplier_result_to_market_quote_result(supplier_result)
        row = MarketQuoteRepository(
            session_factory,
            tenant_code=tenant_code,
            pricing_task_code=payload.pricing_task_code,
        ).save(
            result,
            username=user.username,
        )
    except MarketQuoteProviderError as exc:
        call_logs.fail(
            call_code,
            duration_ms=int((time.monotonic() - started) * 1000),
            error_message=str(exc),
        )
        raise HTTPException(status_code=422, detail=_market_quote_error_detail(str(exc), selected_provider)) from exc
    return to_market_quote_summary(row)


def _market_quote_error_detail(message: str, provider: str | None) -> str:
    provider_label = provider or "默认模型渠道"
    if "InvalidEndpointOrModel.NotFound" in message or "does not exist or you do not have access" in message:
        return (
            f"{provider_label} 模型配置不可用：模型名称或 Endpoint 不存在，或当前账号没有访问权限。"
            "请到“平台配置”检查模型名称/Endpoint ID、Base URL 和 API Key。"
            "如果火山方舟控制台显示服务已开通但仍报错，请复制控制台里的推理接入点 ID（通常是 ep- 开头）作为模型名称；"
            "部分 Retiring/灰度模型即使出现在模型列表中，也可能不能直接用基础模型 ID 调用。"
            f"原始错误：{message}"
        )
    if "ToolNotOpen" in message or "web search" in message:
        return (
            f"{provider_label} 联网搜索未开通：当前账号未启用联网搜索工具。"
            "请在火山方舟控制台开通联网搜索，或关闭联网搜索后使用普通模型询价。"
            f"原始错误：{message}"
        )
    return message


@router.get("/tasks/{task_code}/targets", response_model=list[MarketQuoteTaskTarget])
def list_market_quote_targets(
    task_code: str,
    tenant_code: str = Query("default"),
    limit: int = Query(50, ge=1, le=200),
    user: CurrentUser = Depends(get_current_user),
) -> list[MarketQuoteTaskTarget]:
    require_permission(user, "rule:view")
    session_factory = get_session_factory()
    task = PricingTaskRepository(session_factory).get(tenant_code, task_code)
    if task is None:
        raise HTTPException(status_code=404, detail="Pricing task was not found.")
    if not task.mysql_run_code:
        return []
    with session_scope(session_factory) as session:
        run = session.scalar(
            select(PricingRunORM).where(
                PricingRunORM.tenant_code == tenant_code,
                PricingRunORM.run_code == task.mysql_run_code,
            )
        )
        if run is None:
            return []
        rows = session.scalars(
            select(PricingResultORM)
            .where(
                PricingResultORM.run_id == run.id,
                PricingResultORM.unit_price.is_(None),
            )
            .order_by(PricingResultORM.source_sheet.asc(), PricingResultORM.source_row_number.asc())
            .limit(limit)
        ).all()
        return [
            MarketQuoteTaskTarget(
                task_code=task_code,
                source_sheet=row.source_sheet,
                source_row_number=row.source_row_number,
                item_name=row.item_name,
                unit=row.unit,
                quantity=str(row.quantity) if row.quantity is not None else None,
                features=dict(row.features_json or {}),
                issues=list(row.issues_json or []),
            )
            for row in rows
        ]


@router.post("/excel", response_model=ExcelMarketQuoteResponse, status_code=201)
def estimate_market_quote_excel(
    file: UploadFile = File(...),
    tenant_code: str = Form("default"),
    provider: str = Form("doubao"),
    region: str | None = Form(None),
    price_month: str | None = Form(None),
    standard: str | None = Form(None),
    limit: int = Form(50),
    user: CurrentUser = Depends(get_current_user),
) -> ExcelMarketQuoteResponse:
    require_permission(user, "rule:create")
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Only .xlsx/.xlsm files are supported.")

    settings = get_settings()
    upload_dir = settings.upload_dir / "market-quotes"
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename).suffix
    input_path = upload_dir / f"{uuid.uuid4().hex}{suffix}"
    with input_path.open("wb") as target:
        shutil.copyfileobj(file.file, target)

    session_factory = get_session_factory(settings)
    provider_config = PlatformConfigRepository(
        session_factory,
        tenant_code=tenant_code,
    ).get_active_provider_config(provider)
    quote_provider = create_market_quote_provider(provider, config=provider_config)
    try:
        summary = ExcelMarketQuoteService(
            provider=quote_provider,
            repository=MarketQuoteRepository(session_factory, tenant_code=tenant_code),
            output_dir=settings.output_dir / "market-quotes",
            call_log_repository=ModelCallLogRepository(session_factory, tenant_code=tenant_code),
        ).quote_workbook(
            input_path=input_path,
            username=user.username,
            region=region,
            price_month=price_month,
            standard=standard,
            limit=limit,
        )
    except MarketQuoteProviderError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Excel 批量询价处理失败：{exc}") from exc
    return ExcelMarketQuoteResponse(
        item_count=summary.item_count,
        quoted_count=summary.quoted_count,
        failed_count=summary.failed_count,
        output_path=summary.output_path,
    )


@router.post("/excel/tasks", response_model=PricingTaskAccepted, status_code=202)
def create_market_quote_excel_task(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    tenant_code: str = Form("default"),
    provider: str = Form("doubao"),
    region: str | None = Form(None),
    price_month: str | None = Form(None),
    standard: str | None = Form(None),
    limit: int = Form(50),
    user: CurrentUser = Depends(get_current_user),
) -> PricingTaskAccepted:
    require_permission(user, "rule:create")
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Only .xlsx/.xlsm files are supported.")

    settings = get_settings()
    session_factory = get_session_factory(settings)
    task_code = uuid.uuid4().hex
    upload_dir = settings.upload_dir / "market-quotes"
    upload_dir.mkdir(parents=True, exist_ok=True)
    input_path = upload_dir / f"{task_code}{Path(file.filename).suffix}"
    with input_path.open("wb") as target:
        shutil.copyfileobj(file.file, target)

    task = PricingTaskRepository(session_factory).create(
        PricingTaskCreate(
            tenant_code=tenant_code,
            task_code=task_code,
            workbook_name=file.filename,
            upload_path=str(input_path),
            region_code=region,
            specialty="market_quote_excel",
            cost_category=provider,
            rule_version=price_month,
        )
    )
    background_tasks.add_task(
        MarketQuoteExcelTaskRunner(
            session_factory=session_factory,
            output_dir=settings.output_dir,
        ).run,
        tenant_code,
        task_code,
        provider,
        region,
        price_month,
        standard,
        limit,
    )
    return PricingTaskAccepted(
        task_code=task.task_code,
        status=task.status,
        progress=task.progress,
        message=task.message,
    )


@router.get("/excel/tasks/{task_code}", response_model=PricingTaskStatus)
def get_market_quote_excel_task(
    task_code: str,
    tenant_code: str = "default",
    user: CurrentUser = Depends(get_current_user),
) -> PricingTaskStatus:
    require_permission(user, "rule:view")
    task = PricingTaskRepository(get_session_factory()).get(tenant_code, task_code)
    if task is None:
        raise HTTPException(status_code=404, detail="Market quote task was not found.")
    return to_task_status(task)


@router.post("/excel/tasks/{task_code}/cancel", response_model=PricingTaskStatus)
def cancel_market_quote_excel_task(
    task_code: str,
    tenant_code: str = "default",
    user: CurrentUser = Depends(get_current_user),
) -> PricingTaskStatus:
    require_permission(user, "rule:create")
    repository = PricingTaskRepository(get_session_factory())
    task = repository.get(tenant_code, task_code)
    if task is None:
        raise HTTPException(status_code=404, detail="Market quote task was not found.")
    if task.status in {"succeeded", "failed", "canceled"}:
        return to_task_status(task)
    repository.mark_canceled(tenant_code, task_code)
    canceled = repository.get(tenant_code, task_code)
    return to_task_status(canceled)


@router.get("/page", response_model=MarketQuotePage)
def list_market_quote_page(
    tenant_code: str = Query("default"),
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
) -> MarketQuotePage:
    require_permission(user, "rule:view")
    rows, total = MarketQuoteRepository(get_session_factory(), tenant_code=tenant_code).list_page(
        status=status,
        page=page,
        page_size=page_size,
    )
    return MarketQuotePage(
        items=[to_market_quote_summary(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("", response_model=list[MarketQuoteSummary])
def list_market_quotes(
    tenant_code: str = Query("default"),
    status: str | None = None,
    limit: int = 50,
    user: CurrentUser = Depends(get_current_user),
) -> list[MarketQuoteSummary]:
    require_permission(user, "rule:view")
    rows = MarketQuoteRepository(get_session_factory(), tenant_code=tenant_code).list_recent(
        status=status,
        limit=max(1, min(limit, 100)),
    )
    return [to_market_quote_summary(row) for row in rows]


@router.post("/{quote_code}/approve", response_model=MarketQuoteSummary)
def approve_market_quote(
    quote_code: str,
    background_tasks: BackgroundTasks,
    payload: MarketQuoteReviewRequest | None = None,
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> MarketQuoteSummary:
    require_permission(user, "rule:approve")
    try:
        settings = get_settings()
        session_factory = get_session_factory(settings)
        repository = MarketQuoteRepository(session_factory, tenant_code=tenant_code)
        row = repository.approve(
            quote_code,
            username=user.username,
            comment=payload.comment if payload else None,
        )
        task_code = row.pricing_task_code
        if task_code and not repository.has_pending_for_task(task_code):
            pricing_task = PricingTaskRepository(session_factory).get(tenant_code, task_code)
            if pricing_task is None or pricing_task.status != "waiting_market_quote":
                return to_market_quote_summary(row)
            background_tasks.add_task(
                PricingTaskRunner(
                    session_factory=session_factory,
                    mysql_client=get_mysql_client(settings),
                    output_dir=settings.output_dir,
                ).run,
                tenant_code,
                task_code,
            )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return to_market_quote_summary(row)


@router.post("/{quote_code}/reject", response_model=MarketQuoteSummary)
def reject_market_quote(
    quote_code: str,
    payload: MarketQuoteReviewRequest | None = None,
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> MarketQuoteSummary:
    require_permission(user, "rule:reject")
    try:
        row = MarketQuoteRepository(get_session_factory(), tenant_code=tenant_code).reject(
            quote_code,
            username=user.username,
            comment=payload.comment if payload else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return to_market_quote_summary(row)


def to_market_quote_summary(row) -> MarketQuoteSummary:
    return MarketQuoteSummary(
        quote_code=row.quote_code,
        pricing_task_code=row.pricing_task_code,
        provider=row.provider,
        model=row.model,
        item_name=row.item_name,
        unit=row.unit,
        region_code=row.region_code,
        price_min=str(row.price_min) if row.price_min is not None else None,
        price_max=str(row.price_max) if row.price_max is not None else None,
        recommended_price=str(row.recommended_price) if row.recommended_price is not None else None,
        tax_included=row.tax_included,
        confidence=str(row.confidence),
        source_urls=list(row.source_urls_json or []),
        assumptions=dict(row.assumptions_json or {}),
        status=row.status,
        created_by=row.created_by,
        reviewed_by=row.reviewed_by,
        review_comment=row.review_comment,
        created_at=str(row.created_at),
    )
