from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from boq_pricing.api.dependencies import get_session_factory, get_settings
from boq_pricing.config import Settings
from boq_pricing.infrastructure.db import session_scope
from boq_pricing.infrastructure.orm_models import SystemUserORM, UserRoleORM


ROLE_PERMISSIONS = {
    "admin": {"rule:create", "rule:submit", "rule:approve", "rule:reject", "rule:view"},
    "estimator": {"rule:create", "rule:submit", "rule:view"},
    "reviewer": {"rule:approve", "rule:reject", "rule:view"},
    "viewer": {"rule:view"},
}


@dataclass(frozen=True)
class CurrentUser:
    username: str
    role: str
    tenant_code: str

    def can(self, permission: str) -> bool:
        return permission in ROLE_PERMISSIONS.get(self.role, set())


def get_current_user(
    authorization: str | None = Header(None),
) -> CurrentUser:
    settings = get_settings()
    session_factory = get_session_factory(settings)
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="请先登录。")
    token_payload = verify_access_token(authorization.removeprefix("Bearer ").strip(), settings)
    username = str(token_payload.get("username") or "")
    tenant_code = str(token_payload.get("tenant_code") or settings.default_tenant_code)
    user = load_active_user(session_factory, tenant_code, username)
    if user is None:
        raise HTTPException(status_code=401, detail="登录用户不存在或已停用。")
    role = user.role.lower()
    if role not in ROLE_PERMISSIONS:
        raise HTTPException(status_code=403, detail="Unknown user role.")
    return CurrentUser(username=user.username, role=role, tenant_code=user.tenant_code)


def require_permission(user: CurrentUser, permission: str) -> None:
    if not user.can(permission):
        raise HTTPException(status_code=403, detail=f"Permission denied: {permission}")


@dataclass(frozen=True)
class AuthenticatedUser:
    tenant_code: str
    username: str
    display_name: str | None
    role: str


def authenticate_user(
    session_factory: sessionmaker[Session],
    tenant_code: str,
    username: str,
    password: str,
) -> AuthenticatedUser | None:
    with session_scope(session_factory) as session:
        row = session.scalar(
            select(SystemUserORM).where(
                SystemUserORM.tenant_code == tenant_code,
                SystemUserORM.username == username,
                SystemUserORM.active.is_(True),
            )
        )
        if row is None or not verify_password(password, row.password_hash):
            return None
        role = session.scalar(
            select(UserRoleORM).where(
                UserRoleORM.tenant_code == tenant_code,
                UserRoleORM.username == username,
                UserRoleORM.active.is_(True),
            )
        )
        if role is None or role.role.lower() not in ROLE_PERMISSIONS:
            return None
        row.last_login_at = datetime.now(UTC)
        return AuthenticatedUser(
            tenant_code=tenant_code,
            username=row.username,
            display_name=row.display_name or role.display_name,
            role=role.role.lower(),
        )


def load_active_user(
    session_factory: sessionmaker[Session],
    tenant_code: str,
    username: str,
) -> AuthenticatedUser | None:
    with session_scope(session_factory) as session:
        row = session.scalar(
            select(SystemUserORM).where(
                SystemUserORM.tenant_code == tenant_code,
                SystemUserORM.username == username,
                SystemUserORM.active.is_(True),
            )
        )
        role = session.scalar(
            select(UserRoleORM).where(
                UserRoleORM.tenant_code == tenant_code,
                UserRoleORM.username == username,
                UserRoleORM.active.is_(True),
            )
        )
        if row is None or role is None:
            return None
        return AuthenticatedUser(
            tenant_code=tenant_code,
            username=row.username,
            display_name=row.display_name or role.display_name,
            role=role.role.lower(),
        )


def hash_password(password: str, salt: str | None = None, iterations: int = 200_000) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt, digest = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        expected = hash_password(password, salt=salt, iterations=int(iterations)).split("$", 3)[3]
        return hmac.compare_digest(expected, digest)
    except Exception:
        return False


def create_access_token(user: AuthenticatedUser, settings: Settings) -> str:
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.auth_token_minutes)
    payload = {
        "tenant_code": user.tenant_code,
        "username": user.username,
        "exp": int(expires_at.timestamp()),
    }
    payload_part = base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = sign_token_payload(payload_part, settings.auth_secret)
    return f"{payload_part}.{signature}"


def verify_access_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        payload_part, signature = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="登录凭证格式无效。") from exc
    expected = sign_token_payload(payload_part, settings.auth_secret)
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="登录凭证签名无效。")
    try:
        payload = json.loads(base64url_decode(payload_part))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="登录凭证内容无效。") from exc
    if int(payload.get("exp") or 0) < int(datetime.now(UTC).timestamp()):
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录。")
    return payload


def sign_token_payload(payload_part: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload_part.encode("utf-8"), hashlib.sha256).digest()
    return base64url_encode(digest)


def base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def base64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
