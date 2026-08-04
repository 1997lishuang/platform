from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from boq_pricing.bid_strategy.engine import backtest, calibrate, monte_carlo_search
from boq_pricing.bid_strategy.rule_parser import (
    health,
    list_rule_files,
    list_rules,
    parse_rule_file,
    save_rule_file,
    upsert_rule,
)


router = APIRouter(prefix="/bid-strategy", tags=["bid-strategy"])


class ParseRuleRequest(BaseModel):
    path: str
    allow_heavy: bool = False


class SaveRuleRequest(BaseModel):
    rule: dict[str, Any]


class SimulationRequest(BaseModel):
    rule: dict[str, Any]
    floor: float
    ceiling: float
    step: float
    marketMean: float | None = None
    sigma: float
    bidderMode: str = "range"
    bidderCount: int = 8
    bidderMin: int = 3
    bidderMax: int = 12
    simulationCount: int = 300


class ActualBidsRequest(BaseModel):
    rule: dict[str, Any]
    actualBids: str


@router.get("/health")
def bid_strategy_health() -> dict[str, Any]:
    return health()


@router.get("/rules")
def get_rules() -> list[dict[str, Any]]:
    return list_rules()


@router.post("/rules")
def save_rule(request: SaveRuleRequest) -> dict[str, Any]:
    try:
        return upsert_rule(request.rule)
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/rule-files")
def get_rule_files() -> list[dict[str, Any]]:
    return list_rule_files()


@router.post("/rule-files")
async def upload_rule_file(file: UploadFile = File(...)) -> dict[str, Any]:
    try:
        return save_rule_file(file.filename or "rule-file", await file.read())
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/parse-rule")
def parse_rule(request: ParseRuleRequest) -> dict[str, Any]:
    try:
        return parse_rule_file(request.path, allow_heavy=request.allow_heavy)
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/simulate")
def simulate(request: SimulationRequest) -> dict[str, Any]:
    try:
        bidder_count = max(3, request.bidderCount)
        bidder_min = max(3, request.bidderMin)
        bidder_max = max(bidder_min, request.bidderMax)
        return monte_carlo_search(
            rule=request.rule,
            floor=request.floor,
            ceiling=request.ceiling,
            step=request.step,
            market_mean=request.marketMean,
            sigma=request.sigma,
            bidder_mode=request.bidderMode,
            bidder_count=bidder_count,
            bidder_min=bidder_min,
            bidder_max=bidder_max,
            simulation_count=request.simulationCount,
        )
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/backtest")
def run_backtest(request: ActualBidsRequest) -> dict[str, Any]:
    try:
        return backtest(request.rule, request.actualBids)
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/calibrate")
def run_calibration(request: ActualBidsRequest) -> dict[str, Any]:
    try:
        return calibrate(request.rule, request.actualBids)
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
