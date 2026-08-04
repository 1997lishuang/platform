from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from boq_pricing.api.auth import CurrentUser, get_current_user, require_permission
from boq_pricing.api.dependencies import get_session_factory
from boq_pricing.api.schemas import ModelCallLogPage, ModelCallLogSummary
from boq_pricing.infrastructure.model_call_logs import ModelCallLogRepository

router = APIRouter(prefix="/model-call-logs", tags=["model-call-logs"])


@router.get("/page", response_model=ModelCallLogPage)
def list_model_call_logs(
    tenant_code: str = Query("default"),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
) -> ModelCallLogPage:
    require_permission(user, "rule:view")
    rows, total = ModelCallLogRepository(
        get_session_factory(),
        tenant_code=tenant_code,
    ).list_page(status=status, page=page, page_size=page_size)
    return ModelCallLogPage(
        items=[to_model_call_log_summary(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


def to_model_call_log_summary(row) -> ModelCallLogSummary:
    return ModelCallLogSummary(
        call_code=row.call_code,
        provider=row.provider,
        model=row.model,
        scenario=row.scenario,
        task_code=row.task_code,
        item_name=row.item_name,
        status=row.status,
        prompt_tokens=row.prompt_tokens,
        completion_tokens=row.completion_tokens,
        total_tokens=row.total_tokens,
        duration_ms=row.duration_ms,
        response_excerpt=row.response_excerpt,
        error_message=row.error_message,
        created_by=row.created_by,
        created_at=str(row.created_at),
        finished_at=str(row.finished_at) if row.finished_at else None,
    )
