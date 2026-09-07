from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from attendance_api.models.base import (
    MYSQL_TABLE_OPTIONS,
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class Course(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("owner_teacher_id", "code", "term", name="uq_courses_owner_code_term"),
        CheckConstraint("status IN ('ACTIVE', 'ARCHIVED')", name="status"),
        Index("ix_courses_owner_status", "owner_teacher_id", "status"),
        MYSQL_TABLE_OPTIONS,
    )

    owner_teacher_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str] = mapped_column(String(50))
    term: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), server_default="ACTIVE")


class ClassGroup(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "class_groups"
    __table_args__ = (
        UniqueConstraint("course_id", "name", name="uq_class_groups_course_name"),
        CheckConstraint("status IN ('ACTIVE', 'ARCHIVED')", name="status"),
        Index("ix_class_groups_course_status", "course_id", "status"),
        MYSQL_TABLE_OPTIONS,
    )

    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), server_default="ACTIVE")


class Student(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "students"
    __table_args__ = (Index("ix_students_name", "name"), MYSQL_TABLE_OPTIONS)

    student_number: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    gender: Mapped[str | None] = mapped_column(String(20))
    major: Mapped[str | None] = mapped_column(String(120))


class Enrollment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("class_group_id", "student_id", name="uq_enrollments_class_student"),
        CheckConstraint("status IN ('ACTIVE', 'REMOVED')", name="status"),
        Index("ix_enrollments_class_status", "class_group_id", "status"),
        Index("ix_enrollments_student", "student_id"),
        MYSQL_TABLE_OPTIONS,
    )

    class_group_id: Mapped[str] = mapped_column(
        ForeignKey("class_groups.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    student_id: Mapped[str] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(20), server_default="ACTIVE")
