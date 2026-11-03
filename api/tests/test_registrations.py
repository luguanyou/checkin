import pytest
from sqlalchemy import select

from attendance_api.models import Enrollment, Student, User
from attendance_api.modules.auth.dependencies import get_current_user

pytest_plugins = ("test_portal",)


def test_student_registers_then_teacher_approves(portal_context, portal_client):
    db, teacher, user, group, other = portal_context
    client, app = portal_client
    student = Student(student_number="009", name="New Student")
    db.add(student)
    db.flush()
    db.add(Enrollment(class_group_id=group.id, student_id=student.id))
    db.commit()
    payload = {
        "student_number": "009",
        "name": "New Student",
        "class_id": group.id,
        "password": "Student-password-123",
    }
    response = client.post("/api/v1/auth/student-register", json=payload)
    assert response.status_code == 201
    assert db.scalar(select(User).where(User.student_id == student.id)) is None
    assert (
        client.post(
            "/api/v1/auth/login", json={"username": "009", "password": payload["password"]}
        ).status_code
        == 403
    )
    app.dependency_overrides[get_current_user] = lambda: teacher
    pending = client.get(f"/api/v1/classes/{group.id}/registrations").json()["items"]
    assert len(pending) == 1
    approved = client.post(
        f"/api/v1/classes/{group.id}/registrations/review",
        json={"registration_ids": [pending[0]["id"]], "decision": "APPROVED"},
    )
    assert approved.status_code == 200
    account = db.scalar(select(User).where(User.student_id == student.id))
    assert account.status == "ACTIVE" and not account.must_change_password
    assert (
        client.post(
            "/api/v1/auth/login", json={"username": "009", "password": payload["password"]}
        ).status_code
        == 200
    )


@pytest.fixture
def applicant(portal_context):
    db, teacher, user, group, other = portal_context
    student = Student(student_number="010", name="Applicant")
    db.add(student)
    db.flush()
    db.add(Enrollment(class_group_id=group.id, student_id=student.id))
    db.commit()
    return student


def request_registration(client, group, student, password="Registration-pass-123"):
    return client.post(
        "/api/v1/auth/student-register",
        json={
            "student_number": student.student_number,
            "name": student.name,
            "class_id": group.id,
            "password": password,
        },
    )


def test_monitor_review_permission_is_separate_revocable_and_scoped(
    portal_context, portal_client, applicant
):
    from attendance_api.models import RegistrationReviewer, StudentRegistration
    from attendance_api.modules.monitors.service import project_list

    db, teacher, user, group, other = portal_context
    client, app = portal_client
    assert request_registration(client, group, applicant).status_code == 201
    registration = db.scalar(
        select(StudentRegistration).where(StudentRegistration.student_id == applicant.id)
    )
    review_url = f"/api/v1/classes/{group.id}/registrations/review"
    payload = {"registration_ids": [registration.id], "decision": "APPROVED"}
    assert client.post(review_url, json=payload).status_code == 403
    app.dependency_overrides[get_current_user] = lambda: teacher
    grant_url = f"/api/v1/classes/{group.id}/monitors/{user.id}"
    assert (
        client.put(grant_url, json={"item_ids": [], "can_review_registrations": True}).status_code
        == 200
    )
    assert db.scalar(select(RegistrationReviewer).where(RegistrationReviewer.user_id == user.id))
    assert project_list(db, user) == []
    app.dependency_overrides[get_current_user] = lambda: user
    assert client.get("/api/v1/student/classes").json()["items"][0]["can_review_registrations"]
    assert client.get(f"/api/v1/classes/{other.id}/registrations").status_code == 403
    assert (
        client.put(grant_url, json={"item_ids": [], "can_review_registrations": True}).status_code
        == 403
    )
    app.dependency_overrides[get_current_user] = lambda: teacher
    assert (
        client.put(grant_url, json={"item_ids": [], "can_review_registrations": False}).status_code
        == 200
    )
    app.dependency_overrides[get_current_user] = lambda: user
    assert client.post(review_url, json=payload).status_code == 403
    app.dependency_overrides[get_current_user] = lambda: teacher
    assert (
        client.put(grant_url, json={"item_ids": [], "can_review_registrations": True}).status_code
        == 200
    )
    app.dependency_overrides[get_current_user] = lambda: user
    assert client.post(review_url, json=payload).status_code == 200
    from attendance_api.models import AuditLog

    event = db.scalar(select(AuditLog).where(AuditLog.action == "REGISTRATION_REVIEWED"))
    assert event.actor_user_id == user.id
    assert "password" not in str(event.after_value)


def test_rejection_reapplication_cannot_overwrite_pending_or_existing_account(
    portal_context, portal_client, applicant
):
    from attendance_api.models import StudentRegistration
    from attendance_api.security.passwords import verify_password

    db, teacher, user, group, other = portal_context
    client, app = portal_client
    assert request_registration(client, group, applicant).status_code == 201
    registration = db.scalar(
        select(StudentRegistration).where(StudentRegistration.student_id == applicant.id)
    )
    assert request_registration(client, group, applicant, "Hijack-password-123").status_code == 409
    assert verify_password(registration.password_hash, "Registration-pass-123")
    app.dependency_overrides[get_current_user] = lambda: teacher
    url = f"/api/v1/classes/{group.id}/registrations/review"
    assert (
        client.post(
            url,
            json={
                "registration_ids": [registration.id],
                "decision": "REJECTED",
                "reason": "请当面核对身份",
            },
        ).status_code
        == 200
    )
    response = client.post(
        "/api/v1/auth/login", json={"username": "010", "password": "Registration-pass-123"}
    )
    assert response.status_code == 403
    assert "请当面核对身份" in response.json()["message"]
    old_application_id = registration.id
    assert request_registration(client, group, applicant, "New-password-456").status_code == 201
    assert registration.id != old_application_id
    assert (
        client.post(
            url, json={"registration_ids": [old_application_id], "decision": "APPROVED"}
        ).status_code
        == 404
    )
    assert (
        client.post(
            url, json={"registration_ids": [registration.id], "decision": "APPROVED"}
        ).status_code
        == 200
    )
    assert request_registration(client, group, applicant).status_code == 409
    account = db.scalar(select(User).where(User.student_id == applicant.id))
    assert verify_password(account.password_hash, "New-password-456")
    assert registration.password_hash is None
    history = client.get(
        f"/api/v1/classes/{group.id}/registrations", params={"status": "all"}
    ).json()["items"][0]["history"]
    assert [event["status"] for event in history] == ["REJECTED", "APPROVED"]
    assert (
        client.post(
            url, json={"registration_ids": [registration.id], "decision": "APPROVED"}
        ).status_code
        == 409
    )


def test_batch_validation_prevents_partial_approval_and_self_review(
    portal_context, portal_client, applicant
):
    from attendance_api.models import RegistrationReviewer, StudentRegistration
    from attendance_api.security.passwords import hash_password

    db, teacher, user, group, other = portal_context
    client, app = portal_client
    request_registration(client, group, applicant)
    registration = db.scalar(
        select(StudentRegistration).where(StudentRegistration.student_id == applicant.id)
    )
    own = StudentRegistration(
        student_id=user.student_id,
        class_group_id=group.id,
        password_hash=hash_password("Initial-password-123"),
        status="PENDING",
    )
    db.add_all(
        [own, RegistrationReviewer(class_group_id=group.id, user_id=user.id, granted_by=teacher.id)]
    )
    db.commit()
    url = f"/api/v1/classes/{group.id}/registrations/review"
    assert (
        client.post(
            url, json={"registration_ids": [registration.id, own.id], "decision": "APPROVED"}
        ).status_code
        == 403
    )
    db.refresh(registration)
    assert registration.status == "PENDING"
    assert db.scalar(select(User).where(User.student_id == applicant.id)) is None
    app.dependency_overrides[get_current_user] = lambda: teacher
    assert (
        client.post(
            url, json={"registration_ids": [registration.id, "foreign-id"], "decision": "APPROVED"}
        ).status_code
        == 404
    )
    assert registration.status == "PENDING"


@pytest.mark.parametrize("invalid", ["name", "class", "password", "archived", "removed"])
def test_registration_validation(portal_context, portal_client, applicant, invalid):

    db, teacher, user, group, other = portal_context
    client, app = portal_client
    payload = {
        "student_number": "010",
        "name": "Applicant",
        "class_id": group.id,
        "password": "Student-password-123",
    }
    if invalid == "name":
        payload["name"] = "Wrong"
    if invalid == "class":
        payload["class_id"] = other.id
    if invalid == "password":
        payload["password"] = "short"
    if invalid == "archived":
        group.status = "ARCHIVED"
    if invalid == "removed":
        db.scalar(
            select(Enrollment).where(Enrollment.student_id == applicant.id)
        ).status = "REMOVED"
    db.commit()
    assert client.post("/api/v1/auth/student-register", json=payload).status_code == 400
    assert db.scalar(select(User).where(User.student_id == applicant.id)) is None
