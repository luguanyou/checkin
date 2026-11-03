from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from attendance_api.models.base import (
    MYSQL_TABLE_OPTIONS,
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class StudentRegistration(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "student_registrations"
    __table_args__ = (
        CheckConstraint("status IN ('PENDING','APPROVED','REJECTED')", name="status"),
        MYSQL_TABLE_OPTIONS,
    )
    student_id: Mapped[str] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"), unique=True
    )
    class_group_id: Mapped[str] = mapped_column(
        ForeignKey("class_groups.id", ondelete="CASCADE"), index=True
    )
    password_hash: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), server_default="PENDING")
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    review_reason: Mapped[str | None] = mapped_column(String(500))


class RegistrationReviewer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "registration_reviewers"
    __table_args__ = (
        UniqueConstraint("class_group_id", "user_id", name="uq_registration_reviewers_class_user"),
        MYSQL_TABLE_OPTIONS,
    )
    class_group_id: Mapped[str] = mapped_column(ForeignKey("class_groups.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    granted_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
