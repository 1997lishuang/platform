from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from boq_pricing.config import Settings


class Base(DeclarativeBase):
    pass


@dataclass(frozen=True)
class DatabaseConfig:
    user: str
    password: str
    host: str = "127.0.0.1"
    port: int = 3306
    database: str = "boq_pricing"

    @classmethod
    def from_settings(cls, settings: Settings) -> "DatabaseConfig":
        return cls(
            user=settings.mysql_user,
            password=settings.mysql_password,
            host=settings.mysql_host,
            port=settings.mysql_port,
            database=settings.mysql_database,
        )

    def sqlalchemy_url(self) -> str:
        password = quote_plus(self.password)
        return (
            f"mysql+mysqlconnector://{self.user}:{password}"
            f"@{self.host}:{self.port}/{self.database}?charset=utf8mb4"
        )


def create_session_factory(config: DatabaseConfig) -> sessionmaker[Session]:
    engine = create_engine(
        config.sqlalchemy_url(),
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=5,
        max_overflow=10,
        future=True,
    )
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

