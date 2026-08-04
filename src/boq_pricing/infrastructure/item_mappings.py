from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from boq_pricing.domain import BillItem
from boq_pricing.infrastructure.db import session_scope
from boq_pricing.infrastructure.orm_models import ItemMappingORM, ItemMappingReviewORM, ItemMappingSettingORM
from boq_pricing.pricing.engine import compact, normalize_unit, score_name_match, value_matches


@dataclass(frozen=True)
class ItemMappingInput:
    mapping_code: str
    source_item_name: str
    standard_item_name: str
    match_keywords: list[str]
    unit: str | None = None
    feature_conditions: dict[str, str] | None = None
    status: str = "draft"
    priority: int = 100
    active: bool = True


@dataclass(frozen=True)
class ItemMappingSetting:
    confidence_threshold: Decimal


@dataclass(frozen=True)
class MappingCandidate:
    mapping_code: str
    standard_item_name: str
    score: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "mapping_code": self.mapping_code,
            "standard_item_name": self.standard_item_name,
            "score": round(self.score, 4),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class MappingDecision:
    status: str
    standard_item_name: str | None
    candidates: list[MappingCandidate]


class ItemMappingRepository:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        tenant_code: str = "default",
        pricing_task_code: str | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._tenant_code = tenant_code
        self._pricing_task_code = pricing_task_code

    def list_page(
        self,
        status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ItemMappingORM], int]:
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        filters = [ItemMappingORM.tenant_code == self._tenant_code]
        if status:
            filters.append(ItemMappingORM.status == status)
        if keyword:
            like = f"%{keyword}%"
            filters.append(
                or_(
                    ItemMappingORM.mapping_code.like(like),
                    ItemMappingORM.source_item_name.like(like),
                    ItemMappingORM.standard_item_name.like(like),
                )
            )
        with session_scope(self._session_factory) as session:
            total = session.scalar(select(func.count()).select_from(ItemMappingORM).where(and_(*filters))) or 0
            rows = session.scalars(
                select(ItemMappingORM)
                .where(and_(*filters))
                .order_by(ItemMappingORM.updated_at.desc(), ItemMappingORM.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            for row in rows:
                session.expunge(row)
            return list(rows), int(total)

    def upsert(self, payload: ItemMappingInput, username: str | None = None) -> ItemMappingORM:
        with session_scope(self._session_factory) as session:
            row = session.scalar(
                select(ItemMappingORM).where(
                    ItemMappingORM.tenant_code == self._tenant_code,
                    ItemMappingORM.mapping_code == payload.mapping_code,
                )
            )
            if row is None:
                row = ItemMappingORM(
                    tenant_code=self._tenant_code,
                    mapping_code=payload.mapping_code,
                    created_by=username,
                )
                session.add(row)
            row.source_item_name = payload.source_item_name
            row.standard_item_name = payload.standard_item_name
            row.match_keywords_json = payload.match_keywords
            row.unit = payload.unit
            row.feature_conditions_json = payload.feature_conditions or {}
            row.status = payload.status
            row.priority = payload.priority
            row.active = payload.active
            session.flush()
            session.refresh(row)
            session.expunge(row)
            return row

    def submit(self, mapping_code: str, username: str) -> ItemMappingORM:
        return self._set_mapping_status(mapping_code, "reviewing", username, None)

    def approve(self, mapping_code: str, username: str, comment: str | None = None) -> ItemMappingORM:
        return self._set_mapping_status(mapping_code, "active", username, comment)

    def reject(self, mapping_code: str, username: str, comment: str | None = None) -> ItemMappingORM:
        return self._set_mapping_status(mapping_code, "rejected", username, comment)

    def delete(self, mapping_code: str) -> bool:
        with session_scope(self._session_factory) as session:
            row = session.scalar(
                select(ItemMappingORM).where(
                    ItemMappingORM.tenant_code == self._tenant_code,
                    ItemMappingORM.mapping_code == mapping_code,
                )
            )
            if row is None:
                return False
            session.delete(row)
            return True

    def get_setting(self) -> ItemMappingSetting:
        with session_scope(self._session_factory) as session:
            row = session.scalar(
                select(ItemMappingSettingORM).where(ItemMappingSettingORM.tenant_code == self._tenant_code)
            )
            if row is None:
                row = ItemMappingSettingORM(
                    tenant_code=self._tenant_code,
                    confidence_threshold=Decimal("0.8500"),
                )
                session.add(row)
                session.flush()
            return ItemMappingSetting(confidence_threshold=Decimal(row.confidence_threshold))

    def update_setting(self, confidence_threshold: Decimal, username: str | None = None) -> ItemMappingSetting:
        threshold = min(Decimal("1.0000"), max(Decimal("0.0000"), confidence_threshold))
        with session_scope(self._session_factory) as session:
            row = session.scalar(
                select(ItemMappingSettingORM).where(ItemMappingSettingORM.tenant_code == self._tenant_code)
            )
            if row is None:
                row = ItemMappingSettingORM(tenant_code=self._tenant_code)
                session.add(row)
            row.confidence_threshold = threshold
            row.updated_by = username
            return ItemMappingSetting(confidence_threshold=threshold)

    def resolve(self, item: BillItem) -> MappingDecision:
        threshold = float(self.get_setting().confidence_threshold)
        mappings = self._load_active_mappings()
        candidates = sorted(
            (candidate for mapping in mappings if (candidate := score_mapping(mapping, item)) is not None),
            key=lambda candidate: candidate.score,
            reverse=True,
        )
        if not candidates:
            return MappingDecision("unmapped", None, [])
        if len(candidates) > 1 and candidates[0].standard_item_name == candidates[1].standard_item_name:
            same_target = [
                candidate
                for candidate in candidates
                if candidate.standard_item_name == candidates[0].standard_item_name
            ]
            if candidates[0].score < threshold:
                return MappingDecision("low_confidence", None, same_target[:5])
            return MappingDecision("mapped", candidates[0].standard_item_name, same_target[:5])
        if len(candidates) > 1 and candidates[0].score - candidates[1].score <= 0.15:
            return MappingDecision("ambiguous", None, candidates[:5])
        if candidates[0].score < threshold:
            return MappingDecision("low_confidence", None, candidates[:5])
        return MappingDecision("mapped", candidates[0].standard_item_name, candidates[:5])

    def create_ambiguity_review(self, item: BillItem, candidates: list[MappingCandidate]) -> ItemMappingReviewORM:
        feature_json = item.features.values if item.features else {}
        with session_scope(self._session_factory) as session:
            existing_rows = session.scalars(
                select(ItemMappingReviewORM).where(
                    ItemMappingReviewORM.tenant_code == self._tenant_code,
                    ItemMappingReviewORM.status == "pending",
                    ItemMappingReviewORM.source_item_name == item.item_name,
                    ItemMappingReviewORM.unit == item.unit,
                    ItemMappingReviewORM.pricing_task_code == self._pricing_task_code,
                )
            ).all()
            for existing in existing_rows:
                if dict(existing.feature_json or {}) == dict(feature_json):
                    session.expunge(existing)
                    return existing
            row = ItemMappingReviewORM(
                tenant_code=self._tenant_code,
                review_code=uuid.uuid4().hex,
                pricing_task_code=self._pricing_task_code,
                workbook_name=item.source.workbook,
                source_sheet=item.source.sheet,
                source_row_number=item.source.row_number,
                source_item_name=item.item_name,
                unit=item.unit,
                feature_json=feature_json,
                candidate_json=[candidate.to_dict() for candidate in candidates],
                status="pending",
            )
            session.add(row)
            session.flush()
            session.refresh(row)
            session.expunge(row)
            return row

    def has_pending_reviews_for_task(self, pricing_task_code: str) -> bool:
        with session_scope(self._session_factory) as session:
            count = session.scalar(
                select(func.count()).select_from(ItemMappingReviewORM).where(
                    ItemMappingReviewORM.tenant_code == self._tenant_code,
                    ItemMappingReviewORM.pricing_task_code == pricing_task_code,
                    ItemMappingReviewORM.status == "pending",
                )
            )
            return bool(count)

    def list_reviews(
        self,
        status: str | None = None,
        persisted: bool | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ItemMappingReviewORM], int]:
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        filters = [ItemMappingReviewORM.tenant_code == self._tenant_code]
        if status:
            filters.append(ItemMappingReviewORM.status == status)
        if keyword:
            like = f"%{keyword}%"
            filters.append(or_(ItemMappingReviewORM.source_item_name.like(like), ItemMappingReviewORM.selected_standard_item_name.like(like)))
        if persisted is not None:
            persisted_clause = review_persisted_clause()
            filters.append(persisted_clause if persisted else ~persisted_clause)
        with session_scope(self._session_factory) as session:
            total = session.scalar(select(func.count()).select_from(ItemMappingReviewORM).where(and_(*filters))) or 0
            rows = session.scalars(
                select(ItemMappingReviewORM)
                .where(and_(*filters))
                .order_by(ItemMappingReviewORM.created_at.desc(), ItemMappingReviewORM.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            for row in rows:
                setattr(row, "_persisted", self._is_review_persisted(session, row))
                session.expunge(row)
            return list(rows), int(total)

    def resolve_review(
        self,
        review_code: str,
        standard_item_name: str,
        username: str,
        comment: str | None = None,
        create_mapping: bool = True,
    ) -> ItemMappingReviewORM:
        with session_scope(self._session_factory) as session:
            row = session.scalar(
                select(ItemMappingReviewORM).where(
                    ItemMappingReviewORM.tenant_code == self._tenant_code,
                    ItemMappingReviewORM.review_code == review_code,
                )
            )
            if row is None:
                raise KeyError(review_code)
            row.selected_standard_item_name = standard_item_name
            row.status = "resolved"
            row.reviewed_by = username
            row.review_comment = comment
            row.reviewed_at = datetime.now(UTC)
            if create_mapping:
                mapping_code = f"MAP-{uuid.uuid4().hex[:10]}"
                session.add(
                    ItemMappingORM(
                        tenant_code=self._tenant_code,
                        mapping_code=mapping_code,
                        source_item_name=row.source_item_name,
                        standard_item_name=standard_item_name,
                        match_keywords_json=[],
                        unit=row.unit,
                        feature_conditions_json=dict(row.feature_json or {}),
                        status="active",
                        active=True,
                        priority=50,
                        created_by=username,
                        reviewed_by=username,
                        reviewed_at=datetime.now(UTC),
                        review_comment=f"由歧义校准 {review_code} 生成",
                    )
                )
            session.flush()
            session.refresh(row)
            session.expunge(row)
            return row

    def _load_active_mappings(self) -> list[ItemMappingORM]:
        with session_scope(self._session_factory) as session:
            rows = session.scalars(
                select(ItemMappingORM)
                .where(
                    ItemMappingORM.tenant_code == self._tenant_code,
                    ItemMappingORM.status == "active",
                    ItemMappingORM.active.is_(True),
                )
                .order_by(ItemMappingORM.priority.asc(), ItemMappingORM.id.asc())
            ).all()
            for row in rows:
                session.expunge(row)
            return list(rows)

    def _is_review_persisted(self, session: Session, row: ItemMappingReviewORM) -> bool:
        if not row.selected_standard_item_name:
            return False
        count = session.scalar(
            select(func.count()).select_from(ItemMappingORM).where(
                ItemMappingORM.tenant_code == row.tenant_code,
                ItemMappingORM.source_item_name == row.source_item_name,
                ItemMappingORM.standard_item_name == row.selected_standard_item_name,
                ItemMappingORM.unit == row.unit,
                ItemMappingORM.status == "active",
                ItemMappingORM.active.is_(True),
            )
        )
        return bool(count)

    def _set_mapping_status(self, mapping_code: str, status: str, username: str, comment: str | None) -> ItemMappingORM:
        with session_scope(self._session_factory) as session:
            row = session.scalar(
                select(ItemMappingORM).where(
                    ItemMappingORM.tenant_code == self._tenant_code,
                    ItemMappingORM.mapping_code == mapping_code,
                )
            )
            if row is None:
                raise KeyError(mapping_code)
            row.status = status
            if status == "reviewing":
                row.submitted_by = username
            if status in {"active", "rejected"}:
                row.reviewed_by = username
                row.reviewed_at = datetime.now(UTC)
                row.review_comment = comment
            session.flush()
            session.refresh(row)
            session.expunge(row)
            return row


def review_persisted_clause():
    return exists(
        select(ItemMappingORM.id).where(
            ItemMappingORM.tenant_code == ItemMappingReviewORM.tenant_code,
            ItemMappingORM.source_item_name == ItemMappingReviewORM.source_item_name,
            ItemMappingORM.standard_item_name == ItemMappingReviewORM.selected_standard_item_name,
            or_(
                ItemMappingORM.unit == ItemMappingReviewORM.unit,
                and_(ItemMappingORM.unit.is_(None), ItemMappingReviewORM.unit.is_(None)),
            ),
            ItemMappingORM.status == "active",
            ItemMappingORM.active.is_(True),
        )
    )


def score_mapping(mapping: ItemMappingORM, item: BillItem) -> MappingCandidate | None:
    item_name = compact(item.item_name).lower()
    source_name = compact(mapping.source_item_name).lower()
    score = 0.0
    reasons: list[str] = []

    name_similarity = score_name_match(item_name, source_name)
    if source_name and name_similarity >= 0.99:
        score += 0.55
        reasons.append("项目名称完全匹配")
    elif source_name and name_similarity >= 0.45:
        score += 0.55 * name_similarity
        reasons.append(f"项目名称相似度 {name_similarity:.0%}")

    keyword_hits = 0
    for keyword in mapping.match_keywords_json or []:
        if compact(keyword).lower() in item_name:
            keyword_hits += 1
    if keyword_hits:
        score += min(0.25, keyword_hits * 0.08)
        reasons.append(f"关键词命中 {keyword_hits} 个")

    if mapping.unit:
        if item.unit and normalize_unit(mapping.unit) == normalize_unit(item.unit):
            score += 0.12
            reasons.append("单位匹配")
        else:
            return None

    features = item.features.values if item.features else {}
    conditions = mapping.feature_conditions_json or {}
    if conditions:
        matched = sum(1 for key, expected in conditions.items() if value_matches(features.get(key, ""), str(expected)))
        if matched != len(conditions):
            return None
        score += 0.28
        reasons.append("特征条件匹配")

    if score <= 0:
        return None
    priority_bonus = max(0, 100 - int(mapping.priority or 100)) / 1000
    return MappingCandidate(
        mapping_code=mapping.mapping_code,
        standard_item_name=mapping.standard_item_name,
        score=min(1.0, score + priority_bonus),
        reason="；".join(reasons),
    )
