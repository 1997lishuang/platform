from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from boq_pricing.infrastructure.db import session_scope
from boq_pricing.infrastructure.orm_models import ModelCallLogORM


class ModelCallLogRepository:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        tenant_code: str = "default",
    ) -> None:
        self._session_factory = session_factory
        self._tenant_code = tenant_code

    def start(
        self,
        *,
        provider: str,
        model: str,
        scenario: str,
        task_code: str | None = None,
        item_name: str | None = None,
        username: str | None = None,
    ) -> str:
        call_code = uuid.uuid4().hex
        with session_scope(self._session_factory) as session:
            session.add(
                ModelCallLogORM(
                    tenant_code=self._tenant_code,
                    call_code=call_code,
                    provider=provider,
                    model=model,
                    scenario=scenario,
                    task_code=task_code,
                    item_name=item_name,
                    status="running",
                    created_by=username,
                )
            )
        return call_code

    def succeed(
        self,
        call_code: str,
        *,
        duration_ms: int,
        token_usage: Mapping[str, Any] | None = None,
        response_excerpt: str | None = None,
    ) -> None:
        usage = normalize_token_usage(token_usage)
        with session_scope(self._session_factory) as session:
            row = self._get_for_update(session, call_code)
            if row is None:
                return
            row.status = "succeeded"
            row.prompt_tokens = usage.get("prompt_tokens")
            row.completion_tokens = usage.get("completion_tokens")
            row.total_tokens = usage.get("total_tokens")
            row.duration_ms = duration_ms
            row.response_excerpt = truncate(response_excerpt, 4000)
            row.error_message = None
            row.finished_at = datetime.now()

    def fail(
        self,
        call_code: str,
        *,
        duration_ms: int,
        error_message: str,
        response_excerpt: str | None = None,
    ) -> None:
        with session_scope(self._session_factory) as session:
            row = self._get_for_update(session, call_code)
            if row is None:
                return
            row.status = "failed"
            row.duration_ms = duration_ms
            row.error_message = truncate(error_message, 4000)
            row.response_excerpt = truncate(response_excerpt, 4000)
            row.finished_at = datetime.now()

    def list_page(
        self,
        *,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ModelCallLogORM], int]:
        normalized_page = max(page, 1)
        normalized_size = max(1, min(page_size, 100))
        with session_scope(self._session_factory) as session:
            filters = [ModelCallLogORM.tenant_code == self._tenant_code]
            if status:
                filters.append(ModelCallLogORM.status == status)
            total = session.scalar(select(func.count()).select_from(ModelCallLogORM).where(*filters)) or 0
            rows = list(
                session.scalars(
                    select(ModelCallLogORM)
                    .where(*filters)
                    .order_by(ModelCallLogORM.created_at.desc(), ModelCallLogORM.id.desc())
                    .offset((normalized_page - 1) * normalized_size)
                    .limit(normalized_size)
                )
            )
            return rows, int(total)

    def _get_for_update(self, session: Session, call_code: str) -> ModelCallLogORM | None:
        return session.scalar(
            select(ModelCallLogORM).where(
                ModelCallLogORM.tenant_code == self._tenant_code,
                ModelCallLogORM.call_code == call_code,
            )
        )


def normalize_token_usage(token_usage: Mapping[str, Any] | None) -> dict[str, int | None]:
    if not token_usage:
        return {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
    prompt_tokens = to_int_or_none(token_usage.get("prompt_tokens") or token_usage.get("input_tokens"))
    completion_tokens = to_int_or_none(token_usage.get("completion_tokens") or token_usage.get("output_tokens"))
    total_tokens = to_int_or_none(token_usage.get("total_tokens"))
    if total_tokens is None and (prompt_tokens is not None or completion_tokens is not None):
        total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


def to_int_or_none(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def truncate(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    return value[:limit]
