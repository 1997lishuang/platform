from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from boq_pricing.api.auth import (
    CurrentUser,
    authenticate_user,
    create_access_token,
    get_current_user,
    load_active_user,
)
from boq_pricing.api.dependencies import get_session_factory, get_settings
from boq_pricing.api.schemas import CurrentUserResponse, LoginRequest, LoginResponse


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
) -> LoginResponse:
    settings = get_settings()
    session_factory = get_session_factory(settings)
    user = authenticate_user(
        session_factory,
        tenant_code=payload.tenant_code or settings.default_tenant_code,
        username=payload.username,
        password=payload.password,
    )
    if user is None:
        raise HTTPException(status_code=401, detail="用户名、密码或角色无效。")
    return LoginResponse(
        access_token=create_access_token(user, settings),
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        tenant_code=user.tenant_code,
    )


@router.get("/me", response_model=CurrentUserResponse)
def me(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUserResponse:
    session_factory = get_session_factory()
    user = load_active_user(session_factory, current_user.tenant_code, current_user.username)
    if user is None:
        raise HTTPException(status_code=401, detail="登录用户不存在或已停用。")
    return CurrentUserResponse(
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        tenant_code=user.tenant_code,
    )
