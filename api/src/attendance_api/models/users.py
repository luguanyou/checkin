from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.dialects.mysql import DATETIME, INTEGER
from sqlalchemy.orm import Mapped, mapped_column

from attendance_api.models.base import (
    MYSQL_TABLE_OPTIONS,
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('ADMIN', 'TEACHER')", name="role"),
        CheckConstraint("status IN ('ACTIVE', 'DISABLED')", name="status"),
        CheckConstraint("failed_login_count >= 0", name="failed_login_count_nonnegative"),
        Index("ix_users_role_status", "role", "status"),
        MYSQL_TABLE_OPTIONS,
    )

    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), server_default="ACTIVE")
    must_change_password: Mapped[bool] = mapped_column(Boolean, server_default=text("1"))
    failed_login_count: Mapped[int] = mapped_column(INTEGER(unsigned=True), server_default="0")
    last_failed_login_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    last_login_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))


class LoginSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "login_sessions"
    __table_args__ = (
        Index("ix_login_sessions_user_active", "user_id", "revoked_at", "expires_at"),
        MYSQL_TABLE_OPTIONS,
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6))
    revoked_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    last_used_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6))
    ip_address: Mapped[str] = mapped_column(String(45))
    user_agent: Mapped[str] = mapped_column(String(255))
