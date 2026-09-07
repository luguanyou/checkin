from datetime import date, datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME, INTEGER
from sqlalchemy.orm import Mapped, mapped_column

from attendance_api.models.base import (
    MYSQL_TABLE_OPTIONS,
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class AttendanceSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attendance_sessions"
    __table_args__ = (
        CheckConstraint("status IN ('DRAFT', 'COMPLETED')", name="status"),
        CheckConstraint(
            "(status = 'DRAFT' AND completed_at IS NULL) OR "
            "(status = 'COMPLETED' AND completed_at IS NOT NULL)",
            name="completion_state",
        ),
        Index("ix_attendance_sessions_creator_date", "created_by", "session_date"),
        Index(
            "ix_attendance_sessions_class_status_date",
            "class_group_id",
            "status",
            "session_date",
        ),
        MYSQL_TABLE_OPTIONS,
    )

    class_group_id: Mapped[str] = mapped_column(
        ForeignKey("class_groups.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    session_date: Mapped[date]
    status: Mapped[str] = mapped_column(String(20), server_default="DRAFT")
    started_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6))
    completed_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    created_by: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )


class AttendanceRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("session_id", "student_id", name="uq_attendance_records_session_student"),
        CheckConstraint(
            "status IN ('pending', 'present', 'absent', 'leave', 'late')", name="status"
        ),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint(
            "(status = 'pending' AND marked_at IS NULL) OR "
            "(status <> 'pending' AND marked_at IS NOT NULL)",
            name="marked_state",
        ),
        Index("ix_attendance_records_session_status", "session_id", "status"),
        Index("ix_attendance_records_student", "student_id"),
        MYSQL_TABLE_OPTIONS,
    )

    session_id: Mapped[str] = mapped_column(
        ForeignKey("attendance_sessions.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    student_id: Mapped[str] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    student_number_snapshot: Mapped[str] = mapped_column(String(50))
    student_name_snapshot: Mapped[str] = mapped_column(String(100))
    class_name_snapshot: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), server_default="pending")
    marked_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    last_modified_by: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    last_modified_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    version: Mapped[int] = mapped_column(INTEGER(unsigned=True), server_default="1")
