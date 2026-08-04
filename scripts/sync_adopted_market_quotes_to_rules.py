from __future__ import annotations

from boq_pricing.api.dependencies import get_session_factory
from boq_pricing.infrastructure.market_quotes import MarketQuoteRepository


def main() -> None:
    count = MarketQuoteRepository(get_session_factory()).publish_adopted_quotes_as_rules()
    print(f"synced {count} adopted market quote(s) to active price rules")


if __name__ == "__main__":
    main()
