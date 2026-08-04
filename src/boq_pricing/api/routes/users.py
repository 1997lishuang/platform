from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from boq_pricing.api.auth import CurrentUser, ROLE_PERMISSIONS, get_current_user, hash_password
from boq_pricing.api.dependencies import get_session_factory
from boq_pricing.infrastructure.db import session_scope
from boq_pricing.infrastructure.orm_models import SystemUserORM, UserRoleORM


router = APIRouter(prefix="/users", tags=["users"])
RoleName = Literal["admin", "estimator", "reviewer", "viewer"]


class UserSummary(BaseModel):
    username: str
    display_name: str | None = None
    role: str
    active: bool
    role_active: bool
    last_login_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class UserPage(BaseModel):
    items: list[UserSummary]
    total: int
    page: int
    page_size: int


class UserCreatePayload(BaseModel):
    username: str = Field(min_length=2, max_length=128)
    display_name: str | None = Field(default=None, max_length=128)
    password: str = Field(min_length=6, max_length=128)
    role: RoleName
    active: bool = True


class UserUpdatePayload(BaseModel):
    display_name: str | None = Field(default=None, max_length=128)
    role: RoleName
    active: bool = True


class PasswordResetPayload(BaseModel):
    password: str = Field(min_length=6, max_length=128)


@router.get("", response_model=UserPage)
def list_users(
    tenant_code: str = Query("default"),
    keyword: str = "",
    role: str = "",
    active: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
) -> UserPage:
    require_admin(user)
    with session_scope(get_session_factory()) as session:
        users = session.scalars(
            select(SystemUserORM)
            .where(SystemUserORM.tenant_code == tenant_code)
            .order_by(SystemUserORM.created_at.desc(), SystemUserORM.username.asc())
        ).all()
        roles = {
            row.username: row
            for row in session.scalars(select(UserRoleORM).where(UserRoleORM.tenant_code == tenant_code)).all()
        }

    normalized_keyword = keyword.strip().lower()
    rows = [to_summary(row, roles.get(row.username)) for row in users]
    if normalized_keyword:
        rows = [
            row
            for row in rows
            if normalized_keyword in row.username.lower()
            or normalized_keyword in (row.display_name or "").lower()
        ]
    if role:
        rows = [row for row in rows if row.role == role]
    if active == "active":
        rows = [row for row in rows if row.active and row.role_active]
    elif active == "inactive":
        rows = [row for row in rows if not row.active or not row.role_active]
    total = len(rows)
    start = (page - 1) * page_size
    return UserPage(items=rows[start : start + page_size], total=total, page=page, page_size=page_size)


@router.post("", response_model=UserSummary)
def create_user(
    payload: UserCreatePayload,
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> UserSummary:
    require_admin(user)
    username = normalize_username(payload.username)
    ensure_role(payload.role)
    with session_scope(get_session_factory()) as session:
        exists = session.scalar(
            select(SystemUserORM).where(
                SystemUserORM.tenant_code == tenant_code,
                SystemUserORM.username == username,
            )
        )
        if exists is not None:
            raise HTTPException(status_code=409, detail="用户名已存在。")
        user_row = SystemUserORM(
            tenant_code=tenant_code,
            username=username,
            display_name=payload.display_name,
            password_hash=hash_password(payload.password),
            active=payload.active,
        )
        role_row = UserRoleORM(
            tenant_code=tenant_code,
            username=username,
            display_name=payload.display_name,
            role=payload.role,
            active=payload.active,
        )
        session.add(user_row)
        session.add(role_row)
        session.flush()
        return to_summary(user_row, role_row)


@router.put("/{username}", response_model=UserSummary)
def update_user(
    username: str,
    payload: UserUpdatePayload,
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> UserSummary:
    require_admin(user)
    username = normalize_username(username)
    ensure_role(payload.role)
    if username == user.username and not payload.active:
        raise HTTPException(status_code=400, detail="不能停用当前登录账号。")
    with session_scope(get_session_factory()) as session:
        user_row, role_row = load_user_pair(session, tenant_code, username)
        user_row.display_name = payload.display_name
        user_row.active = payload.active
        role_row.display_name = payload.display_name
        role_row.role = payload.role
        role_row.active = payload.active
        session.flush()
        return to_summary(user_row, role_row)


@router.patch("/{username}/password", response_model=UserSummary)
def reset_user_password(
    username: str,
    payload: PasswordResetPayload,
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> UserSummary:
    require_admin(user)
    username = normalize_username(username)
    with session_scope(get_session_factory()) as session:
        user_row, role_row = load_user_pair(session, tenant_code, username)
        user_row.password_hash = hash_password(payload.password)
        session.flush()
        return to_summary(user_row, role_row)


@router.delete("/{username}", response_model=UserSummary)
def delete_user(
    username: str,
    tenant_code: str = Query("default"),
    user: CurrentUser = Depends(get_current_user),
) -> UserSummary:
    require_admin(user)
    username = normalize_username(username)
    if username == user.username:
        raise HTTPException(status_code=400, detail="不能删除当前登录账号。")
    with session_scope(get_session_factory()) as session:
        user_row, role_row = load_user_pair(session, tenant_code, username)
        user_row.active = False
        role_row.active = False
        session.flush()
        return to_summary(user_row, role_row)


def require_admin(user: CurrentUser) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="只有管理员可以管理用户。")


def ensure_role(role: str) -> None:
    if role not in ROLE_PERMISSIONS:
        raise HTTPException(status_code=400, detail="角色不存在。")


def normalize_username(username: str) -> str:
    normalized = username.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="用户名不能为空。")
    return normalized


def load_user_pair(session, tenant_code: str, username: str) -> tuple[SystemUserORM, UserRoleORM]:
    user_row = session.scalar(
        select(SystemUserORM).where(
            SystemUserORM.tenant_code == tenant_code,
            SystemUserORM.username == username,
        )
    )
    role_row = session.scalar(
        select(UserRoleORM).where(
            UserRoleORM.tenant_code == tenant_code,
            UserRoleORM.username == username,
        )
    )
    if user_row is None or role_row is None:
        raise HTTPException(status_code=404, detail="用户不存在。")
    return user_row, role_row


def serialize_time(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.isoformat(sep=" ")
    return value.astimezone(UTC).isoformat(sep=" ")


def to_summary(row: SystemUserORM, role: UserRoleORM | None) -> UserSummary:
    return UserSummary(
        username=row.username,
        display_name=row.display_name or role.display_name if role else row.display_name,
        role=(role.role if role else "viewer").lower(),
        active=bool(row.active),
        role_active=bool(role.active) if role else False,
        last_login_at=serialize_time(row.last_login_at),
        created_at=serialize_time(row.created_at),
        updated_at=serialize_time(row.updated_at),
    )
