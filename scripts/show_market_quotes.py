from __future__ import annotations

from sqlalchemy import text

from boq_pricing.config import load_settings
from boq_pricing.infrastructure.db import DatabaseConfig, create_session_factory


def main() -> None:
    session_factory = create_session_factory(DatabaseConfig.from_settings(load_settings()))
    with session_factory() as session:
        rows = session.execute(
            text(
                """
                SELECT quote_code, item_name, status, recommended_price, created_at,
                       JSON_LENGTH(source_urls_json) AS source_count
                FROM market_price_quote
                ORDER BY id DESC
                LIMIT 20
                """
            )
        ).mappings()
        for row in rows:
            print(dict(row))


if __name__ == "__main__":
    main()
