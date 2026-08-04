from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from boq_pricing.infrastructure.db import session_scope
from boq_pricing.infrastructure.market_quote_provider import MarketQuoteProviderConfig
from boq_pricing.infrastructure.orm_models import PlatformConfigORM


@dataclass(frozen=True)
class PlatformConfigInput:
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


class PlatformConfigRepository:
    def __init__(self, session_factory: sessionmaker[Session], tenant_code: str = "default") -> None:
        self._session_factory = session_factory
        self._tenant_code = tenant_code

    def list(self) -> list[PlatformConfigORM]:
        with session_scope(self._session_factory) as session:
            rows = session.scalars(
                select(PlatformConfigORM)
                .where(PlatformConfigORM.tenant_code == self._tenant_code)
                .order_by(PlatformConfigORM.provider)
            ).all()
            for row in rows:
                session.expunge(row)
            return list(rows)

    def get_active_provider_config(self, provider: str) -> MarketQuoteProviderConfig | None:
        row = self.get(provider)
        if row is None or not row.active:
            return None
        endpoint_type = row.endpoint_type
        search_tool_type = row.search_tool_type
        if row.provider == "doubao" and row.enable_web_search and search_tool_type == "web_search_preview":
            search_tool_type = "web_search"
            endpoint_type = "responses"
        return MarketQuoteProviderConfig(
            provider=row.provider,
            api_key=row.api_key,
            model=row.model,
            base_url=row.base_url,
            timeout_seconds=row.timeout_seconds,
            endpoint_type=endpoint_type,
            enable_web_search=row.enable_web_search,
            search_tool_type=search_tool_type,
        )

    def get(self, provider: str) -> PlatformConfigORM | None:
        with session_scope(self._session_factory) as session:
            row = session.scalar(
                select(PlatformConfigORM).where(
                    PlatformConfigORM.tenant_code == self._tenant_code,
                    PlatformConfigORM.provider == provider.lower(),
                )
            )
            if row is not None:
                session.expunge(row)
            return row

    def upsert(self, payload: PlatformConfigInput, username: str | None = None) -> PlatformConfigORM:
        provider = payload.provider.lower()
        with session_scope(self._session_factory) as session:
            row = session.scalar(
                select(PlatformConfigORM).where(
                    PlatformConfigORM.tenant_code == self._tenant_code,
                    PlatformConfigORM.provider == provider,
                )
            )
            if row is None:
                row = PlatformConfigORM(
                    tenant_code=self._tenant_code,
                    provider=provider,
                    display_name=payload.display_name,
                    base_url=payload.base_url,
                    model=payload.model,
                    api_key=payload.api_key or None,
                    endpoint_type=payload.endpoint_type,
                    enable_web_search=payload.enable_web_search,
                    search_tool_type=payload.search_tool_type,
                    timeout_seconds=payload.timeout_seconds,
                    active=payload.active,
                    remark=payload.remark,
                    updated_by=username,
                )
                session.add(row)
            else:
                row.display_name = payload.display_name
                row.base_url = payload.base_url
                row.model = payload.model
                if payload.api_key:
                    row.api_key = payload.api_key
                row.endpoint_type = payload.endpoint_type
                row.enable_web_search = payload.enable_web_search
                row.search_tool_type = payload.search_tool_type
                row.timeout_seconds = payload.timeout_seconds
                row.active = payload.active
                row.remark = payload.remark
                row.updated_by = username
            session.flush()
            session.refresh(row)
            session.expunge(row)
            return row
