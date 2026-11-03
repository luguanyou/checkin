import pytest
from sqlalchemy import select

from attendance_api.models import AuditLog, Enrollment, Student, User
from attendance_api.modules.auth.dependencies import get_current_user

pytest_plugins = ("test_portal",)


def test_teacher_edits_profile_and_linked_account(portal_context, portal_client):
    db, teacher, user, group, other = portal_context
    client, app = portal_client
    app.dependency_overrides[get_current_user] = lambda: teacher
    enrollment = db.scalar(select(Enrollment).where(Enrollment.student_id == user.student_id))
    url = f"/api/v1/classes/{group.id}/roster/{enrollment.id}"
    result = client.put(
        url, json={"student_number": " 008 ", "name": " 新姓名 ", "gender": "女", "major": "设计"}
    )
    assert result.status_code == 200, result.text
    assert result.json()["student"]["id"] == user.student_id
    assert result.json()["enrollment_id"] == enrollment.id
    assert result.json()["student"]["name"] == "新姓名"
    db.refresh(user)
    assert user.username == "008"
    assert user.display_name == "新姓名"
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "STUDENT_PROFILE_UPDATED"))
    assert audit.actor_user_id == teacher.id
    assert audit.before_value["student_number"] == "001"
    assert audit.after_value["student_number"] == "008"


def test_student_cannot_edit_and_foreign_scope_is_rejected(portal_context, portal_client):
    db, teacher, user, group, other = portal_context
    client, app = portal_client
    enrollment = db.scalar(select(Enrollment).where(Enrollment.student_id == user.student_id))
    payload = {"student_number": "008", "name": "Name"}
    assert (
        client.put(f"/api/v1/classes/{group.id}/roster/{enrollment.id}", json=payload).status_code
        == 403
    )
    app.dependency_overrides[get_current_user] = lambda: teacher
    assert (
        client.put(f"/api/v1/classes/{other.id}/roster/{enrollment.id}", json=payload).status_code
        == 404
    )
    outsider = User(
        username="other",
        display_name="Other",
        password_hash="test",
        role="TEACHER",
        must_change_password=False,
    )
    db.add(outsider)
    db.commit()
    app.dependency_overrides[get_current_user] = lambda: outsider
    assert (
        client.put(f"/api/v1/classes/{group.id}/roster/{enrollment.id}", json=payload).status_code
        == 404
    )


@pytest.mark.parametrize("collision", ["student", "username"])
def test_duplicate_edit_rolls_back_profile_and_account(portal_context, portal_client, collision):
    db, teacher, user, group, other = portal_context
    client, app = portal_client
    app.dependency_overrides[get_current_user] = lambda: teacher
    enrollment = db.scalar(select(Enrollment).where(Enrollment.student_id == user.student_id))
    db.add(
        Student(student_number="008", name="Other")
        if collision == "student"
        else User(username="008", display_name="Other", password_hash="test", role="TEACHER")
    )
    db.commit()
    result = client.put(
        f"/api/v1/classes/{group.id}/roster/{enrollment.id}",
        json={"student_number": "008", "name": "Changed"},
    )
    assert result.status_code == 409
    db.refresh(user)
    assert user.username == "001"
    assert db.get(Student, user.student_id).name == "Alice"


def test_edit_validates_and_blocks_archived_classes(portal_context, portal_client):
    db, teacher, user, group, other = portal_context
    client, app = portal_client
    app.dependency_overrides[get_current_user] = lambda: teacher
    enrollment = db.scalar(select(Enrollment).where(Enrollment.student_id == user.student_id))
    url = f"/api/v1/classes/{group.id}/roster/{enrollment.id}"
    assert client.put(url, json={"student_number": " ", "name": "Name"}).status_code == 400
    group.status = "ARCHIVED"
    db.commit()
    assert client.put(url, json={"student_number": "008", "name": "Name"}).status_code == 409


def test_edit_preserves_history_scores_and_enrollment_links(portal_context, portal_client):
    from datetime import date

    from attendance_api.models import AttendanceRecord, AttendanceSession, ScoreItem, ScoreRecord
    from attendance_api.models.base import utc_now

    db, teacher, user, group, other = portal_context
    client, app = portal_client
    app.dependency_overrides[get_current_user] = lambda: teacher
    enrollment = db.scalar(select(Enrollment).where(Enrollment.student_id == user.student_id))
    session = AttendanceSession(
        class_group_id=group.id,
        session_date=date(2026, 11, 3),
        started_at=utc_now(),
        created_by=teacher.id,
    )
    item = ScoreItem(
        class_group_id=group.id, category="HOMEWORK", name="Homework", occurred_on=date(2026, 11, 3)
    )
    db.add_all([session, item])
    db.flush()
    record = AttendanceRecord(
        session_id=session.id,
        student_id=user.student_id,
        student_number_snapshot="001",
        student_name_snapshot="Alice",
        class_name_snapshot="Class",
        last_modified_by=teacher.id,
    )
    score = ScoreRecord(item_id=item.id, enrollment_id=enrollment.id, points=3, note="Original")
    db.add_all([record, score])
    db.commit()
    result = client.put(
        f"/api/v1/classes/{group.id}/roster/{enrollment.id}",
        json={"student_number": "008", "name": "Changed", "gender": None, "major": ""},
    )
    assert result.status_code == 200
    db.refresh(record)
    db.refresh(score)
    assert record.student_number_snapshot == "001"
    assert record.student_name_snapshot == "Alice"
    assert score.enrollment_id == enrollment.id
    assert score.points == 3
    assert result.json()["student"]["major"] is None
