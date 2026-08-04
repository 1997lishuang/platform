from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from boq_pricing.api.dependencies import get_session_factory
from boq_pricing.bid_strategy.generation import dynamic_game_simulation, reverse_price_items
from boq_pricing.infrastructure.db import session_scope
from boq_pricing.infrastructure.orm_models import PricingResultORM, PricingRunORM
from boq_pricing.pricing.calculations import calculate_total_price


router = APIRouter(prefix="/bid-generation", tags=["bid-generation"])


class DynamicGameRequest(BaseModel):
    rule: dict[str, Any]
    floor: str
    ceiling: str
    step: str
    bidder_min: int = 5
    bidder_max: int = 12
    rounds: int = 300
    profiles: list[dict[str, Any]] = []


class ReversePriceRequest(BaseModel):
    run_code: str | None = None
    target_total: str
    items: list[dict[str, Any]] = []
    locked_items: dict[str, dict[str, Any]] = {}
    tenant_code: str = "default"


@router.post("/dynamic-game")
def dynamic_game(request: DynamicGameRequest) -> dict[str, Any]:
    try:
        return dynamic_game_simulation(
            rule=request.rule,
            floor=Decimal(request.floor),
            ceiling=Decimal(request.ceiling),
            step=Decimal(request.step),
            profiles=request.profiles,
            bidder_min=request.bidder_min,
            bidder_max=request.bidder_max,
            rounds=max(1, min(request.rounds, 5000)),
        )
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/reverse-pricing")
def reverse_pricing(request: ReversePriceRequest) -> dict[str, Any]:
    try:
        items = request.items or load_run_items(request.run_code, request.tenant_code)
        return reverse_price_items(
            items=items,
            target_total=Decimal(request.target_total),
            locked_items=request.locked_items,
        )
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def load_run_items(run_code: str | None, tenant_code: str) -> list[dict[str, Any]]:
    if not run_code:
        raise ValueError("请选择计价批次或传入明细。")
    with session_scope(get_session_factory()) as session:
        run = session.scalar(
            select(PricingRunORM).where(
                PricingRunORM.tenant_code == tenant_code,
                PricingRunORM.run_code == run_code,
            )
        )
        if run is None:
            raise ValueError("计价批次不存在。")
        rows = session.scalars(
            select(PricingResultORM)
            .where(PricingResultORM.run_id == run.id)
            .order_by(PricingResultORM.source_sheet.asc(), PricingResultORM.source_row_number.asc())
        ).all()
        return [
            {
                "itemKey": f"{row.source_sheet}:{row.source_row_number}",
                "sourceSheet": row.source_sheet,
                "sourceRowNumber": row.source_row_number,
                "itemCode": row.item_code,
                "itemName": row.item_name,
                "unit": row.unit,
                "quantity": str(row.quantity) if row.quantity is not None else "0",
                "unitPrice": str(row.unit_price) if row.unit_price is not None else "0",
                "totalPrice": str(calculate_total_price(row.quantity, row.unit_price) or "0"),
                "confidence": str(row.confidence),
                "features": dict(row.features_json or {}),
                "issues": list(row.issues_json or []),
            }
            for row in rows
        ]
