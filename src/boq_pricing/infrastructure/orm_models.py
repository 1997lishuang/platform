from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from boq_pricing.infrastructure.db import Base

BIGINT_PK = BigInteger().with_variant(Integer, "sqlite")


class PriceRuleORM(Base):
    __tablename__ = "price_rule"
    __table_args__ = (
        UniqueConstraint("tenant_code", "rule_code", "version", name="uk_price_rule_tenant_code_version"),
        Index("idx_price_rule_active_name_unit", "tenant_code", "active", "item_name_contains", "unit"),
        Index("idx_price_rule_scope", "tenant_code", "active", "region_code", "specialty", "cost_category"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    tenant_code: Mapped[str] = mapped_column(String(64), default="default", nullable=False)
    rule_code: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    project_type: Mapped[str | None] = mapped_column(String(64))
    region_code: Mapped[str | None] = mapped_column(String(64))
    specialty: Mapped[str | None] = mapped_column(String(64))
    cost_category: Mapped[str | None] = mapped_column(String(64))
    item_name_contains: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32))
    feature_conditions_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    pricing_method: Mapped[str] = mapped_column(String(32), default="fixed_unit_price", nullable=False)
    match_priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(128))
    submitted_by: Mapped[str | None] = mapped_column(String(128))
    reviewed_by: Mapped[str | None] = mapped_column(String(128))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_comment: Mapped[str | None] = mapped_column(String(512))
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    conditions: Mapped[list["PriceRuleConditionORM"]] = relationship(
        back_populates="rule",
        cascade="all, delete-orphan",
    )


class PriceRuleConditionORM(Base):
    __tablename__ = "price_rule_condition"
    __table_args__ = (
        UniqueConstraint("price_rule_id", "feature_key", "operator", "expected_value", name="uk_rule_condition"),
        Index("idx_condition_feature_key", "feature_key"),
        Index("idx_condition_expected_value", "expected_value"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    price_rule_id: Mapped[int] = mapped_column(ForeignKey("price_rule.id", ondelete="CASCADE"), nullable=False)
    feature_key: Mapped[str] = mapped_column(String(128), nullable=False)
    operator: Mapped[str] = mapped_column(String(32), default="contains", nullable=False)
    expected_value: Mapped[str] = mapped_column(String(512), nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    rule: Mapped[PriceRuleORM] = relationship(back_populates="conditions")


class ItemMappingORM(Base):
    __tablename__ = "item_mapping"
    __table_args__ = (
        UniqueConstraint("tenant_code", "mapping_code", name="uk_item_mapping_code"),
        Index("idx_item_mapping_lookup", "tenant_code", "status", "active", "source_item_name", "unit"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    tenant_code: Mapped[str] = mapped_column(String(64), default="default", nullable=False)
    mapping_code: Mapped[str] = mapped_column(String(128), nullable=False)
    source_item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    standard_item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    match_keywords_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32))
    feature_conditions_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(128))
    submitted_by: Mapped[str | None] = mapped_column(String(128))
    reviewed_by: Mapped[str | None] = mapped_column(String(128))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_comment: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class ItemMappingReviewORM(Base):
    __tablename__ = "item_mapping_review"
    __table_args__ = (
        Index("idx_item_mapping_review_status", "tenant_code", "status", "created_at"),
        Index("idx_item_mapping_review_item", "tenant_code", "source_item_name", "unit"),
        Index("idx_item_mapping_review_task", "tenant_code", "pricing_task_code", "status"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    tenant_code: Mapped[str] = mapped_column(String(64), default="default", nullable=False)
    review_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    pricing_task_code: Mapped[str | None] = mapped_column(String(64))
    workbook_name: Mapped[str | None] = mapped_column(String(255))
    source_sheet: Mapped[str | None] = mapped_column(String(255))
    source_row_number: Mapped[int | None] = mapped_column(Integer)
    source_item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32))
    feature_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    candidate_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    selected_standard_item_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(128))
    reviewed_by: Mapped[str | None] = mapped_column(String(128))
    review_comment: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)


class ItemMappingSettingORM(Base):
    __tablename__ = "item_mapping_setting"
    __table_args__ = (
        UniqueConstraint("tenant_code", name="uk_item_mapping_setting_tenant"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    tenant_code: Mapped[str] = mapped_column(String(64), default="default", nullable=False)
    confidence_threshold: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.8500"), nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class PriceRuleComponentORM(Base):
    __tablename__ = "price_rule_component"

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    price_rule_id: Mapped[int] = mapped_column(ForeignKey("price_rule.id", ondelete="CASCADE"), nullable=False)
    component_type: Mapped[str] = mapped_column(String(64), nullable=False)
    component_name: Mapped[str] = mapped_column(String(255), nullable=False)
    material_code: Mapped[str | None] = mapped_column(String(128))
    quota_code: Mapped[str | None] = mapped_column(String(128))
    unit: Mapped[str | None] = mapped_column(String(32))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("1"), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    price_source_type: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    source: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())


class PricingRunORM(Base):
    __tablename__ = "pricing_run"
    __table_args__ = (
        UniqueConstraint("tenant_code", "run_code", name="uk_pricing_run_code"),
        Index("idx_pricing_run_created_at", "tenant_code", "created_at"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    tenant_code: Mapped[str] = mapped_column(String(64), default="default", nullable=False)
    run_code: Mapped[str] = mapped_column(String(64), nullable=False)
    workbook_name: Mapped[str] = mapped_column(String(255), nullable=False)
    project_name: Mapped[str | None] = mapped_column(String(255))
    region_code: Mapped[str | None] = mapped_column(String(64))
    rule_source: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_version: Mapped[str | None] = mapped_column(String(64))
    item_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    priced_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unpriced_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    results: Mapped[list["PricingResultORM"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )


class PricingTaskORM(Base):
    __tablename__ = "pricing_task"
    __table_args__ = (
        UniqueConstraint("tenant_code", "task_code", name="uk_pricing_task_code"),
        Index("idx_pricing_task_status", "tenant_code", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    tenant_code: Mapped[str] = mapped_column(String(64), default="default", nullable=False)
    task_code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    message: Mapped[str | None] = mapped_column(String(512))
    workbook_name: Mapped[str] = mapped_column(String(255), nullable=False)
    upload_path: Mapped[str] = mapped_column(String(512), nullable=False)
    project_name: Mapped[str | None] = mapped_column(String(255))
    region_code: Mapped[str | None] = mapped_column(String(64))
    specialty: Mapped[str | None] = mapped_column(String(64))
    cost_category: Mapped[str | None] = mapped_column(String(64))
    rule_version: Mapped[str | None] = mapped_column(String(64))
    mysql_run_code: Mapped[str | None] = mapped_column(String(64))
    item_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    priced_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unpriced_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    excel_path: Mapped[str | None] = mapped_column(String(512))
    missing_rules_path: Mapped[str | None] = mapped_column(String(512))
    audit_path: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class PricingResultORM(Base):
    __tablename__ = "pricing_result"

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("pricing_run.id", ondelete="CASCADE"), nullable=False)
    source_sheet: Mapped[str] = mapped_column(String(255), nullable=False)
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    sequence_no: Mapped[str | None] = mapped_column(String(64))
    item_code: Mapped[str | None] = mapped_column(String(64))
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    total_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    rule_code: Mapped[str | None] = mapped_column(String(128))
    rule_version: Mapped[str | None] = mapped_column(String(64))
    price_source: Mapped[str | None] = mapped_column(String(255))
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0"), nullable=False)
    features_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    issues_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    run: Mapped[PricingRunORM] = relationship(back_populates="results")


class FeatureDictionaryORM(Base):
    __tablename__ = "feature_dictionary"

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    canonical_key: Mapped[str] = mapped_column(String(128), nullable=False)
    alias_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    data_type: Mapped[str] = mapped_column(String(32), default="text", nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())


class MaterialPriceORM(Base):
    __tablename__ = "material_price"

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    tenant_code: Mapped[str] = mapped_column(String(64), default="default", nullable=False)
    material_code: Mapped[str | None] = mapped_column(String(128))
    material_name: Mapped[str] = mapped_column(String(255), nullable=False)
    specification: Mapped[str | None] = mapped_column(String(255))
    region_code: Mapped[str | None] = mapped_column(String(64))
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    price_month: Mapped[str] = mapped_column(String(7), nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())


class MarketPriceQuoteORM(Base):
    __tablename__ = "market_price_quote"
    __table_args__ = (
        UniqueConstraint("tenant_code", "quote_code", name="uk_market_quote_code"),
        Index("idx_market_quote_status", "tenant_code", "status", "created_at"),
        Index("idx_market_quote_item", "tenant_code", "item_name", "region_code"),
        Index("idx_market_quote_task", "tenant_code", "pricing_task_code", "status"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    tenant_code: Mapped[str] = mapped_column(String(64), default="default", nullable=False)
    quote_code: Mapped[str] = mapped_column(String(64), nullable=False)
    pricing_task_code: Mapped[str | None] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    feature_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    region_code: Mapped[str | None] = mapped_column(String(64))
    unit: Mapped[str | None] = mapped_column(String(32))
    price_min: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    price_max: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    recommended_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    tax_included: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0"), nullable=False)
    source_urls_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    assumptions_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    raw_response: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending_review", nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(128))
    reviewed_by: Mapped[str | None] = mapped_column(String(128))
    review_comment: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)


class ModelCallLogORM(Base):
    __tablename__ = "model_call_log"
    __table_args__ = (
        UniqueConstraint("tenant_code", "call_code", name="uk_model_call_log_code"),
        Index("idx_model_call_log_status", "tenant_code", "status", "created_at"),
        Index("idx_model_call_log_task", "tenant_code", "task_code", "created_at"),
        Index("idx_model_call_log_provider", "tenant_code", "provider", "model", "created_at"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    tenant_code: Mapped[str] = mapped_column(String(64), default="default", nullable=False)
    call_code: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    scenario: Mapped[str] = mapped_column(String(64), nullable=False)
    task_code: Mapped[str | None] = mapped_column(String(64))
    item_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    response_excerpt: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class PlatformConfigORM(Base):
    __tablename__ = "platform_config"
    __table_args__ = (
        UniqueConstraint("tenant_code", "provider", name="uk_platform_config_provider"),
        Index("idx_platform_config_active", "tenant_code", "active", "provider"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    tenant_code: Mapped[str] = mapped_column(String(64), default="default", nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    api_key: Mapped[str | None] = mapped_column(String(1024))
    endpoint_type: Mapped[str] = mapped_column(String(32), default="chat_completions", nullable=False)
    enable_web_search: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    search_tool_type: Mapped[str | None] = mapped_column(String(64))
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    remark: Mapped[str | None] = mapped_column(String(512))
    updated_by: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class QuotaItemORM(Base):
    __tablename__ = "quota_item"
    __table_args__ = (
        UniqueConstraint("tenant_code", "quota_code", "version", name="uk_quota_item_code_version"),
        Index("idx_quota_item_lookup", "tenant_code", "specialty", "quota_name"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    tenant_code: Mapped[str] = mapped_column(String(64), default="default", nullable=False)
    quota_code: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    quota_name: Mapped[str] = mapped_column(String(255), nullable=False)
    specialty: Mapped[str | None] = mapped_column(String(64))
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    work_content: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    consumptions: Mapped[list["QuotaConsumptionORM"]] = relationship(
        back_populates="quota",
        cascade="all, delete-orphan",
    )


class QuotaConsumptionORM(Base):
    __tablename__ = "quota_consumption"
    __table_args__ = (
        Index("idx_quota_consumption_quota", "quota_item_id"),
        Index("idx_quota_consumption_material", "material_code"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    quota_item_id: Mapped[int] = mapped_column(ForeignKey("quota_item.id", ondelete="CASCADE"), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_code: Mapped[str | None] = mapped_column(String(128))
    resource_name: Mapped[str] = mapped_column(String(255), nullable=False)
    material_code: Mapped[str | None] = mapped_column(String(128))
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    consumption: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    quota: Mapped[QuotaItemORM] = relationship(back_populates="consumptions")


class UserRoleORM(Base):
    __tablename__ = "user_role"
    __table_args__ = (
        UniqueConstraint("tenant_code", "username", name="uk_user_role_username"),
        Index("idx_user_role_role", "tenant_code", "role", "active"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    tenant_code: Mapped[str] = mapped_column(String(64), default="default", nullable=False)
    username: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())


class SystemUserORM(Base):
    __tablename__ = "system_user"
    __table_args__ = (
        UniqueConstraint("tenant_code", "username", name="uk_system_user_username"),
        Index("idx_system_user_active", "tenant_code", "active", "username"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    tenant_code: Mapped[str] = mapped_column(String(64), default="default", nullable=False)
    username: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(128))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
