from dataclasses import dataclass
from datetime import date, datetime

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from attendance_api.models import AttendanceSession, Course, Enrollment, Student, User

PASSWORD = "teacher-password-123"


@dataclass
class TeacherContext:
    id: str
    client: TestClient


@pytest.fixture
def teacher_context(client: TestClient, db_session: Session) -> TeacherContext:
    teacher = User(
        username="teacher",
        password_hash=PasswordHasher().hash(PASSWORD),
        display_name="任课教师",
        role="TEACHER",
        status="ACTIVE",
        must_change_password=False,
    )
    db_session.add(teacher)
    db_session.commit()
    login = client.post(
        "/api/v1/auth/login", json={"username": teacher.username, "password": PASSWORD}
    )
    assert login.status_code == 200
    client.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})
    return TeacherContext(teacher.id, client)


@pytest.fixture
def other_course(db_session: Session) -> Course:
    owner = User(
        username="other",
        password_hash=PasswordHasher().hash(PASSWORD),
        display_name="其他教师",
        role="TEACHER",
        status="ACTIVE",
        must_change_password=False,
    )
    db_session.add(owner)
    db_session.flush()
    course = Course(
        owner_teacher_id=owner.id,
        name="其他课程",
        code="OTHER",
        term="2026 秋季学期",
        status="ACTIVE",
    )
    db_session.add(course)
    db_session.commit()
    return course


def create_course(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/courses",
        json={"name": " 产品设计方法 ", "code": " PD204 ", "term": " 2026 秋季学期 "},
    )
    assert response.status_code == 201
    return response.json()


def test_teacher_creates_and_lists_only_own_courses(
    teacher_context: TeacherContext, other_course: Course
) -> None:
    created = create_course(teacher_context.client)

    listed = teacher_context.client.get("/api/v1/courses")

    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == created["id"]
    assert listed.json()["items"][0]["name"] == "产品设计方法"
    assert other_course.id not in {item["id"] for item in listed.json()["items"]}


def test_course_embeds_classes_and_active_student_counts(
    teacher_context: TeacherContext, db_session: Session
) -> None:
    course = create_course(teacher_context.client)
    class_response = teacher_context.client.post(
        f"/api/v1/courses/{course['id']}/classes", json={"name": "2024 级 2 班"}
    )
    assert class_response.status_code == 201
    class_id = class_response.json()["id"]
    for index, status in enumerate(["ACTIVE", "ACTIVE", "REMOVED"]):
        student = Student(student_number=f"202400{index}", name=f"学生{index}")
        db_session.add(student)
        db_session.flush()
        db_session.add(Enrollment(class_group_id=class_id, student_id=student.id, status=status))
    db_session.commit()

    listed = teacher_context.client.get("/api/v1/courses")

    summary = listed.json()["items"][0]["classes"][0]
    assert summary["name"] == "2024 级 2 班"
    assert summary["active_student_count"] == 2


def test_duplicate_course_code_and_term_is_rejected(teacher_context: TeacherContext) -> None:
    create_course(teacher_context.client)

    response = teacher_context.client.post(
        "/api/v1/courses",
        json={"name": "重复课程", "code": "PD204", "term": "2026 秋季学期"},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "DUPLICATE_RESOURCE"


def test_foreign_course_is_hidden(teacher_context: TeacherContext, other_course: Course) -> None:
    update = teacher_context.client.patch(
        f"/api/v1/courses/{other_course.id}", json={"name": "越权修改"}
    )
    create_class = teacher_context.client.post(
        f"/api/v1/courses/{other_course.id}/classes", json={"name": "越权班级"}
    )

    assert update.status_code == 404
    assert update.json()["code"] == "RESOURCE_NOT_FOUND"
    assert create_class.status_code == 404


def test_class_name_is_unique_within_course(teacher_context: TeacherContext) -> None:
    course = create_course(teacher_context.client)
    first = teacher_context.client.post(
        f"/api/v1/courses/{course['id']}/classes", json={"name": "一班"}
    )
    duplicate = teacher_context.client.post(
        f"/api/v1/courses/{course['id']}/classes", json={"name": " 一班 "}
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "DUPLICATE_RESOURCE"


def test_archived_course_rejects_new_classes(teacher_context: TeacherContext) -> None:
    course = create_course(teacher_context.client)
    archived = teacher_context.client.patch(
        f"/api/v1/courses/{course['id']}", json={"status": "ARCHIVED"}
    )

    response = teacher_context.client.post(
        f"/api/v1/courses/{course['id']}/classes", json={"name": "一班"}
    )

    assert archived.status_code == 200
    assert response.status_code == 409
    assert response.json()["code"] == "RESOURCE_STATE_CONFLICT"


def test_course_and_class_archives_are_one_way(teacher_context: TeacherContext) -> None:
    course = create_course(teacher_context.client)
    class_group = teacher_context.client.post(
        f"/api/v1/courses/{course['id']}/classes", json={"name": "一班"}
    ).json()
    class_archived = teacher_context.client.patch(
        f"/api/v1/classes/{class_group['id']}", json={"status": "ARCHIVED"}
    )
    class_reactivate = teacher_context.client.patch(
        f"/api/v1/classes/{class_group['id']}", json={"status": "ACTIVE"}
    )
    teacher_context.client.patch(f"/api/v1/courses/{course['id']}", json={"status": "ARCHIVED"})
    course_reactivate = teacher_context.client.patch(
        f"/api/v1/courses/{course['id']}", json={"status": "ACTIVE"}
    )

    assert class_archived.status_code == 200
    assert class_reactivate.status_code == 409
    assert course_reactivate.status_code == 409


def test_teacher_can_delete_empty_course_and_class(teacher_context: TeacherContext) -> None:
    course = create_course(teacher_context.client)
    class_group = teacher_context.client.post(
        f"/api/v1/courses/{course['id']}/classes", json={"name": "一班"}
    ).json()

    deleted_class = teacher_context.client.delete(f"/api/v1/classes/{class_group['id']}")
    deleted_course = teacher_context.client.delete(f"/api/v1/courses/{course['id']}")

    assert deleted_class.status_code == 204
    assert deleted_course.status_code == 204
    assert teacher_context.client.get("/api/v1/courses").json()["total"] == 0


def test_course_delete_requires_no_classes(teacher_context: TeacherContext) -> None:
    course = create_course(teacher_context.client)
    teacher_context.client.post(f"/api/v1/courses/{course['id']}/classes", json={"name": "一班"})

    response = teacher_context.client.delete(f"/api/v1/courses/{course['id']}")

    assert response.status_code == 409
    assert response.json()["code"] == "RESOURCE_STATE_CONFLICT"


def test_class_delete_requires_no_roster_or_attendance(
    teacher_context: TeacherContext, db_session: Session
) -> None:
    course = create_course(teacher_context.client)
    class_group = teacher_context.client.post(
        f"/api/v1/courses/{course['id']}/classes", json={"name": "一班"}
    ).json()
    student = Student(student_number="20240001", name="学生")
    db_session.add(student)
    db_session.flush()
    db_session.add(
        Enrollment(class_group_id=class_group["id"], student_id=student.id, status="REMOVED")
    )
    db_session.commit()

    roster_response = teacher_context.client.delete(f"/api/v1/classes/{class_group['id']}")
    assert roster_response.status_code == 409
    assert roster_response.json()["code"] == "RESOURCE_STATE_CONFLICT"

    db_session.query(Enrollment).delete()
    db_session.add(
        AttendanceSession(
            class_group_id=class_group["id"],
            session_date=date(2026, 9, 6),
            status="DRAFT",
            started_at=datetime(2026, 9, 6, 9),
            created_by=teacher_context.id,
        )
    )
    db_session.commit()
    attendance_response = teacher_context.client.delete(f"/api/v1/classes/{class_group['id']}")

    assert attendance_response.status_code == 409
    assert attendance_response.json()["code"] == "RESOURCE_STATE_CONFLICT"


def test_delete_hides_foreign_resources(
    teacher_context: TeacherContext, other_course: Course
) -> None:
    response = teacher_context.client.delete(f"/api/v1/courses/{other_course.id}")

    assert response.status_code == 404
    assert response.json()["code"] == "RESOURCE_NOT_FOUND"
