from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    app_name: str
    environment: str


class LoginRequest(BaseModel):
    username: str
    password: str
    tenant_code: str = "default"


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    display_name: str | None
    role: str
    tenant_code: str


class CurrentUserResponse(BaseModel):
    username: str
    display_name: str | None
    role: str
    tenant_code: str


class PriceRuleSummary(BaseModel):
    rule_id: str
    version: str
    status: str = "active"
    region_code: str | None = None
    specialty: str | None = None
    cost_category: str | None = None
    item_name_contains: str
    unit: str | None
    unit_price: str
    source: str
    feature_conditions: dict[str, str]
    created_by: str | None = None
    submitted_by: str | None = None
    reviewed_by: str | None = None
    review_comment: str | None = None


class PriceRulePage(BaseModel):
    items: list[PriceRuleSummary]
    total: int
    page: int
    page_size: int


class PriceRuleVersionSummary(BaseModel):
    version: str
    status: str
    rule_count: int


class ItemMappingSummary(BaseModel):
    mapping_code: str
    source_item_name: str
    standard_item_name: str
    match_keywords: list[str]
    unit: str | None
    feature_conditions: dict[str, str]
    status: str
    priority: int
    active: bool
    created_by: str | None = None
    submitted_by: str | None = None
    reviewed_by: str | None = None
    review_comment: str | None = None


class ItemMappingPage(BaseModel):
    items: list[ItemMappingSummary]
    total: int
    page: int
    page_size: int


class ItemMappingSettingSummary(BaseModel):
    confidence_threshold: str


class ItemMappingSettingPayload(BaseModel):
    confidence_threshold: str


class ItemMappingPayload(BaseModel):
    mapping_code: str
    source_item_name: str
    standard_item_name: str
    match_keywords: list[str] = []
    unit: str | None = None
    feature_conditions: dict[str, str] = {}
    status: str = "draft"
    priority: int = 100
    active: bool = True


class ItemMappingReviewSummary(BaseModel):
    review_code: str
    pricing_task_code: str | None = None
    workbook_name: str | None
    source_sheet: str | None
    source_row_number: int | None
    source_item_name: str
    unit: str | None
    features: dict
    candidates: list[dict]
    selected_standard_item_name: str | None
    status: str
    persisted: bool = False
    reviewed_by: str | None
    review_comment: str | None
    created_at: str
    reviewed_at: str | None = None


class ItemMappingReviewPage(BaseModel):
    items: list[ItemMappingReviewSummary]
    total: int
    page: int
    page_size: int


class ItemMappingReviewResolveRequest(BaseModel):
    standard_item_name: str
    comment: str | None = None
    create_mapping: bool = True


class PriceRuleImportResponse(BaseModel):
    imported_count: int
    skipped_count: int
    message: str


class PriceRuleIdentity(BaseModel):
    rule_id: str
    version: str


class PriceRuleBulkSubmitRequest(BaseModel):
    items: list[PriceRuleIdentity] = []
    all_matching: bool = False
    status: str | None = None
    version: str | None = None
    region_code: str | None = None
    specialty: str | None = None
    cost_category: str | None = None
    keyword: str | None = None


class PriceRuleBulkDeleteRequest(BaseModel):
    items: list[PriceRuleIdentity] = []
    all_matching: bool = False
    status: str | None = None
    version: str | None = None
    region_code: str | None = None
    specialty: str | None = None
    cost_category: str | None = None
    keyword: str | None = None


class PriceRuleBulkReviewRequest(BaseModel):
    items: list[PriceRuleIdentity] = []
    all_matching: bool = False
    status: str | None = None
    version: str | None = None
    region_code: str | None = None
    specialty: str | None = None
    cost_category: str | None = None
    keyword: str | None = None
    comment: str | None = None


class PriceRuleBulkActionResponse(BaseModel):
    affected_count: int
    skipped_count: int
    message: str


class PriceRuleUpsertRequest(BaseModel):
    rule_id: str
    version: str = "v1"
    status: str = "active"
    region_code: str | None = None
    specialty: str | None = None
    cost_category: str | None = None
    item_name_contains: str
    unit: str | None = None
    unit_price: str
    source: str = "manual"
    feature_conditions: dict[str, str] = {}
    match_priority: int = 100
    active: bool = True


class PriceRuleDraftRequest(BaseModel):
    rule_id: str
    version: str
    item_name_contains: str
    unit: str | None = None
    unit_price: str
    source: str
    feature_conditions: dict[str, str] = {}


class RuleReviewRequest(BaseModel):
    comment: str | None = None


class MaterialPricePayload(BaseModel):
    material_code: str | None = None
    material_name: str
    specification: str | None = None
    region_code: str | None = None
    unit: str
    unit_price: str
    price_month: str
    source: str


class PriceComponentPayload(BaseModel):
    component_type: str
    component_name: str
    unit: str | None = None
    quantity: str
    unit_price: str | None = None
    material_code: str | None = None
    quota_code: str | None = None
    price_source_type: str = "manual"
    source: str | None = None


class RuleComponentsRequest(BaseModel):
    region_code: str | None = None
    price_month: str | None = None
    components: list[PriceComponentPayload]


class PriceComponentSummary(BaseModel):
    component_type: str
    component_name: str
    unit: str | None
    quantity: str
    unit_price: str
    amount: str
    source: str | None


class MarketQuoteRequestPayload(BaseModel):
    item_name: str
    unit: str | None = None
    features: dict[str, str] = {}
    region: str | None = None
    price_month: str | None = None
    standard: str | None = None
    pricing_task_code: str | None = None


class MarketQuoteTaskTarget(BaseModel):
    task_code: str
    source_sheet: str
    source_row_number: int
    item_name: str
    unit: str | None
    quantity: str | None
    features: dict
    issues: list[str]


class MarketQuoteSummary(BaseModel):
    quote_code: str
    pricing_task_code: str | None = None
    provider: str
    model: str
    item_name: str
    unit: str | None
    region_code: str | None
    price_min: str | None
    price_max: str | None
    recommended_price: str | None
    tax_included: bool
    confidence: str
    source_urls: list[str]
    assumptions: dict
    status: str
    created_by: str | None
    reviewed_by: str | None = None
    review_comment: str | None = None
    created_at: str


class MarketQuotePage(BaseModel):
    items: list[MarketQuoteSummary]
    total: int
    page: int
    page_size: int


class MarketQuoteReviewRequest(BaseModel):
    comment: str | None = None


class ExcelMarketQuoteResponse(BaseModel):
    item_count: int
    quoted_count: int
    failed_count: int
    output_path: str


class ModelCallLogSummary(BaseModel):
    call_code: str
    provider: str
    model: str
    scenario: str
    task_code: str | None
    item_name: str | None
    status: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    duration_ms: int | None
    response_excerpt: str | None
    error_message: str | None
    created_by: str | None
    created_at: str
    finished_at: str | None


class ModelCallLogPage(BaseModel):
    items: list[ModelCallLogSummary]
    total: int
    page: int
    page_size: int


class PlatformConfigPayload(BaseModel):
    provider: str
    display_name: str
    base_url: str
    model: str
    api_key: str | None = None
    endpoint_type: str = "chat_completions"
    enable_web_search: bool = False
    search_tool_type: str | None = "web_search_preview"
    timeout_seconds: int = 60
    active: bool = True
    remark: str | None = None


class PlatformConfigSummary(BaseModel):
    provider: str
    display_name: str
    base_url: str
    model: str
    api_key_configured: bool
    endpoint_type: str
    enable_web_search: bool
    search_tool_type: str | None
    timeout_seconds: int
    active: bool
    remark: str | None
    updated_by: str | None
    updated_at: str


class PricingRunRequest(BaseModel):
    tenant_code: str = "default"
    project_name: str | None = None
    region_code: str | None = None
    specialty: str | None = None
    cost_category: str | None = None
    rule_version: str | None = None
    write_mysql_audit: bool = True


class PricingRunResponse(BaseModel):
    item_count: int
    priced_count: int
    unpriced_count: int
    issue_counts: dict[str, int]
    excel_path: str
    missing_rules_path: str
    audit_path: str
    mysql_run_code: str | None


class PricingTaskAccepted(BaseModel):
    task_code: str
    status: str
    progress: int
    message: str | None


class PricingTaskStatus(BaseModel):
    task_code: str
    status: str
    progress: int
    message: str | None
    workbook_name: str
    project_name: str | None
    region_code: str | None
    item_count: int
    priced_count: int
    unpriced_count: int
    excel_path: str | None
    missing_rules_path: str | None
    audit_path: str | None
    mysql_run_code: str | None
    failure_reasons: list[str] = []
    created_at: str
    started_at: str | None
    finished_at: str | None


class PricingRunSummary(BaseModel):
    run_code: str
    project_name: str | None
    region_code: str | None
    item_count: int
    priced_count: int
    unpriced_count: int
    created_at: str
    updated_at: str


class PricingResultSummary(BaseModel):
    source_sheet: str
    source_row_number: int
    sequence_no: str | None
    item_code: str | None
    item_name: str
    unit: str | None
    quantity: str | None
    unit_price: str | None
    total_price: str | None
    rule_code: str | None
    rule_version: str | None
    price_source: str | None
    confidence: str
    features: dict
    issues: list[str]


class PricingRunDetail(BaseModel):
    run_code: str
    workbook_name: str
    project_name: str | None
    region_code: str | None
    rule_source: str
    rule_version: str | None
    item_count: int
    priced_count: int
    unpriced_count: int
    created_at: str
    updated_at: str
    results: list[PricingResultSummary]


class ErrorResponse(BaseModel):
    detail: str = Field(..., examples=["No active MySQL price rules were found."])
