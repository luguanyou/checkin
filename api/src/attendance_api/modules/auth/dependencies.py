from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from attendance_api.db import get_db
from attendance_api.errors import ApiError
from attendance_api.models import LoginSession, User
from attendance_api.models.base import utc_now
from attendance_api.security.tokens import InvalidAccessTokenError, decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def authentication_required() -> ApiError:
    return ApiError(401, "AUTHENTICATION_REQUIRED", "请先登录")


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise authentication_required()
    try:
        claims = decode_access_token(credentials.credentials)
    except InvalidAccessTokenError:
        raise authentication_required() from None

    login_session = db.scalar(
        select(LoginSession).where(
            LoginSession.id == claims["sid"], LoginSession.user_id == claims["sub"]
        )
    )
    now = utc_now()
    if (
        login_session is None
        or login_session.revoked_at is not None
        or login_session.expires_at <= now
    ):
        raise authentication_required()

    user = db.get(User, claims["sub"])
    if user is None:
        raise authentication_required()
    if user.status != "ACTIVE":
        raise ApiError(403, "ACCOUNT_DISABLED", "账号已禁用")

    request.state.auth_session_id = login_session.id
    return user


def require_teacher(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "TEACHER":
        raise ApiError(403, "RESOURCE_FORBIDDEN", "无权访问该资源")
    return user


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "ADMIN":
        raise ApiError(403, "RESOURCE_FORBIDDEN", "无权访问该资源")
    return user


def require_password_changed(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.must_change_password:
        raise ApiError(403, "PASSWORD_CHANGE_REQUIRED", "请先修改初始密码")
    return user
