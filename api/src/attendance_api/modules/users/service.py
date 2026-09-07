from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from attendance_api.errors import ApiError
from attendance_api.models import LoginSession, User
from attendance_api.models.base import utc_now
from attendance_api.modules.audit.service import append_audit
from attendance_api.security.passwords import (
    hash_password,
    password_meets_policy,
    verify_password,
)


def list_users(
    db: Session,
    *,
    page: int,
    page_size: int,
    role: str | None,
    status: str | None,
    query: str | None,
) -> tuple[list[User], int]:
    filters = []
    if role:
        filters.append(User.role == role)
    if status:
        filters.append(User.status == status)
    normalized_query = query.strip() if query else ""
    if normalized_query:
        pattern = f"%{normalized_query}%"
        filters.append(or_(User.username.like(pattern), User.display_name.like(pattern)))

    total = db.scalar(select(func.count()).select_from(User).where(*filters)) or 0
    users = list(
        db.scalars(
            select(User)
            .where(*filters)
            .order_by(User.created_at.desc(), User.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return users, total


def create_teacher(
    db: Session,
    *,
    actor: User,
    username: str,
    display_name: str,
    temporary_password: str,
    ip_address: str,
    request_id: str,
) -> User:
    if not password_meets_policy(temporary_password):
        raise ApiError(400, "PASSWORD_POLICY_VIOLATION", "密码长度必须为 12 至 128 个字符")
    normalized_username = username.strip().lower()
    if db.scalar(select(User.id).where(User.username == normalized_username)) is not None:
        raise ApiError(409, "DUPLICATE_RESOURCE", "用户名已存在")

    user = User(
        username=normalized_username,
        password_hash=hash_password(temporary_password),
        display_name=display_name.strip(),
        role="TEACHER",
        status="ACTIVE",
        must_change_password=True,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "DUPLICATE_RESOURCE", "用户名已存在") from None
    append_audit(
        db,
        actor_user_id=actor.id,
        action="USER_CREATED",
        entity_type="user",
        entity_id=user.id,
        before_value=None,
        after_value={
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
            "status": user.status,
            "must_change_password": user.must_change_password,
        },
        reason=None,
        ip_address=ip_address,
        request_id=request_id,
    )
    db.commit()
    return user


def update_user_status(
    db: Session,
    *,
    actor: User,
    user_id: str,
    status: str,
    ip_address: str,
    request_id: str,
) -> User:
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "用户不存在")
    if user.id == actor.id and status == "DISABLED":
        raise ApiError(403, "SELF_ADMIN_ACTION_FORBIDDEN", "管理员不能禁用自己")

    previous_status = user.status
    user.status = status
    if status == "DISABLED":
        db.execute(
            update(LoginSession)
            .where(LoginSession.user_id == user.id, LoginSession.revoked_at.is_(None))
            .values(revoked_at=utc_now())
        )
    append_audit(
        db,
        actor_user_id=actor.id,
        action="USER_STATUS_CHANGED",
        entity_type="user",
        entity_id=user.id,
        before_value={"status": previous_status},
        after_value={"status": status},
        reason=None,
        ip_address=ip_address,
        request_id=request_id,
    )
    db.commit()
    return user


def reset_user_password(
    db: Session,
    *,
    actor: User,
    user_id: str,
    temporary_password: str,
    ip_address: str,
    request_id: str,
) -> None:
    if not password_meets_policy(temporary_password):
        raise ApiError(400, "PASSWORD_POLICY_VIOLATION", "密码长度必须为 12 至 128 个字符")
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "用户不存在")
    if verify_password(user.password_hash, temporary_password):
        raise ApiError(400, "PASSWORD_POLICY_VIOLATION", "新密码不能与当前密码相同")

    user.password_hash = hash_password(temporary_password)
    user.must_change_password = True
    db.execute(
        update(LoginSession)
        .where(LoginSession.user_id == user.id, LoginSession.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )
    append_audit(
        db,
        actor_user_id=actor.id,
        action="USER_PASSWORD_RESET",
        entity_type="user",
        entity_id=user.id,
        before_value=None,
        after_value={"must_change_password": True},
        reason=None,
        ip_address=ip_address,
        request_id=request_id,
    )
    db.commit()
