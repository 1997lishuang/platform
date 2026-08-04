from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from boq_pricing.api.auth import CurrentUser, get_current_user, require_permission
from boq_pricing.api.dependencies import get_mysql_client, get_session_factory, get_settings
from boq_pricing.api.schemas import (
    ItemMappingPage,
    ItemMappingPayload,
    ItemMappingReviewPage,
    ItemMappingReviewResolveRequest,
    ItemMappingReviewSummary,
    ItemMappingSettingPayload,
    ItemMappingSettingSummary,
    ItemMappingSummary,
    RuleReviewRequest,
)
from boq_pricing.infrastructure import ItemMappingInput, ItemMappingRepository
from boq_pricing.infrastructure.pricing_tasks import PricingTaskRepository
from boq_pricing.application.async_tasks import PricingTaskRunner

router = APIRouter(prefix="/item-mappings", tags=["item-mappings"])


@router.get("/setting", response_model=ItemMappingSettingSummary)
def get_mapping_setting(
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> ItemMappingSettingSummary:
    require_permission(user, "rule:view")
    setting = ItemMappingRepository(get_session_factory(), tenant_code=tenant_code).get_setting()
    return ItemMappingSettingSummary(confidence_threshold=str(setting.confidence_threshold))


@router.put("/setting", response_model=ItemMappingSettingSummary)
def update_mapping_setting(
    payload: ItemMappingSettingPayload,
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> ItemMappingSettingSummary:
    require_permission(user, "rule:create")
    setting = ItemMappingRepository(get_session_factory(), tenant_code=tenant_code).update_setting(
        Decimal(payload.confidence_threshold),
        username=user.username,
    )
    return ItemMappingSettingSummary(confidence_threshold=str(setting.confidence_threshold))


@router.get("/page", response_model=ItemMappingPage)
def list_mappings(
    tenant_code: str = Query("default"),
    status: str | None = None,
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
) -> ItemMappingPage:
    require_permission(user, "rule:view")
    rows, total = ItemMappingRepository(get_session_factory(), tenant_code=tenant_code).list_page(
        status=status,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return ItemMappingPage(items=[to_mapping_summary(row) for row in rows], total=total, page=page, page_size=page_size)


@router.post("", response_model=ItemMappingSummary, status_code=201)
def upsert_mapping(
    payload: ItemMappingPayload,
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> ItemMappingSummary:
    require_permission(user, "rule:create")
    row = ItemMappingRepository(get_session_factory(), tenant_code=tenant_code).upsert(
        ItemMappingInput(
            mapping_code=payload.mapping_code,
            source_item_name=payload.source_item_name,
            standard_item_name=payload.standard_item_name,
            match_keywords=payload.match_keywords,
            unit=payload.unit,
            feature_conditions=payload.feature_conditions,
            status=payload.status,
            priority=payload.priority,
            active=payload.active,
        ),
        username=user.username,
    )
    return to_mapping_summary(row)


@router.put("/{mapping_code}", response_model=ItemMappingSummary)
def update_mapping(
    mapping_code: str,
    payload: ItemMappingPayload,
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> ItemMappingSummary:
    require_permission(user, "rule:create")
    row = ItemMappingRepository(get_session_factory(), tenant_code=tenant_code).upsert(
        ItemMappingInput(
            mapping_code=mapping_code,
            source_item_name=payload.source_item_name,
            standard_item_name=payload.standard_item_name,
            match_keywords=payload.match_keywords,
            unit=payload.unit,
            feature_conditions=payload.feature_conditions,
            status=payload.status,
            priority=payload.priority,
            active=payload.active,
        ),
        username=user.username,
    )
    return to_mapping_summary(row)


@router.delete("/{mapping_code}", status_code=204)
def delete_mapping(
    mapping_code: str,
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    require_permission(user, "rule:create")
    deleted = ItemMappingRepository(get_session_factory(), tenant_code=tenant_code).delete(mapping_code)
    if not deleted:
        raise HTTPException(status_code=404, detail="Mapping was not found.")


@router.post("/{mapping_code}/submit", response_model=ItemMappingSummary)
def submit_mapping(
    mapping_code: str,
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> ItemMappingSummary:
    require_permission(user, "rule:submit")
    try:
        row = ItemMappingRepository(get_session_factory(), tenant_code=tenant_code).submit(mapping_code, user.username)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Mapping was not found.") from exc
    return to_mapping_summary(row)


@router.post("/{mapping_code}/approve", response_model=ItemMappingSummary)
def approve_mapping(
    mapping_code: str,
    payload: RuleReviewRequest,
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> ItemMappingSummary:
    require_permission(user, "rule:approve")
    try:
        row = ItemMappingRepository(get_session_factory(), tenant_code=tenant_code).approve(mapping_code, user.username, payload.comment)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Mapping was not found.") from exc
    return to_mapping_summary(row)


@router.post("/{mapping_code}/reject", response_model=ItemMappingSummary)
def reject_mapping(
    mapping_code: str,
    payload: RuleReviewRequest,
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> ItemMappingSummary:
    require_permission(user, "rule:reject")
    try:
        row = ItemMappingRepository(get_session_factory(), tenant_code=tenant_code).reject(mapping_code, user.username, payload.comment)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Mapping was not found.") from exc
    return to_mapping_summary(row)


@router.get("/reviews/page", response_model=ItemMappingReviewPage)
def list_mapping_reviews(
    tenant_code: str = Query("default"),
    status: str | None = "pending",
    persisted: bool | None = None,
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
) -> ItemMappingReviewPage:
    require_permission(user, "rule:view")
    rows, total = ItemMappingRepository(get_session_factory(), tenant_code=tenant_code).list_reviews(
        status=status,
        persisted=persisted,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return ItemMappingReviewPage(items=[to_review_summary(row) for row in rows], total=total, page=page, page_size=page_size)


@router.post("/reviews/{review_code}/resolve", response_model=ItemMappingReviewSummary)
def resolve_mapping_review(
    review_code: str,
    payload: ItemMappingReviewResolveRequest,
    background_tasks: BackgroundTasks,
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> ItemMappingReviewSummary:
    require_permission(user, "rule:approve")
    try:
        session_factory = get_session_factory()
        repository = ItemMappingRepository(session_factory, tenant_code=tenant_code)
        row = repository.resolve_review(
            review_code=review_code,
            standard_item_name=payload.standard_item_name,
            username=user.username,
            comment=payload.comment,
            create_mapping=payload.create_mapping,
        )
        task_code = row.pricing_task_code
        if task_code and not repository.has_pending_reviews_for_task(task_code):
            pricing_task = PricingTaskRepository(session_factory).get(tenant_code, task_code)
            if pricing_task is None or pricing_task.status != "waiting_mapping":
                return to_review_summary(row)
            settings = get_settings()
            background_tasks.add_task(
                PricingTaskRunner(
                    session_factory=session_factory,
                    mysql_client=get_mysql_client(settings),
                    output_dir=settings.output_dir,
                ).run,
                tenant_code,
                task_code,
            )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Mapping review was not found.") from exc
    return to_review_summary(row)


def to_mapping_summary(row) -> ItemMappingSummary:
    return ItemMappingSummary(
        mapping_code=row.mapping_code,
        source_item_name=row.source_item_name,
        standard_item_name=row.standard_item_name,
        match_keywords=list(row.match_keywords_json or []),
        unit=row.unit,
        feature_conditions=dict(row.feature_conditions_json or {}),
        status=row.status,
        priority=row.priority,
        active=row.active,
        created_by=row.created_by,
        submitted_by=row.submitted_by,
        reviewed_by=row.reviewed_by,
        review_comment=row.review_comment,
    )


def to_review_summary(row) -> ItemMappingReviewSummary:
    return ItemMappingReviewSummary(
        review_code=row.review_code,
        pricing_task_code=row.pricing_task_code,
        workbook_name=row.workbook_name,
        source_sheet=row.source_sheet,
        source_row_number=row.source_row_number,
        source_item_name=row.source_item_name,
        unit=row.unit,
        features=dict(row.feature_json or {}),
        candidates=list(row.candidate_json or []),
        selected_standard_item_name=row.selected_standard_item_name,
        status=row.status,
        persisted=bool(getattr(row, "_persisted", False)),
        reviewed_by=row.reviewed_by,
        review_comment=row.review_comment,
        created_at=str(row.created_at),
        reviewed_at=str(row.reviewed_at) if row.reviewed_at else None,
    )
