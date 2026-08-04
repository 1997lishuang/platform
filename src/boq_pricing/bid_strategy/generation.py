from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from boq_pricing.bid_strategy.engine import build_float_rate_scenarios, evaluate_bid, generate_competitors, rule_with_float_rate, SeededRandom


MONEY = Decimal("0.01")
UNIT_PRICE = Decimal("0.0001")


@dataclass(frozen=True)
class CompetitorProfile:
    name: str
    mean_factor: Decimal
    sigma_factor: Decimal
    probability: Decimal
    min_factor: Decimal | None = None
    max_factor: Decimal | None = None


def dynamic_game_simulation(
    rule: dict[str, Any],
    floor: Decimal,
    ceiling: Decimal,
    step: Decimal,
    profiles: list[dict[str, Any]],
    bidder_min: int,
    bidder_max: int,
    rounds: int,
) -> dict[str, Any]:
    parsed_profiles = normalize_profiles(profiles)
    candidates = decimal_range(floor, ceiling, step)
    float_rates = build_float_rate_scenarios(rule)
    points: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None

    for candidate_index, bid in enumerate(candidates):
        rand = SeededRandom(20260804 + candidate_index + int(bid))
        total_score = Decimal("0")
        total_benchmark = Decimal("0")
        wins = 0
        total_profit = Decimal("0")
        stress_wins = 0
        profile_counts: dict[str, int] = {profile.name: 0 for profile in parsed_profiles}
        profile_wins: dict[str, int] = {profile.name: 0 for profile in parsed_profiles}

        for index in range(rounds):
            bidder_count = bidder_min + int(rand.random() * max(1, bidder_max - bidder_min + 1))
            profile = choose_profile(rand, parsed_profiles)
            profile_counts[profile.name] += 1
            scenario_rule = rule_with_float_rate(rule, float_rates[index % len(float_rates)])
            competitors = profile_competitors(rand, max(1, bidder_count - 1), profile, ceiling)
            result = evaluate_bid(scenario_rule, competitors, float(bid))
            total_score += Decimal(str(result["myScore"]))
            total_benchmark += Decimal(str(result["benchmark"]))
            total_profit += bid - floor
            if result["wins"]:
                wins += 1
                profile_wins[profile.name] += 1
                if profile.mean_factor <= Decimal("0.88"):
                    stress_wins += 1

        point = {
            "bid": money(bid),
            "averageScore": money(total_score / Decimal(rounds)),
            "averageBenchmark": money(total_benchmark / Decimal(rounds)),
            "winProbability": float(Decimal(wins) / Decimal(rounds)),
            "stressWinProbability": float(Decimal(stress_wins) / Decimal(max(1, sum(count for name, count in profile_counts.items() if profile_by_name(parsed_profiles, name).mean_factor <= Decimal("0.88"))))),
            "expectedProfit": money(total_profit / Decimal(rounds)),
            "profileWinRates": {
                name: float(Decimal(profile_wins[name]) / Decimal(count)) if count else 0
                for name, count in profile_counts.items()
            },
        }
        points.append(point)
        if best is None or (point["averageScore"], point["winProbability"], point["bid"]) > (best["averageScore"], best["winProbability"], best["bid"]):
            best = point

    assert best is not None
    return {
        "points": points,
        "best": best,
        "profiles": [profile.__dict__ | {"mean_factor": str(profile.mean_factor), "sigma_factor": str(profile.sigma_factor), "probability": str(profile.probability), "min_factor": str(profile.min_factor) if profile.min_factor is not None else None, "max_factor": str(profile.max_factor) if profile.max_factor is not None else None} for profile in parsed_profiles],
        "summary": {
            "candidateCount": len(candidates),
            "rounds": rounds,
            "floor": money(floor),
            "ceiling": money(ceiling),
            "step": money(step),
        },
    }


def normalize_profiles(values: list[dict[str, Any]]) -> list[CompetitorProfile]:
    if not values:
        values = [
            {"name": "低价抢分型", "meanFactor": "0.86", "sigmaFactor": "0.025", "probability": "0.35", "minFactor": "0.78", "maxFactor": "0.92"},
            {"name": "稳健中位型", "meanFactor": "0.91", "sigmaFactor": "0.030", "probability": "0.45", "minFactor": "0.84", "maxFactor": "0.97"},
            {"name": "利润优先型", "meanFactor": "0.95", "sigmaFactor": "0.020", "probability": "0.20", "minFactor": "0.90", "maxFactor": "1.00"},
        ]
    profiles = [
        CompetitorProfile(
            name=str(item.get("name") or f"画像{index + 1}"),
            mean_factor=Decimal(str(item.get("meanFactor", item.get("mean_factor", "0.9")))),
            sigma_factor=Decimal(str(item.get("sigmaFactor", item.get("sigma_factor", "0.03")))),
            probability=max(Decimal("0"), Decimal(str(item.get("probability", "1")))),
            min_factor=optional_decimal(item.get("minFactor", item.get("min_factor"))),
            max_factor=optional_decimal(item.get("maxFactor", item.get("max_factor"))),
        )
        for index, item in enumerate(values)
    ]
    total = sum((profile.probability for profile in profiles), Decimal("0")) or Decimal("1")
    return [
        CompetitorProfile(
            profile.name,
            profile.mean_factor,
            profile.sigma_factor,
            profile.probability / total,
            profile.min_factor,
            profile.max_factor,
        )
        for profile in profiles
    ]


def choose_profile(rand: SeededRandom, profiles: list[CompetitorProfile]) -> CompetitorProfile:
    cursor = Decimal(str(rand.random()))
    acc = Decimal("0")
    for profile in profiles:
        acc += profile.probability
        if cursor <= acc:
            return profile
    return profiles[-1]


def profile_competitors(rand: SeededRandom, count: int, profile: CompetitorProfile, ceiling: Decimal) -> list[dict[str, Any]]:
    mean_value = float(ceiling * profile.mean_factor)
    sigma_value = float(ceiling * profile.sigma_factor)
    competitors = generate_competitors(rand, count, mean_value, sigma_value, float(ceiling))
    for item in competitors:
        amount = Decimal(str(item["amount"]))
        if profile.min_factor is not None:
            amount = max(amount, ceiling * profile.min_factor)
        if profile.max_factor is not None:
            amount = min(amount, ceiling * profile.max_factor)
        item["amount"] = float(money(amount))
        item["profile"] = profile.name
    return competitors


def profile_by_name(profiles: list[CompetitorProfile], name: str) -> CompetitorProfile:
    return next(profile for profile in profiles if profile.name == name)


def reverse_price_items(
    items: list[dict[str, Any]],
    target_total: Decimal,
    locked_items: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    locked_items = locked_items or {}
    rows = [normalize_cost_item(item) for item in items if Decimal(str(item.get("quantity") or "0")) > 0]
    if not rows:
        raise ValueError("没有可反推的计价明细。")

    for row in rows:
        override = locked_items.get(row["itemKey"], {})
        row["locked"] = bool(override.get("locked", row.get("locked", False)))
        row["weight"] = Decimal(str(override.get("weight", row.get("weight", "1")) or "1"))
        manual_total = optional_decimal(override.get("targetTotal"))
        manual_unit = optional_decimal(override.get("targetUnitPrice"))
        row["manual"] = manual_total is not None or manual_unit is not None
        if manual_total is not None:
            row["targetTotal"] = money(manual_total)
            row["targetUnitPrice"] = unit_price(row["targetTotal"] / row["quantity"])
            row["locked"] = True
        elif manual_unit is not None:
            row["targetUnitPrice"] = unit_price(manual_unit)
            row["targetTotal"] = money(row["targetUnitPrice"] * row["quantity"])
            row["locked"] = True

    locked_total = sum((row.get("targetTotal", row["costTotal"]) for row in rows if row["locked"]), Decimal("0"))
    adjustable = [row for row in rows if not row["locked"]]
    adjustable_cost = sum((row["costTotal"] for row in adjustable), Decimal("0"))
    remaining_target = target_total - locked_total
    if remaining_target < Decimal("0"):
        raise ValueError("固定项合计已经超过目标总价，无法反推。")
    profit_pool = remaining_target - adjustable_cost
    weighted_base = sum((max(row["costTotal"], Decimal("0.01")) * max(row["weight"], Decimal("0")) for row in adjustable), Decimal("0")) or Decimal("1")

    for row in adjustable:
        share = (max(row["costTotal"], Decimal("0.01")) * max(row["weight"], Decimal("0"))) / weighted_base
        row["targetTotal"] = money(row["costTotal"] + profit_pool * share)
        row["targetUnitPrice"] = unit_price(row["targetTotal"] / row["quantity"])

    rounded_total = sum((row["targetTotal"] for row in rows), Decimal("0"))
    diff = money(target_total - rounded_total)
    if diff and adjustable:
        carrier = max(adjustable, key=lambda item: item["costTotal"])
        carrier["targetTotal"] = money(carrier["targetTotal"] + diff)
        carrier["targetUnitPrice"] = unit_price(carrier["targetTotal"] / carrier["quantity"])

    for row in rows:
        row["profit"] = money(row["targetTotal"] - row["costTotal"])
        row["profitRate"] = float((row["profit"] / row["costTotal"]) if row["costTotal"] else Decimal("0"))
        row["issues"] = []
        if row["targetTotal"] < row["costTotal"]:
            row["issues"].append("目标合价低于成本")
        if row["confidence"] < Decimal("0.75"):
            row["issues"].append("成本置信度偏低")

    total_cost = sum((row["costTotal"] for row in rows), Decimal("0"))
    final_total = sum((row["targetTotal"] for row in rows), Decimal("0"))
    return {
        "summary": {
            "costTotal": money(total_cost),
            "targetTotal": money(target_total),
            "finalTotal": money(final_total),
            "difference": money(target_total - final_total),
            "profit": money(final_total - total_cost),
            "profitRate": float((final_total - total_cost) / total_cost) if total_cost else 0,
            "lockedTotal": money(locked_total),
            "adjustableCount": len(adjustable),
            "itemCount": len(rows),
        },
        "items": [serialize_row(row) for row in rows],
    }


def normalize_cost_item(item: dict[str, Any]) -> dict[str, Any]:
    quantity = Decimal(str(item.get("quantity") or "0"))
    unit = Decimal(str(item.get("unitPrice") or item.get("unit_price") or "0"))
    total = optional_decimal(item.get("totalPrice") or item.get("total_price"))
    cost_total = money(total if total is not None else quantity * unit)
    return {
        "itemKey": str(item.get("itemKey") or f"{item.get('sourceSheet', item.get('source_sheet', ''))}:{item.get('sourceRowNumber', item.get('source_row_number', ''))}"),
        "sourceSheet": item.get("sourceSheet") or item.get("source_sheet"),
        "sourceRowNumber": item.get("sourceRowNumber") or item.get("source_row_number"),
        "itemCode": item.get("itemCode") or item.get("item_code"),
        "itemName": item.get("itemName") or item.get("item_name"),
        "unit": item.get("unit"),
        "quantity": quantity,
        "costUnitPrice": unit_price(unit),
        "costTotal": cost_total,
        "confidence": Decimal(str(item.get("confidence") or "1")),
        "features": item.get("features") or {},
        "issues": item.get("issues") or [],
        "locked": bool(item.get("locked", False)),
        "weight": Decimal(str(item.get("weight") or "1")),
    }


def serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **{key: value for key, value in row.items() if key not in {"quantity", "costUnitPrice", "costTotal", "targetUnitPrice", "targetTotal", "profit", "weight", "confidence"}},
        "quantity": str(row["quantity"]),
        "costUnitPrice": str(row["costUnitPrice"]),
        "costTotal": str(row["costTotal"]),
        "targetUnitPrice": str(row["targetUnitPrice"]),
        "targetTotal": str(row["targetTotal"]),
        "profit": str(row["profit"]),
        "profitRate": row["profitRate"],
        "weight": str(row["weight"]),
        "confidence": str(row["confidence"]),
    }


def decimal_range(start: Decimal, end: Decimal, step: Decimal) -> list[Decimal]:
    values = []
    current = start
    while current <= end:
        values.append(current)
        current += step
    return values


def optional_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def unit_price(value: Decimal) -> Decimal:
    return value.quantize(UNIT_PRICE, rounding=ROUND_HALF_UP)
