from __future__ import annotations

from sqlalchemy import text

from boq_pricing.config import load_settings
from boq_pricing.infrastructure.db import DatabaseConfig, create_session_factory


def main() -> None:
    session_factory = create_session_factory(DatabaseConfig.from_settings(load_settings()))
    with session_factory() as session:
        session.execute(
            text(
                """
                UPDATE platform_config
                SET endpoint_type = 'responses',
                    enable_web_search = 1,
                    search_tool_type = 'web_search'
                WHERE provider = 'doubao'
                """
            )
        )
        session.commit()
        rows = session.execute(
            text(
                """
                SELECT provider, endpoint_type, enable_web_search, search_tool_type, base_url, model
                FROM platform_config
                ORDER BY provider
                """
            )
        ).mappings()
        for row in rows:
            print(dict(row))


if __name__ == "__main__":
    main()
