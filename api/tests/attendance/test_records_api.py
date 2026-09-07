from dataclasses import dataclass
from datetime import date

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from attendance_api.models import (
    AttendanceRecord,
    AttendanceSession,
    AuditLog,
    ClassGroup,
    Course,
    Student,
    User,
)
from attendance_api.models.base import utc_now

PASSWORD = "teacher-password-123"
MUTATION_ONE = "e9329885-359a-49b9-8846-6fad26c6501b"
MUTATION_TWO = "f9329885-359a-49b9-8846-6fad26c6501c"


@dataclass
class RecordContext:
    teacher: User
    attendance_session: AttendanceSession
    records: list[AttendanceRecord]
    client: TestClient


@pytest.fixture
def record_context(client: TestClient, db_session: Session) -> RecordContext:
    teacher = User(
        username="record-teacher",
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
        code="RECORD",
        term="2026 秋季学期",
        status="ACTIVE",
    )
    db_session.add(course)
    db_session.flush()
    class_group = ClassGroup(course_id=course.id, name="2024 级 2 班", status="ACTIVE")
    db_session.add(class_group)
    db_session.flush()
    attendance_session = AttendanceSession(
        class_group_id=class_group.id,
        session_date=date(2026, 9, 3),
        status="DRAFT",
        started_at=utc_now(),
        created_by=teacher.id,
    )
    db_session.add(attendance_session)
    db_session.flush()
    records = []
    for index in range(2):
        student = Student(student_number=f"2024000{index + 1}", name=f"学生{index + 1}")
        db_session.add(student)
        db_session.flush()
        record = AttendanceRecord(
            session_id=attendance_session.id,
            student_id=student.id,
            student_number_snapshot=student.student_number,
            student_name_snapshot=student.name,
            class_name_snapshot=class_group.name,
            status="pending",
            last_modified_by=teacher.id,
            version=1,
        )
        db_session.add(record)
        records.append(record)
    db_session.commit()
    login = client.post(
        "/api/v1/auth/login", json={"username": teacher.username, "password": PASSWORD}
    )
    client.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})
    return RecordContext(teacher, attendance_session, records, client)


def update_record(
    context: RecordContext,
    record: AttendanceRecord,
    *,
    status: str,
    expected_version: int,
    mutation_id: str,
    reason: str | None = None,
):
    payload: dict[str, object] = {
        "status": status,
        "expected_version": expected_version,
        "client_mutation_id": mutation_id,
    }
    if reason is not None:
        payload["reason"] = reason
    return context.client.patch(f"/api/v1/attendance-records/{record.id}", json=payload)


def test_stale_version_returns_current_record_without_update(record_context: RecordContext) -> None:
    record = record_context.records[0]

    response = update_record(
        record_context,
        record,
        status="late",
        expected_version=2,
        mutation_id=MUTATION_ONE,
    )

    assert response.status_code == 409
    assert response.json()["code"] == "ATTENDANCE_RECORD_CONFLICT"
    assert response.json()["details"]["current_record"] == {
        "id": record.id,
        "status": "pending",
        "version": 1,
    }


def test_draft_update_increments_version_and_writes_audit(
    record_context: RecordContext, db_session: Session
) -> None:
    record = record_context.records[0]

    response = update_record(
        record_context,
        record,
        status="present",
        expected_version=1,
        mutation_id=MUTATION_ONE,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "present"
    assert response.json()["version"] == 2
    assert response.json()["marked_at"] is not None
    audit = db_session.scalar(select(AuditLog).where(AuditLog.client_mutation_id == MUTATION_ONE))
    assert audit is not None
    assert audit.before_value["status"] == "pending"
    assert audit.after_value["version"] == 2


def test_completed_record_requires_reason_and_audits_it(
    record_context: RecordContext, db_session: Session
) -> None:
    record_context.attendance_session.status = "COMPLETED"
    record_context.attendance_session.completed_at = utc_now()
    record = record_context.records[0]
    record.status = "present"
    record.marked_at = utc_now()
    db_session.commit()

    missing_reason = update_record(
        record_context,
        record,
        status="late",
        expected_version=1,
        mutation_id=MUTATION_ONE,
    )
    corrected = update_record(
        record_context,
        record,
        status="late",
        expected_version=1,
        mutation_id=MUTATION_TWO,
        reason=" 学生点名后到场 ",
    )

    assert missing_reason.status_code == 400
    assert missing_reason.json()["code"] == "INVALID_REQUEST"
    assert corrected.status_code == 200
    audit = db_session.scalar(select(AuditLog).where(AuditLog.client_mutation_id == MUTATION_TWO))
    assert audit is not None and audit.reason == "学生点名后到场"


def test_same_mutation_replays_first_response(record_context: RecordContext) -> None:
    record = record_context.records[0]
    first = update_record(
        record_context,
        record,
        status="absent",
        expected_version=1,
        mutation_id=MUTATION_ONE,
    )
    replay = update_record(
        record_context,
        record,
        status="late",
        expected_version=1,
        mutation_id=MUTATION_ONE,
    )

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json() == first.json()


def test_mutation_id_cannot_be_reused_for_another_record(record_context: RecordContext) -> None:
    first = update_record(
        record_context,
        record_context.records[0],
        status="present",
        expected_version=1,
        mutation_id=MUTATION_ONE,
    )
    reused = update_record(
        record_context,
        record_context.records[1],
        status="present",
        expected_version=1,
        mutation_id=MUTATION_ONE,
    )

    assert first.status_code == 200
    assert reused.status_code == 400
    assert reused.json()["code"] == "INVALID_REQUEST"


def test_pending_records_are_preserved_when_session_is_completed(
    record_context: RecordContext, db_session: Session
) -> None:
    response = record_context.client.post(
        f"/api/v1/attendance-sessions/{record_context.attendance_session.id}/complete"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    db_session.refresh(record_context.attendance_session)
    for record in record_context.records:
        db_session.refresh(record)
    assert record_context.attendance_session.status == "COMPLETED"
    assert [record.status for record in record_context.records] == ["pending", "pending"]


def test_completion_is_idempotent_and_preserves_timestamp(
    record_context: RecordContext, db_session: Session
) -> None:
    for record in record_context.records:
        record.status = "present"
        record.marked_at = utc_now()
        record.last_modified_at = utc_now()
    db_session.commit()

    first = record_context.client.post(
        f"/api/v1/attendance-sessions/{record_context.attendance_session.id}/complete"
    )
    second = record_context.client.post(
        f"/api/v1/attendance-sessions/{record_context.attendance_session.id}/complete"
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["completed_at"] == second.json()["completed_at"]
    assert "records" not in first.json()
    audit_count = db_session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.action == "ATTENDANCE_SESSION_COMPLETED")
    )
    assert audit_count == 1
