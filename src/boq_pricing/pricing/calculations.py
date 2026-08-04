from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


MONEY_QUANT = Decimal("0.01")


def calculate_total_price(quantity: Decimal | None, unit_price: Decimal | None) -> Decimal | None:
    if quantity is None or unit_price is None:
        return None
    return (quantity * unit_price).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
