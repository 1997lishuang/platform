from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from boq_pricing.api.auth import CurrentUser, get_current_user, require_permission
from boq_pricing.api.dependencies import get_session_factory
from boq_pricing.api.schemas import PlatformConfigPayload, PlatformConfigSummary
from boq_pricing.infrastructure import PlatformConfigInput, PlatformConfigRepository


router = APIRouter(prefix="/platform-configs", tags=["platform-configs"])


@router.get("", response_model=list[PlatformConfigSummary])
def list_platform_configs(
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> list[PlatformConfigSummary]:
    require_permission(user, "rule:view")
    rows = PlatformConfigRepository(get_session_factory(), tenant_code=tenant_code).list()
    return [to_summary(row) for row in rows]


@router.put("/{provider}", response_model=PlatformConfigSummary)
def upsert_platform_config(
    provider: str,
    payload: PlatformConfigPayload,
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> PlatformConfigSummary:
    require_permission(user, "rule:create")
    row = PlatformConfigRepository(get_session_factory(), tenant_code=tenant_code).upsert(
        PlatformConfigInput(
            provider=provider,
            display_name=payload.display_name,
            base_url=payload.base_url,
            model=payload.model,
            api_key=payload.api_key,
            endpoint_type=payload.endpoint_type,
            enable_web_search=payload.enable_web_search,
            search_tool_type=payload.search_tool_type,
            timeout_seconds=payload.timeout_seconds,
            active=payload.active,
            remark=payload.remark,
        ),
        username=user.username,
    )
    return to_summary(row)


def to_summary(row) -> PlatformConfigSummary:
    return PlatformConfigSummary(
        provider=row.provider,
        display_name=row.display_name,
        base_url=row.base_url,
        model=row.model,
        api_key_configured=bool(row.api_key),
        endpoint_type=row.endpoint_type,
        enable_web_search=row.enable_web_search,
        search_tool_type=row.search_tool_type,
        timeout_seconds=row.timeout_seconds,
        active=row.active,
        remark=row.remark,
        updated_by=row.updated_by,
        updated_at=str(row.updated_at),
    )
