from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from boq_pricing.api.auth import authenticate_user, create_access_token, hash_password, load_active_user, verify_access_token
from boq_pricing.config import Settings
from boq_pricing.infrastructure.db import Base
from boq_pricing.infrastructure.orm_models import SystemUserORM, UserRoleORM


def test_authenticate_user_requires_system_user_and_active_role():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    with session_factory() as session:
        session.add(
            SystemUserORM(
                tenant_code="default",
                username="admin",
                display_name="系统管理员",
                password_hash=hash_password("secret"),
                active=True,
            )
        )
        session.add(
            UserRoleORM(
                tenant_code="default",
                username="admin",
                display_name="系统管理员",
                role="admin",
                active=True,
            )
        )
        session.commit()

    user = authenticate_user(session_factory, "default", "admin", "secret")
    assert user is not None
    assert user.role == "admin"
    assert authenticate_user(session_factory, "default", "admin", "bad") is None
    assert authenticate_user(session_factory, "default", "missing", "secret") is None


def test_access_token_roundtrip_and_user_lookup():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    with session_factory() as session:
        session.add(
            SystemUserORM(
                tenant_code="default",
                username="reviewer",
                password_hash=hash_password("secret"),
                active=True,
            )
        )
        session.add(UserRoleORM(tenant_code="default", username="reviewer", role="reviewer", active=True))
        session.commit()

    settings = Settings(auth_secret="unit-test-secret")
    user = load_active_user(session_factory, "default", "reviewer")
    assert user is not None
    token = create_access_token(user, settings)
    payload = verify_access_token(token, settings)
    assert payload["username"] == "reviewer"
    assert payload["tenant_code"] == "default"
