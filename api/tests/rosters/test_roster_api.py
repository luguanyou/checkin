from dataclasses import dataclass
from datetime import date

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from attendance_api.models import (
    AttendanceRecord,
    AttendanceSession,
    ClassGroup,
    Course,
    Enrollment,
    Student,
    User,
)
from attendance_api.models.base import utc_now

PASSWORD = "teacher-password-123"


@dataclass
class RosterContext:
    teacher_id: str
    class_group: ClassGroup
    client: TestClient


@pytest.fixture
def roster_context(client: TestClient, db_session: Session) -> RosterContext:
    teacher = User(
        username="roster-teacher",
        password_hash=PasswordHasher().hash(PASSWORD),
        display_name="名单教师",
        role="TEACHER",
        status="ACTIVE",
        must_change_password=False,
    )
    db_session.add(teacher)
    db_session.flush()
    course = Course(
        owner_teacher_id=teacher.id,
        name="设计课",
        code="DESIGN",
        term="2026 秋季学期",
        status="ACTIVE",
    )
    db_session.add(course)
    db_session.flush()
    class_group = ClassGroup(course_id=course.id, name="2024 级 2 班", status="ACTIVE")
    db_session.add(class_group)
    db_session.commit()
    login = client.post(
        "/api/v1/auth/login", json={"username": teacher.username, "password": PASSWORD}
    )
    client.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})
    return RosterContext(teacher.id, class_group, client)


def add_member(
    db: Session,
    class_group_id: str,
    *,
    number: str,
    name: str,
    major: str,
    status: str = "ACTIVE",
) -> Enrollment:
    student = Student(student_number=number, name=name, gender=None, major=major)
    db.add(student)
    db.flush()
    enrollment = Enrollment(class_group_id=class_group_id, student_id=student.id, status=status)
    db.add(enrollment)
    db.commit()
    return enrollment


def test_roster_is_scoped_and_searchable(
    roster_context: RosterContext, db_session: Session
) -> None:
    add_member(
        db_session,
        roster_context.class_group.id,
        number="20240001",
        name="林晓雨",
        major="工业设计",
    )
    add_member(
        db_session,
        roster_context.class_group.id,
        number="20240002",
        name="张敏",
        major="视觉传达",
        status="REMOVED",
    )

    active = roster_context.client.get(
        f"/api/v1/classes/{roster_context.class_group.id}/roster", params={"q": "工业"}
    )
    all_members = roster_context.client.get(
        f"/api/v1/classes/{roster_context.class_group.id}/roster", params={"status": "all"}
    )

    assert active.status_code == 200
    assert active.json()["total"] == 1
    assert active.json()["items"][0]["student"]["student_number"] == "20240001"
    assert all_members.json()["total"] == 2


def test_foreign_class_roster_returns_not_found(
    roster_context: RosterContext, db_session: Session
) -> None:
    other = User(
        username="roster-other",
        password_hash=PasswordHasher().hash(PASSWORD),
        display_name="其他教师",
        role="TEACHER",
        status="ACTIVE",
        must_change_password=False,
    )
    db_session.add(other)
    db_session.flush()
    course = Course(
        owner_teacher_id=other.id,
        name="其他课",
        code="OTHER",
        term="2026 秋季学期",
        status="ACTIVE",
    )
    db_session.add(course)
    db_session.flush()
    foreign_class = ClassGroup(course_id=course.id, name="其他班", status="ACTIVE")
    db_session.add(foreign_class)
    db_session.commit()

    response = roster_context.client.get(f"/api/v1/classes/{foreign_class.id}/roster")

    assert response.status_code == 404
    assert response.json()["code"] == "RESOURCE_NOT_FOUND"


def test_enrollment_status_change_preserves_attendance_snapshot(
    roster_context: RosterContext, db_session: Session
) -> None:
    enrollment = add_member(
        db_session,
        roster_context.class_group.id,
        number="20240001",
        name="林晓雨",
        major="工业设计",
    )
    session = AttendanceSession(
        class_group_id=roster_context.class_group.id,
        session_date=date(2026, 9, 3),
        status="DRAFT",
        started_at=utc_now(),
        created_by=roster_context.teacher_id,
    )
    db_session.add(session)
    db_session.flush()
    record = AttendanceRecord(
        session_id=session.id,
        student_id=enrollment.student_id,
        student_number_snapshot="20240001",
        student_name_snapshot="林晓雨",
        class_name_snapshot="2024 级 2 班",
        status="pending",
        last_modified_by=roster_context.teacher_id,
        version=1,
    )
    db_session.add(record)
    db_session.commit()

    response = roster_context.client.patch(
        f"/api/v1/enrollments/{enrollment.id}/status", json={"status": "REMOVED"}
    )

    assert response.status_code == 200
    assert response.json()["enrollment_status"] == "REMOVED"
    db_session.refresh(record)
    assert record.student_name_snapshot == "林晓雨"
    assert record.class_name_snapshot == "2024 级 2 班"
