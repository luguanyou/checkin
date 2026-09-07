from dataclasses import dataclass

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from attendance_api.models import (
    AttendanceRecord,
    ClassGroup,
    Course,
    Enrollment,
    Student,
    User,
)
from attendance_api.models.base import utc_now

PASSWORD = "teacher-password-123"


@dataclass
class AttendanceContext:
    teacher: User
    course: Course
    class_group: ClassGroup
    enrollments: list[Enrollment]
    client: TestClient


@pytest.fixture
def attendance_context(client: TestClient, db_session: Session) -> AttendanceContext:
    teacher = User(
        username="attendance-teacher",
        password_hash=PasswordHasher().hash(PASSWORD),
        display_name="考勤教师",
        role="TEACHER",
        status="ACTIVE",
        must_change_password=False,
    )
    db_session.add(teacher)
    db_session.flush()
    course = Course(
        owner_teacher_id=teacher.id,
        name="设计课",
        code="ATTEND",
        term="2026 秋季学期",
        status="ACTIVE",
    )
    db_session.add(course)
    db_session.flush()
    class_group = ClassGroup(course_id=course.id, name="2024 级 2 班", status="ACTIVE")
    db_session.add(class_group)
    db_session.flush()
    enrollments = []
    for index, enrollment_status in enumerate(["ACTIVE", "ACTIVE", "ACTIVE", "REMOVED"]):
        student = Student(
            student_number=f"2024000{index + 1}",
            name=f"学生{index + 1}",
            gender=None,
            major="工业设计",
        )
        db_session.add(student)
        db_session.flush()
        enrollment = Enrollment(
            class_group_id=class_group.id,
            student_id=student.id,
            status=enrollment_status,
        )
        db_session.add(enrollment)
        enrollments.append(enrollment)
    db_session.commit()
    login = client.post(
        "/api/v1/auth/login", json={"username": teacher.username, "password": PASSWORD}
    )
    client.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})
    return AttendanceContext(teacher, course, class_group, enrollments, client)


def create_session(context: AttendanceContext, session_date: str = "2026-09-03"):
    return context.client.post(
        f"/api/v1/classes/{context.class_group.id}/attendance-sessions",
        json={"session_date": session_date},
    )


def test_create_session_snapshots_every_active_roster_member(
    attendance_context: AttendanceContext,
) -> None:
    response = create_session(attendance_context)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "DRAFT"
    assert len(body["records"]) == 3
    assert {record["status"] for record in body["records"]} == {"pending"}
    assert body["summary"]["pending"] == 3
    assert [record["student_number"] for record in body["records"]] == sorted(
        record["student_number"] for record in body["records"]
    )


def test_empty_archived_and_foreign_classes_are_rejected(
    attendance_context: AttendanceContext, db_session: Session
) -> None:
    empty_class = ClassGroup(course_id=attendance_context.course.id, name="空班", status="ACTIVE")
    db_session.add(empty_class)
    db_session.commit()
    empty = attendance_context.client.post(
        f"/api/v1/classes/{empty_class.id}/attendance-sessions",
        json={"session_date": "2026-09-03"},
    )
    attendance_context.class_group.status = "ARCHIVED"
    db_session.commit()
    archived = create_session(attendance_context)

    other = User(
        username="attendance-other",
        password_hash=PasswordHasher().hash(PASSWORD),
        display_name="其他教师",
        role="TEACHER",
        status="ACTIVE",
        must_change_password=False,
    )
    db_session.add(other)
    db_session.flush()
    other_course = Course(
        owner_teacher_id=other.id,
        name="其他课",
        code="OTHER-ATTEND",
        term="2026 秋季学期",
        status="ACTIVE",
    )
    db_session.add(other_course)
    db_session.flush()
    foreign_class = ClassGroup(course_id=other_course.id, name="其他班", status="ACTIVE")
    db_session.add(foreign_class)
    db_session.commit()
    foreign = attendance_context.client.post(
        f"/api/v1/classes/{foreign_class.id}/attendance-sessions",
        json={"session_date": "2026-09-03"},
    )

    assert empty.status_code == 409 and empty.json()["code"] == "ROSTER_EMPTY"
    assert archived.status_code == 409
    assert archived.json()["code"] == "RESOURCE_STATE_CONFLICT"
    assert foreign.status_code == 404


def test_same_class_and_date_is_unique(attendance_context: AttendanceContext) -> None:
    first = create_session(attendance_context)
    duplicate = create_session(attendance_context)

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "DUPLICATE_RESOURCE"


def test_list_filters_and_omits_records(attendance_context: AttendanceContext) -> None:
    first = create_session(attendance_context, "2026-09-03")
    second = create_session(attendance_context, "2026-09-04")
    assert first.status_code == 201 and second.status_code == 201

    response = attendance_context.client.get(
        "/api/v1/attendance-sessions",
        params={
            "course_id": attendance_context.course.id,
            "class_group_id": attendance_context.class_group.id,
            "status": "DRAFT",
            "date_from": "2026-09-04",
            "date_to": "2026-09-04",
        },
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["session_date"] == "2026-09-04"
    assert "records" not in response.json()["items"][0]


def test_detail_keeps_creation_snapshots(
    attendance_context: AttendanceContext, db_session: Session
) -> None:
    created = create_session(attendance_context).json()
    attendance_context.enrollments[0].status = "REMOVED"
    attendance_context.class_group.name = "重命名班级"
    db_session.commit()

    response = attendance_context.client.get(f"/api/v1/attendance-sessions/{created['id']}")

    assert response.status_code == 200
    assert len(response.json()["records"]) == 3
    assert {item["class_name"] for item in response.json()["records"]} == {"2024 级 2 班"}


def test_detail_summary_contains_all_status_counts(
    attendance_context: AttendanceContext, db_session: Session
) -> None:
    created = create_session(attendance_context).json()
    records = list(
        db_session.scalars(
            select(AttendanceRecord)
            .where(AttendanceRecord.session_id == created["id"])
            .order_by(AttendanceRecord.student_number_snapshot)
        )
    )
    for record, status in zip(records, ["present", "absent", "late"], strict=True):
        record.status = status
        record.marked_at = utc_now()
        record.last_modified_at = utc_now()
    db_session.commit()

    response = attendance_context.client.get(f"/api/v1/attendance-sessions/{created['id']}")

    assert response.status_code == 200
    assert response.json()["summary"] == {
        "total": 3,
        "pending": 0,
        "present": 1,
        "absent": 1,
        "leave": 0,
        "late": 1,
        "exceptions": 2,
    }
