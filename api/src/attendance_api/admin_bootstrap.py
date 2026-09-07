import logging
from typing import Literal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from attendance_api.config import Settings, get_settings
from attendance_api.db import SessionFactory
from attendance_api.models import LoginSession, User
from attendance_api.models.base import utc_now
from attendance_api.security.passwords import (
    hash_password,
    password_meets_policy,
    verify_password,
)

AdminBootstrapResult = Literal["disabled", "created", "updated", "unchanged"]
logger = logging.getLogger(__name__)


class AdminBootstrapError(RuntimeError):
    pass


def sync_configured_admin(db: Session, settings: Settings) -> AdminBootstrapResult:
    if settings.admin_password is None:
        return "disabled"
    password = settings.admin_password.get_secret_value()
    if not password:
        return "disabled"

    username = settings.admin_username.strip().lower()
    display_name = settings.admin_display_name.strip()
    if not username:
        raise AdminBootstrapError("ADMIN_USERNAME 不能为空")
    if not display_name:
        raise AdminBootstrapError("ADMIN_DISPLAY_NAME 不能为空")
    if not password_meets_policy(password):
        raise AdminBootstrapError("ADMIN_PASSWORD 长度必须为 12 至 128 个字符")

    user = db.scalar(select(User).where(User.username == username).with_for_update())
    if user is None:
        db.add(
            User(
                username=username,
                password_hash=hash_password(password),
                display_name=display_name,
                role="ADMIN",
                status="ACTIVE",
                must_change_password=False,
            )
        )
        db.commit()
        return "created"

    if user.role != "ADMIN":
        raise AdminBootstrapError(f"ADMIN_USERNAME={username} 已由 {user.role} 账号占用")

    changed = False
    if user.display_name != display_name:
        user.display_name = display_name
        changed = True
    if user.status != "ACTIVE":
        user.status = "ACTIVE"
        changed = True
    if user.must_change_password:
        user.must_change_password = False
        changed = True
    if not verify_password(user.password_hash, password):
        user.password_hash = hash_password(password)
        db.execute(
            update(LoginSession)
            .where(LoginSession.user_id == user.id, LoginSession.revoked_at.is_(None))
            .values(revoked_at=utc_now())
        )
        changed = True

    db.commit()
    return "updated" if changed else "unchanged"


def bootstrap_configured_admin() -> None:
    settings = get_settings()
    with SessionFactory() as db:
        result = sync_configured_admin(db, settings)
    logger.info(
        "Configured administrator synchronization: username=%s result=%s",
        settings.admin_username.strip().lower(),
        result,
    )
