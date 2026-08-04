from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import re
import shutil
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from boq_pricing.api.auth import CurrentUser, get_current_user, require_permission
from boq_pricing.api.dependencies import get_session_factory, get_settings
from boq_pricing.api.schemas import (
    MaterialPricePayload,
    PriceComponentPayload,
    PriceComponentSummary,
    PriceRuleBulkActionResponse,
    PriceRuleBulkDeleteRequest,
    PriceRuleBulkReviewRequest,
    PriceRuleBulkSubmitRequest,
    PriceRuleImportResponse,
    PriceRulePage,
    PriceRuleDraftRequest,
    PriceRuleSummary,
    PriceRuleUpsertRequest,
    PriceRuleVersionSummary,
    RuleComponentsRequest,
    RuleReviewRequest,
)
from boq_pricing.domain import PriceRule
from boq_pricing.infrastructure import (
    ComponentPricingRepository,
    ExcelBillReader,
    MaterialPriceInput,
    PriceComponentInput,
    RuleApprovalRepository,
    SqlAlchemyPriceRuleRepository,
)
from boq_pricing.parsing import FeatureParser

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("", response_model=list[PriceRuleSummary])
def list_rules(
    tenant_code: str = Query("default"),
    status: str | None = None,
    version: str | None = None,
    region_code: str | None = None,
    specialty: str | None = None,
    cost_category: str | None = None,
    user: CurrentUser = Depends(get_current_user),
) -> list[PriceRuleSummary]:
    require_permission(user, "rule:view")
    if status:
        rows = RuleApprovalRepository(get_session_factory(), tenant_code=tenant_code).list_rules(status=status)
        return [to_rule_summary(row) for row in rows]
    rules = SqlAlchemyPriceRuleRepository(get_session_factory(), tenant_code=tenant_code).load(
        version=version,
        region_code=region_code,
        specialty=specialty,
        cost_category=cost_category,
    )
    return [to_active_summary(rule) for rule in rules]


@router.get("/page", response_model=PriceRulePage)
def list_rules_page(
    tenant_code: str = Query("default"),
    status: str | None = None,
    version: str | None = None,
    region_code: str | None = None,
    specialty: str | None = None,
    cost_category: str | None = None,
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
) -> PriceRulePage:
    require_permission(user, "rule:view")
    rows, total = SqlAlchemyPriceRuleRepository(get_session_factory(), tenant_code=tenant_code).list_page(
        status=status,
        version=version,
        region_code=region_code,
        specialty=specialty,
        cost_category=cost_category,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return PriceRulePage(
        items=[to_rule_summary(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/versions", response_model=list[PriceRuleVersionSummary])
def list_rule_versions(
    tenant_code: str = Query("default"),
    status: str | None = Query(None),
    user: CurrentUser = Depends(get_current_user),
) -> list[PriceRuleVersionSummary]:
    require_permission(user, "rule:view")
    rows = SqlAlchemyPriceRuleRepository(get_session_factory(), tenant_code=tenant_code).list_versions(status=status)
    return [
        PriceRuleVersionSummary(version=version, status=row_status, rule_count=rule_count)
        for version, row_status, rule_count in rows
    ]


@router.post("", response_model=PriceRuleSummary, status_code=201)
def create_rule(
    payload: PriceRuleUpsertRequest,
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> PriceRuleSummary:
    require_permission(user, "rule:create")
    try:
        row = SqlAlchemyPriceRuleRepository(get_session_factory(), tenant_code=tenant_code).upsert_rule(
            rule_code=payload.rule_id,
            version=payload.version,
            status=payload.status,
            item_name_contains=payload.item_name_contains,
            unit=payload.unit,
            unit_price=Decimal(payload.unit_price),
            source=payload.source,
            feature_conditions=payload.feature_conditions,
            region_code=payload.region_code,
            specialty=payload.specialty,
            cost_category=payload.cost_category,
            match_priority=payload.match_priority,
            active=payload.active,
            username=user.username,
        )
        return to_rule_summary(row)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/import-excel", response_model=PriceRuleImportResponse, status_code=201)
def import_rules_excel(
    file: UploadFile = File(...),
    tenant_code: str = Form("default"),
    region_code: str | None = Form(None),
    specialty: str | None = Form(None),
    cost_category: str | None = Form(None),
    version: str = Form("excel-import"),
    status: str = Form("draft"),
    user: CurrentUser = Depends(get_current_user),
) -> PriceRuleImportResponse:
    require_permission(user, "rule:create")
    if not (file.filename or "").lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Only .xlsx/.xlsm files are supported.")

    settings = get_settings()
    upload_dir = settings.upload_dir / "price-rules"
    upload_dir.mkdir(parents=True, exist_ok=True)
    input_path = upload_dir / f"{uuid.uuid4().hex}.{file.filename or 'rules.xlsx'}"
    with input_path.open("wb") as output:
        shutil.copyfileobj(file.file, output)

    repository = SqlAlchemyPriceRuleRepository(get_session_factory(settings), tenant_code=tenant_code)
    parser = FeatureParser()
    imported_count = 0
    skipped_count = 0
    effective_version = build_import_version(version)
    try:
        for item in ExcelBillReader().read(input_path):
            if not item.item_name or item.original_unit_price is None or item.original_unit_price <= 0:
                skipped_count += 1
                continue
            rule_code = build_import_rule_code(item.item_code, item.sequence, item.source.row_number)
            features = parser.parse(item.feature_text).values if item.feature_text else {}
            repository.upsert_rule(
                rule_code=rule_code,
                version=effective_version,
                status=status,
                item_name_contains=item.item_name,
                unit=item.unit,
                unit_price=item.original_unit_price,
                source=f"excel_import:{file.filename or input_path.name}",
                feature_conditions=features,
                region_code=region_code or None,
                specialty=specialty or None,
                cost_category=cost_category or None,
                match_priority=80,
                active=status == "active",
                username=user.username,
            )
            imported_count += 1
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Excel 规则导入失败：{exc}") from exc

    return PriceRuleImportResponse(
        imported_count=imported_count,
        skipped_count=skipped_count,
        message=f"??? {imported_count} ?????? {skipped_count} ???????????????{effective_version}",
    )


@router.put("/{rule_id}/{version}", response_model=PriceRuleSummary)
def update_rule(
    rule_id: str,
    version: str,
    payload: PriceRuleUpsertRequest,
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> PriceRuleSummary:
    require_permission(user, "rule:create")
    repository = SqlAlchemyPriceRuleRepository(get_session_factory(), tenant_code=tenant_code)
    if repository.get(rule_id, version) is None:
        raise HTTPException(status_code=404, detail="Rule was not found.")
    try:
        row = repository.upsert_rule(
            rule_code=rule_id,
            version=version,
            status=payload.status,
            item_name_contains=payload.item_name_contains,
            unit=payload.unit,
            unit_price=Decimal(payload.unit_price),
            source=payload.source,
            feature_conditions=payload.feature_conditions,
            region_code=payload.region_code,
            specialty=payload.specialty,
            cost_category=payload.cost_category,
            match_priority=payload.match_priority,
            active=payload.active,
            username=user.username,
        )
        return to_rule_summary(row)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/{rule_id}/{version}", status_code=204)
def delete_rule(
    rule_id: str,
    version: str,
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    require_permission(user, "rule:create")
    deleted = SqlAlchemyPriceRuleRepository(get_session_factory(), tenant_code=tenant_code).delete_rule(rule_id, version)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule was not found.")


@router.post("/bulk-submit", response_model=PriceRuleBulkActionResponse)
def submit_rules_bulk(
    payload: PriceRuleBulkSubmitRequest,
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> PriceRuleBulkActionResponse:
    require_permission(user, "rule:submit")
    identities = resolve_bulk_identities(payload, tenant_code, allowed_statuses={"draft", "rejected"})
    repository = RuleApprovalRepository(get_session_factory(), tenant_code=tenant_code)
    affected = 0
    skipped = 0
    for rule_id, row_version in identities:
        try:
            repository.submit(rule_id, row_version, user.username)
            affected += 1
        except Exception:
            skipped += 1
    return PriceRuleBulkActionResponse(
        affected_count=affected,
        skipped_count=skipped,
        message=f"已提交审批 {affected} 条，跳过 {skipped} 条。",
    )


@router.post("/bulk-delete", response_model=PriceRuleBulkActionResponse)
def delete_rules_bulk(
    payload: PriceRuleBulkDeleteRequest,
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> PriceRuleBulkActionResponse:
    require_permission(user, "rule:create")
    identities = resolve_bulk_identities(payload, tenant_code)
    affected, skipped = SqlAlchemyPriceRuleRepository(
        get_session_factory(),
        tenant_code=tenant_code,
    ).delete_rules(identities)
    return PriceRuleBulkActionResponse(
        affected_count=affected,
        skipped_count=skipped,
        message=f"已删除 {affected} 条，跳过 {skipped} 条。",
    )


@router.post("/bulk-approve", response_model=PriceRuleBulkActionResponse)
def approve_rules_bulk(
    payload: PriceRuleBulkReviewRequest,
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> PriceRuleBulkActionResponse:
    require_permission(user, "rule:approve")
    identities = resolve_bulk_identities(payload, tenant_code, allowed_statuses={"reviewing"})
    repository = RuleApprovalRepository(get_session_factory(), tenant_code=tenant_code)
    affected = 0
    skipped = 0
    for rule_id, row_version in identities:
        try:
            repository.approve(rule_id, row_version, user.username, payload.comment)
            affected += 1
        except Exception:
            skipped += 1
    return PriceRuleBulkActionResponse(
        affected_count=affected,
        skipped_count=skipped,
        message=f"已通过 {affected} 条，跳过 {skipped} 条。",
    )


@router.post("/bulk-reject", response_model=PriceRuleBulkActionResponse)
def reject_rules_bulk(
    payload: PriceRuleBulkReviewRequest,
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> PriceRuleBulkActionResponse:
    require_permission(user, "rule:reject")
    identities = resolve_bulk_identities(payload, tenant_code, allowed_statuses={"reviewing"})
    repository = RuleApprovalRepository(get_session_factory(), tenant_code=tenant_code)
    affected = 0
    skipped = 0
    for rule_id, row_version in identities:
        try:
            repository.reject(rule_id, row_version, user.username, payload.comment)
            affected += 1
        except Exception:
            skipped += 1
    return PriceRuleBulkActionResponse(
        affected_count=affected,
        skipped_count=skipped,
        message=f"已驳回 {affected} 条，跳过 {skipped} 条。",
    )


@router.post("/drafts", response_model=PriceRuleSummary, status_code=201)
def create_rule_draft(
    payload: PriceRuleDraftRequest,
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> PriceRuleSummary:
    require_permission(user, "rule:create")
    try:
        row = RuleApprovalRepository(get_session_factory(), tenant_code=tenant_code).create_draft(
            PriceRule(
                rule_id=payload.rule_id,
                item_name_contains=payload.item_name_contains,
                unit=payload.unit,
                feature_conditions=payload.feature_conditions,
                unit_price=Decimal(payload.unit_price),
                source=payload.source,
                version=payload.version,
            ),
            username=user.username,
        )
        return to_rule_summary(row)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{rule_id}/{version}/submit", response_model=PriceRuleSummary)
def submit_rule(
    rule_id: str,
    version: str,
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> PriceRuleSummary:
    require_permission(user, "rule:submit")
    return transition_rule("submit", rule_id, version, tenant_code, user, None)


@router.post("/{rule_id}/{version}/approve", response_model=PriceRuleSummary)
def approve_rule(
    rule_id: str,
    version: str,
    payload: RuleReviewRequest | None = None,
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> PriceRuleSummary:
    require_permission(user, "rule:approve")
    return transition_rule("approve", rule_id, version, tenant_code, user, payload)


@router.post("/{rule_id}/{version}/reject", response_model=PriceRuleSummary)
def reject_rule(
    rule_id: str,
    version: str,
    payload: RuleReviewRequest | None = None,
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> PriceRuleSummary:
    require_permission(user, "rule:reject")
    return transition_rule("reject", rule_id, version, tenant_code, user, payload)


@router.post("/materials", status_code=201)
def upsert_material_prices(
    payload: list[MaterialPricePayload],
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, int]:
    require_permission(user, "rule:create")
    count = ComponentPricingRepository(get_session_factory(), tenant_code=tenant_code).upsert_material_prices(
        [
            MaterialPriceInput(
                material_code=item.material_code,
                material_name=item.material_name,
                specification=item.specification,
                region_code=item.region_code,
                unit=item.unit,
                unit_price=Decimal(item.unit_price),
                price_month=item.price_month,
                source=item.source,
            )
            for item in payload
        ]
    )
    return {"imported": count}


@router.put("/{rule_id}/{version}/components", response_model=list[PriceComponentSummary])
def replace_rule_components(
    rule_id: str,
    version: str,
    payload: RuleComponentsRequest,
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> list[PriceComponentSummary]:
    require_permission(user, "rule:create")
    repository = ComponentPricingRepository(get_session_factory(), tenant_code=tenant_code)
    try:
        repository.replace_rule_components(
            rule_id,
            version,
            [
                PriceComponentInput(
                    component_type=item.component_type,
                    component_name=item.component_name,
                    unit=item.unit,
                    quantity=Decimal(item.quantity),
                    unit_price=Decimal(item.unit_price) if item.unit_price is not None else None,
                    material_code=item.material_code,
                    quota_code=item.quota_code,
                    price_source_type=item.price_source_type,
                    source=item.source,
                )
                for item in payload.components
            ],
            region_code=payload.region_code,
            price_month=payload.price_month,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    rule = next(
        (
            rule
            for rule in SqlAlchemyPriceRuleRepository(get_session_factory(), tenant_code=tenant_code).load()
            if rule.rule_id == rule_id and rule.version == version
        ),
        None,
    )
    return [to_component_summary(component) for component in (rule.components if rule else ())]


def transition_rule(
    action: str,
    rule_id: str,
    version: str,
    tenant_code: str,
    user: CurrentUser,
    payload: RuleReviewRequest | None,
) -> PriceRuleSummary:
    repository = RuleApprovalRepository(get_session_factory(), tenant_code=tenant_code)
    try:
        if action == "submit":
            row = repository.submit(rule_id, version, user.username)
        elif action == "approve":
            row = repository.approve(rule_id, version, user.username, payload.comment if payload else None)
        elif action == "reject":
            row = repository.reject(rule_id, version, user.username, payload.comment if payload else None)
        else:
            raise ValueError("Unsupported action.")
        return to_rule_summary(row)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def to_active_summary(rule: PriceRule) -> PriceRuleSummary:
    return PriceRuleSummary(
        rule_id=rule.rule_id,
        version=rule.version,
        status="active",
        item_name_contains=rule.item_name_contains,
        unit=rule.unit,
        unit_price=str(rule.unit_price),
        source=rule.source,
        feature_conditions=rule.feature_conditions,
    )


def build_import_rule_code(item_code: str | None, sequence: str | None, row_number: int) -> str:
    raw = item_code or sequence or f"ROW-{row_number}"
    normalized = re.sub(r"[^0-9A-Za-z_.-]+", "-", str(raw)).strip("-")
    return f"XLSX-{normalized or row_number}"


def build_import_version(version: str) -> str:
    base = re.sub(r"[^0-9A-Za-z_.-]+", "-", (version or "excel-import").strip()).strip("-")
    return f"{base or 'excel-import'}-{datetime.now().strftime('%Y%m%d%H%M%S')}"


def resolve_bulk_identities(
    payload: PriceRuleBulkSubmitRequest | PriceRuleBulkDeleteRequest,
    tenant_code: str,
    allowed_statuses: set[str] | None = None,
) -> list[tuple[str, str]]:
    if payload.all_matching:
        return SqlAlchemyPriceRuleRepository(get_session_factory(), tenant_code=tenant_code).list_identities(
            status=payload.status,
            version=payload.version,
            region_code=payload.region_code,
            specialty=payload.specialty,
            cost_category=payload.cost_category,
            keyword=payload.keyword,
            allowed_statuses=allowed_statuses,
        )
    return [(item.rule_id, item.version) for item in payload.items]


def to_rule_summary(row) -> PriceRuleSummary:
    return PriceRuleSummary(
        rule_id=row.rule_code,
        version=row.version,
        status=row.status,
        region_code=row.region_code,
        specialty=row.specialty,
        cost_category=row.cost_category,
        item_name_contains=row.item_name_contains,
        unit=row.unit,
        unit_price=str(row.unit_price),
        source=row.source,
        feature_conditions=dict(row.feature_conditions_json or {}),
        created_by=row.created_by,
        submitted_by=row.submitted_by,
        reviewed_by=row.reviewed_by,
        review_comment=row.review_comment,
    )


def to_component_summary(component) -> PriceComponentSummary:
    return PriceComponentSummary(
        component_type=component.component_type,
        component_name=component.component_name,
        unit=component.unit,
        quantity=str(component.quantity),
        unit_price=str(component.unit_price),
        amount=str(component.amount),
        source=component.source,
    )
