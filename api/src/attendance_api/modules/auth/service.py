from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from attendance_api.config import get_settings
from attendance_api.errors import ApiError
from attendance_api.models import LoginSession, User
from attendance_api.models.base import utc_now
from attendance_api.security.passwords import hash_password, verify_password
from attendance_api.security.tokens import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
)

_DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-timing")


@dataclass(frozen=True)
class AuthResult:
    user: User
    access_token: str
    refresh_token: str


def _result(user: User, login_session: LoginSession, refresh_token: str) -> AuthResult:
    return AuthResult(
        user=user,
        access_token=create_access_token(
            user_id=user.id,
            session_id=login_session.id,
            role=user.role,
            must_change_password=user.must_change_password,
        ),
        refresh_token=refresh_token,
    )


def login(
    db: Session, *, username: str, password: str, ip_address: str, user_agent: str
) -> AuthResult:
    user = db.scalar(select(User).where(User.username == username.strip().lower()))
    password_matches = verify_password(
        user.password_hash if user is not None else _DUMMY_PASSWORD_HASH, password
    )
    if user is None or not password_matches or user.status != "ACTIVE":
        if user is not None:
            user.failed_login_count += 1
            user.last_failed_login_at = utc_now()
            db.commit()
        raise ApiError(401, "INVALID_CREDENTIALS", "用户名或密码错误")

    now = utc_now()
    refresh_token = generate_refresh_token()
    login_session = LoginSession(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(refresh_token),
        expires_at=now + timedelta(seconds=get_settings().refresh_token_ttl_seconds),
        last_used_at=now,
        ip_address=ip_address[:45],
        user_agent=user_agent[:255],
    )
    user.failed_login_count = 0
    user.last_login_at = now
    db.add(login_session)
    db.flush()
    result = _result(user, login_session, refresh_token)
    db.commit()
    return result


def refresh(db: Session, *, refresh_token: str, origin: str | None) -> AuthResult:
    if origin != get_settings().frontend_origin:
        raise ApiError(403, "INVALID_ORIGIN", "请求来源无效")

    login_session = db.scalar(
        select(LoginSession)
        .where(LoginSession.refresh_token_hash == hash_refresh_token(refresh_token))
        .with_for_update()
    )
    now = utc_now()
    if (
        login_session is None
        or login_session.revoked_at is not None
        or login_session.expires_at <= now
    ):
        raise ApiError(401, "AUTHENTICATION_REQUIRED", "请先登录")

    user = db.get(User, login_session.user_id)
    if user is None:
        raise ApiError(401, "AUTHENTICATION_REQUIRED", "请先登录")
    if user.status != "ACTIVE":
        login_session.revoked_at = now
        db.commit()
        raise ApiError(403, "ACCOUNT_DISABLED", "账号已禁用")

    new_refresh_token = generate_refresh_token()
    login_session.refresh_token_hash = hash_refresh_token(new_refresh_token)
    login_session.last_used_at = now
    result = _result(user, login_session, new_refresh_token)
    db.commit()
    return result


def change_password(
    db: Session,
    *,
    user: User,
    session_id: str,
    current_password: str,
    new_password: str,
) -> AuthResult:
    if not verify_password(user.password_hash, current_password):
        raise ApiError(400, "CURRENT_PASSWORD_INVALID", "当前密码不正确")
    if verify_password(user.password_hash, new_password):
        raise ApiError(400, "PASSWORD_POLICY_VIOLATION", "新密码不能与当前密码相同")

    login_session = db.scalar(
        select(LoginSession)
        .where(LoginSession.id == session_id, LoginSession.user_id == user.id)
        .with_for_update()
    )
    if login_session is None or login_session.revoked_at is not None:
        raise ApiError(401, "AUTHENTICATION_REQUIRED", "请先登录")

    now = utc_now()
    db.execute(
        update(LoginSession)
        .where(
            LoginSession.user_id == user.id,
            LoginSession.id != session_id,
            LoginSession.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    new_refresh_token = generate_refresh_token()
    login_session.refresh_token_hash = hash_refresh_token(new_refresh_token)
    login_session.last_used_at = now
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    result = _result(user, login_session, new_refresh_token)
    db.commit()
    return result


def logout(db: Session, *, refresh_token: str | None, session_id: str | None) -> None:
    login_session: LoginSession | None = None
    if refresh_token:
        login_session = db.scalar(
            select(LoginSession).where(
                LoginSession.refresh_token_hash == hash_refresh_token(refresh_token)
            )
        )
    if login_session is None and session_id:
        login_session = db.get(LoginSession, session_id)
    if login_session is not None and login_session.revoked_at is None:
        login_session.revoked_at = utc_now()
        db.commit()
