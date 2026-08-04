from __future__ import annotations

from decimal import Decimal

from boq_pricing.bid_strategy.generation import dynamic_game_simulation, reverse_price_items
from boq_pricing.bid_strategy.rule_parser import normalize_rule


def test_reverse_price_respects_locked_item_and_rebalances_adjustable_items() -> None:
    items = [
        {"itemKey": "A:1", "itemName": "固定项", "quantity": "10", "unitPrice": "100", "totalPrice": "1000"},
        {"itemKey": "A:2", "itemName": "可调项1", "quantity": "10", "unitPrice": "200", "totalPrice": "2000"},
        {"itemKey": "A:3", "itemName": "可调项2", "quantity": "10", "unitPrice": "300", "totalPrice": "3000"},
    ]
    result = reverse_price_items(
        items,
        target_total=Decimal("7200"),
        locked_items={"A:1": {"locked": True, "targetTotal": "1000"}, "A:3": {"weight": "2"}},
    )

    assert result["summary"]["finalTotal"] == Decimal("7200.00")
    assert result["summary"]["difference"] == Decimal("0.00")
    fixed = next(item for item in result["items"] if item["itemKey"] == "A:1")
    assert fixed["targetTotal"] == "1000.00"
    weighted = next(item for item in result["items"] if item["itemKey"] == "A:3")
    plain = next(item for item in result["items"] if item["itemKey"] == "A:2")
    assert Decimal(weighted["profit"]) > Decimal(plain["profit"])


def test_reverse_price_allows_manual_item_below_cost() -> None:
    items = [
        {"itemKey": "A:1", "itemName": "可低价项", "quantity": "10", "unitPrice": "100", "totalPrice": "1000"},
        {"itemKey": "A:2", "itemName": "可调项", "quantity": "10", "unitPrice": "200", "totalPrice": "2000"},
    ]
    result = reverse_price_items(
        items,
        target_total=Decimal("2600"),
        locked_items={"A:1": {"locked": True, "targetTotal": "800"}},
    )

    below_cost = next(item for item in result["items"] if item["itemKey"] == "A:1")
    assert below_cost["targetTotal"] == "800.00"
    assert "目标合价低于成本" in below_cost["issues"]
    assert result["summary"]["finalTotal"] == Decimal("2600.00")


def test_dynamic_game_returns_candidates_and_best_bid() -> None:
    rule = normalize_rule(
        {
            "id": "rule1",
            "maxScore": 100,
            "benchmark": {"factor": 1, "trimMode": "none", "correction": {"enabled": False}},
            "score": {"type": "distance", "highPenaltyPerPct": 1, "lowPenaltyPerPct": 1, "minScore": 0},
        }
    )
    result = dynamic_game_simulation(
        rule=rule,
        floor=Decimal("800"),
        ceiling=Decimal("1000"),
        step=Decimal("100"),
        profiles=[],
        bidder_min=4,
        bidder_max=6,
        rounds=10,
    )

    assert len(result["points"]) == 3
    assert result["best"]["bid"] in {Decimal("800.00"), Decimal("900.00"), Decimal("1000.00")}
    assert result["summary"]["candidateCount"] == 3
