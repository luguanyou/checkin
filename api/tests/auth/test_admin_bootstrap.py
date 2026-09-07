from datetime import timedelta

import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from attendance_api.admin_bootstrap import AdminBootstrapError, sync_configured_admin
from attendance_api.config import Settings
from attendance_api.models import LoginSession, User
from attendance_api.models.base import utc_now
from attendance_api.security.passwords import verify_password

ADMIN_PASSWORD = "configured-admin-password"


def settings(
    password: str | None = ADMIN_PASSWORD,
    *,
    username: str = " RootAdmin ",
    display_name: str = " 超级管理员 ",
) -> Settings:
    return Settings(
        _env_file=None,
        admin_username=username,
        admin_display_name=display_name,
        admin_password=SecretStr(password) if password is not None else None,
    )


def test_admin_bootstrap_is_disabled_without_password(db_session: Session) -> None:
    result = sync_configured_admin(db_session, settings(None))

    assert result == "disabled"
    assert db_session.scalar(select(User)) is None


def test_admin_bootstrap_creates_active_admin_with_hash(db_session: Session) -> None:
    result = sync_configured_admin(db_session, settings())

    admin = db_session.scalar(select(User).where(User.username == "rootadmin"))
    assert result == "created"
    assert admin is not None
    assert admin.display_name == "超级管理员"
    assert admin.role == "ADMIN"
    assert admin.status == "ACTIVE"
    assert admin.must_change_password is False
    assert admin.password_hash != ADMIN_PASSWORD
    assert verify_password(admin.password_hash, ADMIN_PASSWORD)


def test_admin_bootstrap_is_idempotent_when_configuration_matches(
    db_session: Session,
) -> None:
    sync_configured_admin(db_session, settings())
    admin = db_session.scalar(select(User).where(User.username == "rootadmin"))
    assert admin is not None
    original_hash = admin.password_hash

    result = sync_configured_admin(db_session, settings())

    db_session.refresh(admin)
    assert result == "unchanged"
    assert admin.password_hash == original_hash


def test_admin_bootstrap_updates_password_and_revokes_sessions(
    db_session: Session,
) -> None:
    sync_configured_admin(db_session, settings("old-admin-password"))
    admin = db_session.scalar(select(User).where(User.username == "rootadmin"))
    assert admin is not None
    login_session = LoginSession(
        user_id=admin.id,
        refresh_token_hash="a" * 64,
        expires_at=utc_now() + timedelta(days=1),
        last_used_at=utc_now(),
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    db_session.add(login_session)
    db_session.commit()

    result = sync_configured_admin(
        db_session,
        settings("new-admin-password", display_name=" 新管理员 "),
    )

    db_session.refresh(admin)
    db_session.refresh(login_session)
    assert result == "updated"
    assert admin.display_name == "新管理员"
    assert verify_password(admin.password_hash, "new-admin-password")
    assert login_session.revoked_at is not None


def test_admin_bootstrap_reenables_configured_admin(db_session: Session) -> None:
    sync_configured_admin(db_session, settings())
    admin = db_session.scalar(select(User).where(User.username == "rootadmin"))
    assert admin is not None
    admin.status = "DISABLED"
    admin.must_change_password = True
    db_session.commit()

    result = sync_configured_admin(db_session, settings())

    db_session.refresh(admin)
    assert result == "updated"
    assert admin.status == "ACTIVE"
    assert admin.must_change_password is False


def test_admin_bootstrap_rejects_teacher_username_conflict(db_session: Session) -> None:
    teacher = User(
        username="rootadmin",
        password_hash="$argon2id$occupied",
        display_name="任课教师",
        role="TEACHER",
        status="ACTIVE",
        must_change_password=False,
    )
    db_session.add(teacher)
    db_session.commit()

    with pytest.raises(AdminBootstrapError, match="TEACHER"):
        sync_configured_admin(db_session, settings())

    db_session.refresh(teacher)
    assert teacher.role == "TEACHER"
    assert teacher.display_name == "任课教师"


@pytest.mark.parametrize(
    ("username", "display_name", "password", "message"),
    [
        ("   ", "超级管理员", ADMIN_PASSWORD, "ADMIN_USERNAME"),
        ("admin", "   ", ADMIN_PASSWORD, "ADMIN_DISPLAY_NAME"),
        ("admin", "超级管理员", "short", "ADMIN_PASSWORD"),
        ("admin", "超级管理员", "x" * 129, "ADMIN_PASSWORD"),
    ],
)
def test_admin_bootstrap_rejects_invalid_configuration(
    db_session: Session,
    username: str,
    display_name: str,
    password: str,
    message: str,
) -> None:
    with pytest.raises(AdminBootstrapError, match=message):
        sync_configured_admin(
            db_session,
            settings(password, username=username, display_name=display_name),
        )

    assert db_session.scalar(select(User)) is None
