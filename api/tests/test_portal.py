import pytest
from sqlalchemy import MetaData, create_engine, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from attendance_api.models import ClassGroup, Course, Enrollment, Student, User
from attendance_api.models.base import Base
from attendance_api.modules.portal.service import student_class_data


def test_hidden_data_is_not_returned(portal_context):
    db, teacher, student_user, group, other = portal_context
    result = student_class_data(db, user=student_user, class_id=group.id)
    assert result["attendance"] is None
    assert result["score"] is None
    assert result["details"] is None


def test_student_cannot_access_another_class(portal_context):
    import pytest

    from attendance_api.errors import ApiError

    db, teacher, student_user, group, other = portal_context
    with pytest.raises(ApiError) as error:
        student_class_data(db, user=student_user, class_id=other.id)
    assert error.value.status_code == 404


@pytest.fixture
def portal_context():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        table.to_metadata(metadata)
    for table in metadata.tables.values():
        for column in table.columns:
            if column.server_default is not None and "CURRENT_TIMESTAMP" in str(
                column.server_default.arg
            ):
                column.server_default.arg = text("CURRENT_TIMESTAMP")
    metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        teacher = User(username="t", display_name="Teacher", password_hash="test", role="TEACHER")
        student = Student(student_number="001", name="Alice")
        db.add_all([teacher, student])
        db.flush()
        user = User(
            username="001",
            display_name="Alice",
            password_hash="test",
            role="STUDENT",
            student_id=student.id,
        )
        course = Course(owner_teacher_id=teacher.id, name="Course", code="C", term="2026")
        db.add_all([user, course])
        db.flush()
        group = ClassGroup(course_id=course.id, name="Class")
        other = ClassGroup(course_id=course.id, name="Other")
        db.add_all([group, other])
        db.flush()
        db.add(Enrollment(class_group_id=group.id, student_id=student.id))
        db.commit()
        yield db, teacher, user, group, other
    engine.dispose()


@pytest.fixture
def portal_client(portal_context):
    from fastapi.testclient import TestClient

    from attendance_api.db import get_db
    from attendance_api.main import create_app
    from attendance_api.modules.auth.dependencies import get_current_user

    db, teacher, user, group, other = portal_context
    teacher.must_change_password = False
    user.must_change_password = False
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app, base_url="https://testserver") as client:
        yield client, app


def test_total_only_and_details_never_include_peers(portal_context):
    from datetime import date
    from decimal import Decimal

    from attendance_api.models import ScoreItem, ScoreRecord, ScoreSettings

    db, teacher, user, group, other = portal_context
    peer = Student(student_number="999", name="Secret Peer")
    db.add(peer)
    db.flush()
    enrollment = db.query(Enrollment).filter_by(student_id=user.student_id).one()
    peer_enrollment = Enrollment(class_group_id=group.id, student_id=peer.id)
    item = ScoreItem(
        class_group_id=group.id,
        category="HOMEWORK",
        name="Task",
        occurred_on=date(2026, 11, 2),
        description="",
        default_points=None,
    )
    db.add_all(
        [
            peer_enrollment,
            item,
            ScoreSettings(
                class_group_id=group.id,
                base_score=70,
                homework_factor=1,
                lab_factor=1,
                classroom_factor=1,
                other_factor=1,
            ),
        ]
    )
    db.flush()
    db.add_all(
        [
            ScoreRecord(
                item_id=item.id, enrollment_id=enrollment.id, points=Decimal("2.5"), note="my note"
            ),
            ScoreRecord(
                item_id=item.id, enrollment_id=peer_enrollment.id, points=99, note="secret note"
            ),
        ]
    )
    group.score_visibility = "TOTAL"
    db.commit()
    result = student_class_data(db, user=user, class_id=group.id)
    assert result["score"]["final_score"] == "72.50"
    assert result["details"] is None
    group.score_visibility = "DETAILS"
    db.commit()
    result = student_class_data(db, user=user, class_id=group.id)
    assert len(result["details"]["records"]) == 1
    assert "secret" not in str(result).lower()
    group.score_visibility = "HIDDEN"
    db.commit()
    assert student_class_data(db, user=user, class_id=group.id)["score"] is None


def test_student_routes_deny_writes_and_teacher_pages(portal_client, portal_context):
    client, app = portal_client
    db, teacher, user, group, other = portal_context
    assert client.get("/api/v1/student/classes").status_code == 200
    assert client.get(f"/api/v1/student/classes/{other.id}").status_code == 404
    assert client.get(f"/api/v1/classes/{group.id}/roster").status_code == 403
    assert (
        client.put(
            f"/api/v1/classes/{group.id}/student-visibility",
            json={"attendance_visible": True, "score_visibility": "DETAILS"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/classes/{group.id}/scores/items",
            json={
                "expected_version": 0,
                "name": "fake",
                "category": "HOMEWORK",
                "occurred_on": "2026-11-02",
            },
        ).status_code
        == 403
    )


def test_teacher_controls_visibility_and_provisions_account(portal_client, portal_context):
    from attendance_api.modules.auth.dependencies import get_current_user
    from attendance_api.modules.auth.service import login
    from attendance_api.security.passwords import verify_password
    from attendance_api.security.tokens import decode_access_token

    client, app = portal_client
    db, teacher, user, group, other = portal_context
    app.dependency_overrides[get_current_user] = lambda: teacher
    url = f"/api/v1/classes/{group.id}/student-visibility"
    assert client.get(url).json() == {"attendance_visible": False, "score_visibility": "HIDDEN"}
    assert (
        client.put(url, json={"attendance_visible": True, "score_visibility": "TOTAL"}).status_code
        == 200
    )
    assert (
        client.put(
            url, json={"attendance_visible": True, "score_visibility": "INVALID"}
        ).status_code
        == 400
    )
    student = Student(student_number="002", name="Bob")
    db.add(student)
    db.flush()
    db.add(Enrollment(class_group_id=group.id, student_id=student.id))
    db.commit()
    endpoint = f"/api/v1/classes/{group.id}/students/{student.id}/account"
    password = "01234567"
    assert client.post(endpoint, json={"temporary_password": password}).status_code == 201
    account = db.query(User).filter_by(student_id=student.id).one()
    assert verify_password(account.password_hash, password)
    assert account.must_change_password
    assert client.post(endpoint, json={"temporary_password": password}).status_code == 409
    session = login(db, username="002", password=password, ip_address="test", user_agent="test")
    assert decode_access_token(session.access_token)["role"] == "STUDENT"


def test_attendance_is_scoped_and_hidden_after_closing(portal_client, portal_context):
    from datetime import date

    from attendance_api.models import AttendanceRecord, AttendanceSession
    from attendance_api.models.base import utc_now

    client, app = portal_client
    db, teacher, user, group, other = portal_context
    peer = Student(student_number="003", name="Peer")
    db.add(peer)
    db.flush()
    session = AttendanceSession(
        class_group_id=group.id,
        session_date=date(2026, 11, 2),
        started_at=utc_now(),
        created_by=teacher.id,
    )
    db.add(session)
    db.flush()
    for student_id, number in [(user.student_id, "001"), (peer.id, "003")]:
        db.add(
            AttendanceRecord(
                session_id=session.id,
                student_id=student_id,
                student_number_snapshot=number,
                student_name_snapshot=number,
                class_name_snapshot=group.name,
                status="pending",
                last_modified_by=teacher.id,
                version=1,
            )
        )
    group.attendance_visible = True
    db.commit()
    response = client.get(f"/api/v1/student/classes/{group.id}")
    assert response.headers["cache-control"] == "no-store"
    assert len(response.json()["attendance"]) == 1
    group.attendance_visible = False
    db.commit()
    assert client.get(f"/api/v1/student/classes/{group.id}").json()["attendance"] is None
    enrollment = db.query(Enrollment).filter_by(student_id=user.student_id).one()
    enrollment.status = "REMOVED"
    db.commit()
    assert client.get(f"/api/v1/student/classes/{group.id}").status_code == 404


def test_teacher_cannot_change_other_teachers_visibility(portal_client, portal_context):
    from attendance_api.modules.auth.dependencies import get_current_user

    client, app = portal_client
    db, teacher, user, group, other = portal_context
    other_teacher = User(
        username="other-teacher",
        display_name="Other",
        password_hash="test",
        role="TEACHER",
        must_change_password=False,
    )
    db.add(other_teacher)
    db.commit()
    app.dependency_overrides[get_current_user] = lambda: other_teacher
    url = f"/api/v1/classes/{group.id}/student-visibility"
    assert client.get(url).status_code == 404
    assert (
        client.put(
            url, json={"attendance_visible": True, "score_visibility": "DETAILS"}
        ).status_code
        == 404
    )


def test_teacher_resets_own_student_password_and_revokes_old_sessions(
    portal_client, portal_context
):
    from attendance_api.models import AuditLog, LoginSession
    from attendance_api.modules.auth.dependencies import get_current_user
    from attendance_api.modules.auth.service import login
    from attendance_api.security.passwords import hash_password, verify_password

    client, app = portal_client
    db, teacher, user, group, other = portal_context
    user.password_hash = hash_password("Old-student-password")
    old = login(
        db,
        username=user.username,
        password="Old-student-password",
        ip_address="test",
        user_agent="test",
    )
    app.dependency_overrides[get_current_user] = lambda: teacher
    url = f"/api/v1/classes/{group.id}/students/{user.student_id}/reset-password"
    response = client.post(url, json={"temporary_password": "02468135"})
    assert response.status_code == 200
    assert response.json() == {"username": user.username}
    assert response.headers["cache-control"] == "no-store"
    assert user.must_change_password
    assert verify_password(user.password_hash, "02468135")
    assert all(
        row.revoked_at
        for row in db.scalars(select(LoginSession).where(LoginSession.user_id == user.id))
    )
    event = db.scalar(select(AuditLog).where(AuditLog.action == "USER_PASSWORD_RESET"))
    assert event.actor_user_id == teacher.id
    assert "password" not in str(event.after_value).replace("must_change_password", "")

    del app.dependency_overrides[get_current_user]
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {old.access_token}"}
        ).status_code
        == 401
    )
    signed_in = client.post(
        "/api/v1/auth/login", json={"username": user.username, "password": "02468135"}
    )
    assert signed_in.status_code == 200
    headers = {"Authorization": f"Bearer {signed_in.json()['access_token']}"}
    assert client.get("/api/v1/student/classes", headers=headers).status_code == 403
    changed = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "02468135", "new_password": "New-student-password"},
        headers=headers,
    )
    assert changed.status_code == 200
    assert not changed.json()["user"]["must_change_password"]


@pytest.mark.parametrize("password", ["1234567", "123456789", "1234abcd", "１２３４５６７８"])
def test_teacher_rejects_invalid_short_temporary_passwords(portal_client, portal_context, password):
    from attendance_api.modules.auth.dependencies import get_current_user

    client, app = portal_client
    db, teacher, user, group, other = portal_context
    original_hash = user.password_hash
    app.dependency_overrides[get_current_user] = lambda: teacher
    response = client.post(
        f"/api/v1/classes/{group.id}/students/{user.student_id}/reset-password",
        json={"temporary_password": password},
    )
    assert response.status_code == 400
    assert user.password_hash == original_hash


@pytest.mark.parametrize(
    "case,expected",
    [
        ("student", 403),
        ("other_teacher", 404),
        ("other_class", 404),
        ("removed", 404),
        ("archived_class", 409),
        ("archived_course", 409),
        ("no_account", 404),
        ("short", 400),
    ],
)
def test_teacher_password_reset_is_scoped(portal_client, portal_context, case, expected):
    from attendance_api.modules.auth.dependencies import get_current_user
    from attendance_api.security.passwords import hash_password, verify_password

    client, app = portal_client
    db, teacher, user, group, other = portal_context
    user.password_hash = hash_password("Original-password-123")
    student_id = user.student_id
    class_id = group.id
    actor = teacher
    if case == "student":
        actor = user
    if case == "other_teacher":
        actor = User(
            username="outsider",
            display_name="Other",
            role="TEACHER",
            password_hash="test",
            must_change_password=False,
        )
        db.add(actor)
    if case == "other_class":
        class_id = other.id
    if case == "removed":
        db.scalar(select(Enrollment).where(Enrollment.student_id == student_id)).status = "REMOVED"
    if case == "archived_class":
        group.status = "ARCHIVED"
    if case == "archived_course":
        db.get(Course, group.course_id).status = "ARCHIVED"
    if case == "no_account":
        student = Student(student_number="new", name="No account")
        db.add(student)
        db.flush()
        db.add(Enrollment(class_group_id=group.id, student_id=student.id))
        student_id = student.id
    db.commit()
    app.dependency_overrides[get_current_user] = lambda: actor
    result = client.post(
        f"/api/v1/classes/{class_id}/students/{student_id}/reset-password",
        json={"temporary_password": "short" if case == "short" else "New-password-123"},
    )
    assert result.status_code == expected
    assert verify_password(user.password_hash, "Original-password-123")


def test_student_login_and_mandatory_password_change(portal_client, portal_context):
    from attendance_api.modules.auth.dependencies import get_current_user
    from attendance_api.security.passwords import hash_password

    client, app = portal_client
    db, teacher, user, group, other = portal_context
    user.password_hash = hash_password("Initial-password-123")
    user.must_change_password = True
    db.commit()
    del app.dependency_overrides[get_current_user]
    response = client.post(
        "/api/v1/auth/login", json={"username": "001", "password": "Initial-password-123"}
    )
    assert response.status_code == 200
    client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
    assert client.get("/api/v1/student/classes").status_code == 403
    changed = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "Initial-password-123", "new_password": "New-password-456"},
    )
    assert changed.status_code == 200
    client.headers["Authorization"] = f"Bearer {changed.json()['access_token']}"
    assert client.get("/api/v1/student/classes").status_code == 200
    assert client.get("/api/v1/courses").status_code == 403
