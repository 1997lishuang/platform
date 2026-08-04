from __future__ import annotations

import math
import re
from dataclasses import dataclass
from statistics import mean
from typing import Any


DEFAULT_SEED = 20260714


def _number(value: Any, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _round_if_configured(value: float, precision: Any) -> float:
    precision_value = _number(precision)
    if precision_value is None:
        return value
    return round(value, int(precision_value))


def trim_values(values: list[float], trim_mode: str | None, original_count: int | None = None) -> list[float]:
    sorted_values = sorted(values)
    original_count = len(values) if original_count is None else original_count
    if trim_mode == "drop_high" and len(sorted_values) > 1:
        return sorted_values[:-1]
    if trim_mode == "drop_low" and len(sorted_values) > 1:
        return sorted_values[1:]
    if trim_mode == "drop_high_low" and len(sorted_values) > 2:
        return sorted_values[1:-1]
    if trim_mode == "over5_drop_high_low" and len(sorted_values) > 5:
        return sorted_values[1:-1]
    if trim_mode == "rule2_correction" and original_count > 5 and len(sorted_values) > 1:
        return sorted_values[1:]
    if trim_mode == "rule4_count":
        if len(sorted_values) <= 5:
            return sorted_values
        if len(sorted_values) <= 7:
            return sorted_values[:-1]
        return sorted_values[1:-1]
    if trim_mode == "rule13_count":
        if len(sorted_values) <= 1:
            return sorted_values[:1]
        if len(sorted_values) < 3:
            return sorted_values
        if len(sorted_values) <= 5:
            return sorted_values[:-1]
        return sorted_values[1:-2]
    if trim_mode == "rule14_count":
        n = 3 if len(sorted_values) > 20 else 2 if len(sorted_values) > 10 else 1 if len(sorted_values) > 5 else 0
        return sorted_values[n:-n] if n > 0 and len(sorted_values) > n * 2 else sorted_values
    if trim_mode == "rule15_count":
        if len(sorted_values) >= 15:
            return sorted_values[2:-2]
        if len(sorted_values) >= 10:
            return sorted_values[1:-1]
        return sorted_values
    if trim_mode == "rule16_count":
        return sorted_values[1:-1] if len(sorted_values) > 5 else sorted_values
    if trim_mode == "rule18_count":
        return sorted_values[1:-1] if len(sorted_values) >= 5 else sorted_values
    if trim_mode == "rule20_count":
        if len(sorted_values) <= 3:
            return sorted_values
        if len(sorted_values) <= 6:
            return sorted_values[:-1]
        return sorted_values[1:-1]
    if trim_mode == "rule22_count":
        return sorted_values[1:-1] if len(sorted_values) >= 5 else sorted_values
    return sorted_values


def calculate_benchmark(rule: dict[str, Any], quotes: list[float]) -> float:
    if not quotes:
        raise ValueError("至少需要一个报价。")
    benchmark_rule = rule.get("benchmark") or {}
    correction = benchmark_rule.get("correction") or {}
    trim_mode = benchmark_rule.get("trimMode")
    factor = _number(benchmark_rule.get("factor"), 1) or 1

    if trim_mode == "rule19_control":
        initial_average = mean(quotes)
        lower = initial_average * 0.8
        upper = initial_average * 1.15
        basis = list(quotes)
        if len(quotes) > 3:
            in_range = [value for value in quotes if lower <= value <= upper]
            if len(in_range) >= 3:
                basis = in_range
            else:
                basis = list(quotes)
                while len(basis) > 3 and any(value < lower or value > upper for value in basis):
                    remove_index = max(range(len(basis)), key=lambda index: abs(basis[index] - initial_average))
                    basis.pop(remove_index)
        return _round_if_configured(mean(basis) * factor, benchmark_rule.get("roundPrecision"))

    if trim_mode == "rule22_count":
        base = mean(trim_values(quotes, "rule22_count", len(quotes)))
        float_rate = _number(benchmark_rule.get("floatRate"), 0) or 0
        return _round_if_configured(base * factor * (1 + float_rate), benchmark_rule.get("roundPrecision"))

    if trim_mode == "rule13_count" and len(quotes) <= 1:
        return _round_if_configured(min(quotes), benchmark_rule.get("roundPrecision"))

    if trim_mode in {"rule16_count", "rule18_count"}:
        base = trim_values(quotes, trim_mode, len(quotes))
        base_average = mean(base)
        filtered = [value for value in base if base_average and abs((value - base_average) / base_average) < 0.3]
        average_part = mean(filtered or base)
        min_part = min(base)
        return _round_if_configured(min_part * 0.5 + average_part * 0.5, benchmark_rule.get("roundPrecision"))

    benchmark = mean(trim_values(quotes, trim_mode, len(quotes))) * factor
    if not correction.get("enabled"):
        return _round_if_configured(benchmark, benchmark_rule.get("roundPrecision"))
    if len(quotes) in (correction.get("skipCounts") or []):
        return _round_if_configured(benchmark, benchmark_rule.get("roundPrecision"))

    rounds = max(1, int(_number(correction.get("rounds"), 1) or 1))
    for _ in range(rounds):
        lower_factor = _number(correction.get("lowerFactor"))
        upper_factor = _number(correction.get("upperFactor"))
        lower = benchmark * lower_factor if lower_factor is not None else -math.inf
        upper = benchmark * upper_factor if upper_factor is not None else math.inf
        if not any(value < lower or value >= upper for value in quotes):
            break
        if correction.get("mode") == "remove_outside":
            adjusted = [value for value in quotes if lower <= value < upper] or list(quotes)
        else:
            adjusted = [min(upper, max(lower, value)) for value in quotes]
        next_value = mean(trim_values(adjusted, correction.get("trimMode") or trim_mode, len(quotes))) * factor
        if abs(next_value - benchmark) < 0.000001:
            break
        benchmark = next_value
    return _round_if_configured(benchmark, benchmark_rule.get("roundPrecision"))


def score_quote(rule: dict[str, Any], quote: float, benchmark: float) -> dict[str, float]:
    score_rule = rule.get("score") or {}
    max_score = _number(rule.get("maxScore"), 100) or 100
    deviation = (quote - benchmark) / benchmark
    deviation_pct = deviation * 100
    score_type = score_rule.get("type")

    if score_type == "target_price":
        target = benchmark * (_number(score_rule.get("targetFactor"), 1) or 1)
        if quote < target and _number(score_rule.get("belowTargetScore")) is not None:
            score = _number(score_rule.get("belowTargetScore"), 0) or 0
        elif quote < target:
            score = max_score - ((target - quote) / target) * 100 * (_number(score_rule.get("lowPenaltyPerPct"), 0) or 0)
        else:
            score = max_score - ((quote - target) / target) * 100 * (_number(score_rule.get("highPenaltyPerPct"), 0) or 0)
    elif score_type == "band":
        full_low = _number(score_rule.get("fullLowPct"), 0) or 0
        full_high = _number(score_rule.get("fullHighPct"), 0) or 0
        if full_low < deviation_pct <= full_high:
            score = max_score
        elif deviation_pct <= full_low:
            score = max_score - (full_low - deviation_pct) * (_number(score_rule.get("lowPenaltyPerPct"), 0) or 0)
        else:
            score = max_score - (deviation_pct - full_high) * (_number(score_rule.get("highPenaltyPerPct"), 0) or 0)
    elif score_type == "rule15_band":
        if deviation_pct > 5:
            score = max_score - 2.5 - (deviation_pct - 5)
        elif deviation_pct > 0:
            score = max_score - deviation_pct * 0.5
        elif deviation_pct > -3:
            score = max_score
        elif deviation_pct > -10:
            score = max_score - (-3 - deviation_pct) * 0.5
        else:
            score = max_score - 3.5 - (-10 - deviation_pct)
    elif score_type == "rule16_tier":
        if deviation_pct > 10:
            score = max_score - 10 - (deviation_pct - 10) * 1.2
        elif deviation_pct > 0:
            score = max_score - deviation_pct
        elif deviation_pct >= -5:
            score = max_score
        elif deviation_pct >= -10:
            score = max_score - (-5 - deviation_pct) * 0.2
        else:
            score = max_score - 1 - (-10 - deviation_pct) * 0.5
    elif score_type == "rule17_table":
        if deviation_pct <= -19 or deviation_pct >= 5:
            score = 56
        elif -7 <= deviation_pct <= -3:
            score = 100
        else:
            points = [(-19, 56), (-16, 68), (-13, 80), (-10, 90), (-7, 100), (-3, 100), (-1, 90), (1, 80), (3, 68), (5, 56)]
            lower_point, upper_point = points[0], points[-1]
            for index in range(len(points) - 1):
                if points[index][0] <= deviation_pct <= points[index + 1][0]:
                    lower_point, upper_point = points[index], points[index + 1]
                    break
            ratio = (deviation_pct - lower_point[0]) / (upper_point[0] - lower_point[0])
            score = lower_point[1] + (upper_point[1] - lower_point[1]) * ratio
    elif score_type == "rule19_score":
        base_score = _number(score_rule.get("baseScore"), max_score) or max_score
        if deviation_pct > 5:
            score = base_score - 5 - (deviation_pct - 5) * 1.5
        elif deviation_pct > 0:
            score = base_score - deviation_pct
        elif deviation_pct == 0:
            score = base_score
        else:
            score = base_score + abs(deviation_pct) * 0.5
    elif score_type == "rule20_score":
        base_score = _number(score_rule.get("baseScore"), 95) or 95
        if deviation_pct > 0:
            score = max(60, base_score - deviation_pct)
        elif deviation_pct == 0:
            score = base_score
        else:
            below_pct = abs(deviation_pct)
            if below_pct <= 5:
                score = min(max_score, base_score + below_pct)
            elif below_pct < 20:
                score = max_score - (below_pct - 5)
            else:
                score = 85
    elif score_type == "rule21_score":
        base_score = _number(score_rule.get("baseScore"), 80) or 80
        rationality_score = _number(score_rule.get("rationalityScore"), 15) or 15
        if deviation_pct > 0:
            price_score = max(60, base_score - deviation_pct)
        elif deviation_pct == 0:
            price_score = base_score
        else:
            below_pct = abs(deviation_pct)
            if below_pct <= 5:
                price_score = min(85, base_score + below_pct)
            elif below_pct < 20:
                price_score = 85 - (below_pct - 5)
            else:
                price_score = 70
        score = price_score + rationality_score
    elif score_type == "rule22_score":
        score = max_score - deviation_pct * 2 if deviation_pct > 0 else max_score
    elif score_type == "distance":
        score = max_score - abs(deviation_pct) * (_number(score_rule.get("highPenaltyPerPct"), 1) or 1)
    else:
        score = (
            max_score - deviation_pct * (_number(score_rule.get("highPenaltyPerPct"), 0) or 0)
            if deviation_pct > 0
            else max_score - abs(deviation_pct) * (_number(score_rule.get("lowPenaltyPerPct"), 0) or 0)
        )

    min_score = _number(score_rule.get("minScore"), 0) or 0
    if score_type == "target_price" and quote >= benchmark * (_number(score_rule.get("targetFactor"), 1) or 1):
        score = max(min_score, score)
    final_score_raw = min(max_score, max(min_score, score))
    final_score = _round_if_configured(final_score_raw, score_rule.get("roundPrecision"))
    score_weight = _number(rule.get("scoreWeight"))
    weighted_score = final_score * score_weight if score_weight is not None else final_score
    return {"score": final_score, "weightedScore": weighted_score, "deviation": deviation}


def evaluate_bid(rule: dict[str, Any], competitors: list[dict[str, Any]], my_bid: float) -> dict[str, Any]:
    all_quotes = [float(item["amount"]) for item in competitors] + [my_bid]
    benchmark = calculate_benchmark(rule, all_quotes)
    scored_competitors = [{**item, **score_quote(rule, float(item["amount"]), benchmark)} for item in competitors]
    my_score = score_quote(rule, my_bid, benchmark)
    top_competitor = None
    for item in scored_competitors:
        if top_competitor is None or item["score"] > top_competitor["score"] or (item["score"] == top_competitor["score"] and item["amount"] < top_competitor["amount"]):
            top_competitor = item
    wins = top_competitor is None or my_score["score"] > top_competitor["score"] or (my_score["score"] == top_competitor["score"] and my_bid <= top_competitor["amount"])
    return {
        "bid": my_bid,
        "benchmark": benchmark,
        "myScore": my_score["score"],
        "weightedScore": my_score["weightedScore"],
        "myDeviation": my_score["deviation"],
        "wins": wins,
        "topCompetitor": top_competitor,
        "scoredCompetitors": scored_competitors,
    }


@dataclass
class SeededRandom:
    state: int = DEFAULT_SEED

    def random(self) -> float:
        self.state = (1664525 * self.state + 1013904223) & 0xFFFFFFFF
        return self.state / 4294967296


def normal_random(rand: SeededRandom, mean_value: float, sigma_value: float) -> float:
    u1 = max(rand.random(), 1e-12)
    u2 = max(rand.random(), 1e-12)
    z = math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)
    return mean_value + z * sigma_value


def generate_competitors(rand: SeededRandom, count: int, mean_value: float, sigma_value: float, ceiling: float) -> list[dict[str, Any]]:
    competitors = []
    for index in range(count):
        amount = normal_random(rand, mean_value, sigma_value)
        guard = 0
        while (amount <= 0 or amount > ceiling) and guard < 20:
            amount = normal_random(rand, mean_value, sigma_value)
            guard += 1
        amount = min(ceiling, max(1, amount))
        competitors.append({"name": f"模拟对手{index + 1}", "amount": amount})
    return competitors


def draw_bidder_count(rand: SeededRandom, bidder_mode: str, bidder_count: int, bidder_min: int, bidder_max: int) -> int:
    if bidder_mode == "fixed":
        return max(2, round(bidder_count))
    min_count = max(2, round(min(bidder_min, bidder_max)))
    max_count = max(min_count, round(max(bidder_min, bidder_max)))
    return min_count + math.floor(rand.random() * (max_count - min_count + 1))


def build_market_scenarios(ceiling: float, market_mean: float | None) -> list[dict[str, Any]]:
    if market_mean is not None and market_mean > 0:
        return [{"label": "手动 μ", "mean": market_mean, "weight": 1}]
    return [{"label": f"H×{factor}", "mean": ceiling * factor, "weight": 1} for factor in (0.85, 0.9, 0.95)]


def build_float_rate_scenarios(rule: dict[str, Any]) -> list[float]:
    benchmark = rule.get("benchmark") or {}
    configured = benchmark.get("floatRateScenarios")
    if isinstance(configured, list) and configured:
        values = [_number(item) for item in configured]
        return [value for value in values if value is not None] or [0]
    if rule.get("id") == "rule22":
        return [-0.1, -0.075, -0.05, -0.025, 0]
    fixed = _number(benchmark.get("floatRate"), 0) or 0
    return [fixed] if abs(fixed) > 1e-12 else [0]


def rule_with_float_rate(rule: dict[str, Any], float_rate: float) -> dict[str, Any]:
    current = _number((rule.get("benchmark") or {}).get("floatRate"), 0) or 0
    if abs(float_rate - current) < 1e-12:
        return rule
    copied = {**rule, "benchmark": {**(rule.get("benchmark") or {}), "floatRate": float_rate}}
    return copied


def monte_carlo_search(
    rule: dict[str, Any],
    floor: float,
    ceiling: float,
    step: float,
    market_mean: float | None,
    sigma: float,
    bidder_mode: str,
    bidder_count: int,
    bidder_min: int,
    bidder_max: int,
    simulation_count: int,
) -> dict[str, Any]:
    if floor <= 0 or ceiling <= 0 or ceiling < floor:
        raise ValueError("报价上下限不合法。")
    if step <= 0:
        raise ValueError("搜索步长必须大于 0。")
    if simulation_count <= 0:
        raise ValueError("模拟次数必须大于 0。")
    points: list[dict[str, Any]] = []
    best = None
    max_score = _number(rule.get("maxScore"), 100) or 100
    market_scenarios = build_market_scenarios(ceiling, market_mean)
    float_rate_scenarios = build_float_rate_scenarios(rule)

    candidate_count = math.floor((ceiling - floor) / step) + 1
    for candidate_index in range(candidate_count):
        bid = floor + candidate_index * step
        rand = SeededRandom(DEFAULT_SEED + round(bid))
        total_score = 0.0
        total_benchmark = 0.0
        wins = 0
        full_scores = 0
        total_bidder_count = 0
        for index in range(simulation_count):
            scenario = market_scenarios[index % len(market_scenarios)]
            scenario_rule = rule_with_float_rate(rule, float_rate_scenarios[index % len(float_rate_scenarios)])
            sampled_bidder_count = draw_bidder_count(rand, bidder_mode, bidder_count, bidder_min, bidder_max)
            competitors = generate_competitors(rand, max(1, sampled_bidder_count - 1), scenario["mean"], sigma, ceiling)
            result = evaluate_bid(scenario_rule, competitors, bid)
            total_score += result["myScore"]
            total_benchmark += result["benchmark"]
            total_bidder_count += sampled_bidder_count
            wins += 1 if result["wins"] else 0
            full_scores += 1 if result["myScore"] >= max_score - 1e-9 else 0
        point = {
            "bid": bid,
            "myScore": total_score / simulation_count,
            "benchmark": total_benchmark / simulation_count,
            "averageBidderCount": total_bidder_count / simulation_count,
            "winProbability": wins / simulation_count,
            "fullScoreProbability": full_scores / simulation_count,
            "expectedProfit": bid - floor,
            "wins": wins / simulation_count >= 0.5,
            "scoredCompetitors": [],
            "topCompetitor": None,
            "myDeviation": 0,
        }
        points.append(point)
        if best is None or point["myScore"] > best["myScore"] or (point["myScore"] == best["myScore"] and point["bid"] > best["bid"]):
            best = point
    return {"points": points, "best": best, "interval": analyze_bid_interval(points, best)}


def pick_nearest_point(points: list[dict[str, Any]], target_bid: float) -> dict[str, Any]:
    return min(points, key=lambda point: abs(point["bid"] - target_bid))


def analyze_bid_interval(points: list[dict[str, Any]], best: dict[str, Any]) -> dict[str, Any]:
    score_floor = best["myScore"] * 0.98
    win_floor = max(0, best["winProbability"] * 0.75)
    eligible = [{**point, "robust": point["myScore"] >= score_floor and point["winProbability"] >= win_floor} for point in points]
    best_index = next((index for index, point in enumerate(eligible) if point["bid"] == best["bid"]), 0)
    start_index = end_index = best_index
    while start_index > 0 and eligible[start_index - 1]["robust"]:
        start_index -= 1
    while end_index < len(eligible) - 1 and eligible[end_index + 1]["robust"]:
        end_index += 1
    segment = eligible[start_index : end_index + 1]
    low = segment[0] if segment else best
    high = segment[-1] if segment else best
    balanced = pick_nearest_point(segment or [best], (low["bid"] + high["bid"]) / 2)
    return {
        "low": low,
        "balanced": balanced,
        "high": high,
        "recommended": high,
        "scoreFloor": score_floor,
        "winFloor": win_floor,
        "count": len(segment),
        "isSinglePoint": low["bid"] == high["bid"],
    }


def parse_bid_line(line: str, index: int) -> dict[str, Any]:
    numeric_text_pattern = re.compile(r"^\d[\d,，]*(?:\.\d+)?$")
    for separator in re.finditer(r"[-–—,，:：\t]", line):
        name_part = line[: separator.start()].strip()
        amount_part = line[separator.end() :].strip()
        if re.search(r"[^\d\s,，.]", name_part) and numeric_text_pattern.match(amount_part):
            amount = float(amount_part.replace(",", "").replace("，", ""))
            if amount <= 0:
                raise ValueError(f"第 {index + 1} 行报价必须大于 0。")
            return {"name": re.sub(r"[\s,，:：;；\-–—]+$", "", name_part).strip() or f"投标人{index + 1}", "amount": amount, "rawLine": line}
    matches = list(re.finditer(r"\d[\d,，]*(?:\.\d+)?", line))
    if not matches:
        raise ValueError(f"第 {index + 1} 行没有识别到报价。")
    amount_match = matches[-1]
    amount = float(amount_match.group(0).replace(",", "").replace("，", ""))
    if amount <= 0:
        raise ValueError(f"第 {index + 1} 行报价必须大于 0。")
    name = re.sub(r"[\s,，:：;；\-–—]+$", "", line[: amount_match.start()]).strip()
    return {"name": name or f"投标人{index + 1}", "amount": amount, "rawLine": line}


def parse_actual_bids(text: str) -> list[dict[str, Any]]:
    bidders = [parse_bid_line(line.strip(), index) for index, line in enumerate(text.splitlines()) if line.strip()]
    if len(bidders) < 2:
        raise ValueError("至少需要输入 2 个已开标报价。")
    return bidders


def standard_deviation(values: list[float]) -> float:
    if len(values) <= 1:
        return 0
    avg = mean(values)
    variance = sum((value - avg) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(variance)


def calibration_sample_for_rule(rule: dict[str, Any], amounts: list[float]) -> list[float]:
    sorted_values = sorted(amounts)
    if rule.get("id") == "rule2" and len(sorted_values) > 5:
        return sorted_values[1:-1]
    return sorted_values


def backtest(rule: dict[str, Any], actual_bids_text: str) -> dict[str, Any]:
    bidders = parse_actual_bids(actual_bids_text)
    benchmark = calculate_benchmark(rule, [item["amount"] for item in bidders])
    scored = []
    for item in bidders:
        scored_item = {**item, **score_quote(rule, item["amount"], benchmark)}
        scored_item["rankScore"] = scored_item.get("weightedScore", scored_item["score"])
        scored.append(scored_item)
    ranked = sorted(scored, key=lambda item: (-item["rankScore"], item["amount"]))
    rows = []
    first = ranked[0]
    for index, item in enumerate(ranked):
        previous = ranked[index - 1] if index > 0 else None
        rows.append({
            **item,
            "benchmark": benchmark,
            "rank": index + 1,
            "gapToPreviousScore": previous["rankScore"] - item["rankScore"] if previous else 0,
            "gapToPreviousAmount": abs(item["amount"] - previous["amount"]) if previous else 0,
            "gapToFirstScore": first["rankScore"] - item["rankScore"],
            "gapToFirstAmount": abs(item["amount"] - first["amount"]),
        })
    return {"benchmark": benchmark, "rows": rows, "winner": rows[0]}


def calibrate(rule: dict[str, Any], actual_bids_text: str) -> dict[str, Any]:
    bidders = parse_actual_bids(actual_bids_text)
    amounts = [item["amount"] for item in bidders]
    sample = calibration_sample_for_rule(rule, amounts)
    return {
        "marketMean": round(mean(sample)),
        "sigma": round(standard_deviation(sample)),
        "bidderMode": "fixed",
        "bidderCount": len(bidders),
        "sampleCount": len(sample),
        "totalCount": len(bidders),
    }
