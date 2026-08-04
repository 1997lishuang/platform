from __future__ import annotations

from boq_pricing.bid_strategy.engine import backtest, calculate_benchmark, monte_carlo_search, score_quote
from boq_pricing.bid_strategy.rule_parser import normalize_rule


def test_rule2_benchmark_and_band_score() -> None:
    rule = normalize_rule(
        {
            "id": "rule2",
            "maxScore": 40,
            "benchmark": {
                "factor": 0.95,
                "trimMode": "over5_drop_high_low",
                "correction": {
                    "enabled": True,
                    "mode": "remove_outside",
                    "upperFactor": 1.15,
                    "rounds": 1,
                    "trimMode": "rule2_correction",
                    "skipCounts": [2],
                },
            },
            "score": {
                "type": "band",
                "fullLowPct": -5,
                "fullHighPct": 0,
                "highPenaltyPerPct": 0.6,
                "lowPenaltyPerPct": 0.4,
                "minScore": 0,
            },
        }
    )
    benchmark = calculate_benchmark(rule, [90, 95, 100, 105, 110, 200])
    assert benchmark == 97.375
    assert score_quote(rule, 95, benchmark)["score"] == 40
    assert score_quote(rule, 100, benchmark)["score"] < 40


def test_rule22_float_rate_scenario_and_simulation_interval() -> None:
    rule = normalize_rule(
        {
            "id": "rule22",
            "maxScore": 100,
            "benchmark": {
                "factor": 1,
                "floatRateScenarios": [-0.1, -0.05, 0],
                "trimMode": "rule22_count",
                "correction": {"enabled": False},
            },
            "score": {"type": "rule22_score", "minScore": 0},
        }
    )
    result = monte_carlo_search(
        rule=rule,
        floor=850,
        ceiling=1000,
        step=50,
        market_mean=None,
        sigma=50,
        bidder_mode="range",
        bidder_count=8,
        bidder_min=5,
        bidder_max=8,
        simulation_count=20,
    )
    assert result["best"]["bid"] in {850, 900, 950, 1000}
    assert result["interval"]["recommended"]["bid"] >= result["interval"]["low"]["bid"]
    assert len(result["points"]) == 4


def test_backtest_ranks_by_weighted_score_then_lower_amount() -> None:
    rule = normalize_rule(
        {
            "id": "rule1",
            "maxScore": 100,
            "benchmark": {"factor": 1, "trimMode": "none", "correction": {"enabled": False}},
            "score": {"type": "distance", "highPenaltyPerPct": 1, "lowPenaltyPerPct": 1, "minScore": 0},
        }
    )
    result = backtest(rule, "A公司 - 900\nB公司 - 1000\nC公司 - 1100")
    assert result["benchmark"] == 1000
    assert result["winner"]["name"] == "B公司"
    assert [row["rank"] for row in result["rows"]] == [1, 2, 3]
