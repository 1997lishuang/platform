from __future__ import annotations

from boq_pricing.config import Settings, load_settings
from boq_pricing.infrastructure import DatabaseConfig, MySqlCliClient, create_session_factory
from sqlalchemy.orm import Session, sessionmaker


def get_settings() -> Settings:
    return load_settings()


def get_mysql_client(settings: Settings | None = None) -> MySqlCliClient:
    settings = settings or get_settings()
    return MySqlCliClient(
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_database,
        host=settings.mysql_host,
        port=settings.mysql_port,
        mysql_bin=settings.mysql_bin,
    )


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    settings = settings or get_settings()
    return create_session_factory(DatabaseConfig.from_settings(settings))
