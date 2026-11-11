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


def test_admin_resets_student_password_and_student_can_change_it(portal_context, portal_client):
    from attendance_api.security.passwords import hash_password

    db, teacher, student, group, other = portal_context
    client, app = portal_client
    old_password = "Old-student-password-123"
    temporary = "04268135"
    student.password_hash = hash_password(old_password)
    admin = User(
        username="reset-admin",
        display_name="Admin",
        password_hash=hash_password("Admin-password-123"),
        role="ADMIN",
        must_change_password=False,
    )
    db.add(admin)
    db.commit()
    del app.dependency_overrides[get_current_user]

    def login(username, password):
        return client.post("/api/v1/auth/login", json={"username": username, "password": password})

    def headers(response):
        assert response.status_code == 200
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    old_session = headers(login(student.username, old_password))
    admin_session = headers(login(admin.username, "Admin-password-123"))
    created_teacher = client.post(
        "/api/v1/admin/users",
        json={
            "username": "numeric-temp-teacher",
            "display_name": "Teacher",
            "temporary_password": "02468135",
        },
        headers=admin_session,
    )
    assert created_teacher.status_code == 201
    assert created_teacher.json()["must_change_password"]
    listed = client.get(
        "/api/v1/admin/users",
        params={"role": "STUDENT", "q": student.username},
        headers=admin_session,
    )
    assert [item["id"] for item in listed.json()["items"]] == [student.id]
    reset_url = f"/api/v1/admin/users/{student.id}/reset-password"
    payload = {"temporary_password": temporary}
    assert client.post(reset_url, json=payload, headers=old_session).status_code == 403
    assert client.post(reset_url, json=payload, headers=admin_session).status_code == 204
    assert client.get("/api/v1/auth/me", headers=old_session).status_code == 401
    assert login(student.username, old_password).status_code == 401

    signed_in = login(student.username, temporary)
    temporary_session = headers(signed_in)
    assert signed_in.json()["user"]["must_change_password"]
    assert client.get("/api/v1/student/classes", headers=temporary_session).status_code == 403
    assert (
        client.post(
            "/api/v1/auth/change-password",
            json={"current_password": temporary, "new_password": "12345678"},
            headers=temporary_session,
        ).status_code
        == 400
    )
    changed = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": temporary, "new_password": "New-student-password-123"},
        headers=temporary_session,
    )
    assert client.get("/api/v1/student/classes", headers=headers(changed)).status_code == 200
    assert login(student.username, temporary).status_code == 401
    assert login(student.username, "New-student-password-123").status_code == 200


@pytest.fixture
def second_teacher_class(portal_context):
    from attendance_api.models import ClassGroup, Course

    db, teacher, user, group, other = portal_context
    second = User(
        username="second",
        display_name="Second Teacher",
        password_hash="test",
        role="TEACHER",
        must_change_password=False,
    )
    db.add(second)
    db.flush()
    course = Course(owner_teacher_id=second.id, name="Second Course", code="C2", term="2026")
    db.add(course)
    db.flush()
    shared = ClassGroup(course_id=course.id, name=group.name)
    db.add(shared)
    db.commit()
    return second, shared


@pytest.mark.parametrize("decision", ["APPROVED", "REJECTED"])
def test_teachers_share_roster_student_applications_and_history(
    portal_context, portal_client, applicant, second_teacher_class, decision
):
    from attendance_api.models import AuditLog, StudentRegistration

    db, teacher, user, group, other = portal_context
    second, shared = second_teacher_class
    client, app = portal_client
    db.add(Enrollment(class_group_id=shared.id, student_id=applicant.id))
    db.commit()
    assert request_registration(client, group, applicant).status_code == 201
    app.dependency_overrides[get_current_user] = lambda: second
    url = f"/api/v1/classes/{shared.id}/registrations"
    pending = client.get(url)
    assert pending.status_code == 200
    assert len(pending.json()["items"]) == 1
    item = pending.json()["items"][0]
    assert item["can_review"]
    payload = {"registration_ids": [item["id"]], "decision": decision, "reason": "核验完成"}
    assert client.post(f"{url}/review", json=payload).status_code == 200
    assert client.get(url).json()["items"] == []
    reviewed = client.get(url, params={"status": "all"}).json()["items"][0]
    assert reviewed["reviewer_name"] == second.display_name
    assert reviewed["history"][0]["reviewer_name"] == second.display_name
    registration = db.get(StudentRegistration, item["id"])
    assert registration.class_group_id == group.id
    event = db.scalar(select(AuditLog).where(AuditLog.action == "REGISTRATION_REVIEWED"))
    assert event.after_value["class_id"] == group.id
    assert event.after_value["review_class_id"] == shared.id
    app.dependency_overrides[get_current_user] = lambda: teacher
    source_url = f"/api/v1/classes/{group.id}/registrations"
    source = client.get(source_url, params={"status": "all"}).json()["items"][0]
    assert source["history"] == reviewed["history"]
    assert client.post(f"{source_url}/review", json=payload).status_code == 409
    account = db.scalar(select(User).where(User.student_id == applicant.id))
    assert (account is not None) == (decision == "APPROVED")


@pytest.mark.parametrize("membership", ["missing", "removed", "active"])
def test_shared_review_requires_own_class_and_active_roster(
    portal_context, portal_client, applicant, second_teacher_class, membership
):
    from attendance_api.models import StudentRegistration

    db, teacher, user, group, other = portal_context
    second, shared = second_teacher_class
    client, app = portal_client
    if membership != "missing":
        db.add(
            Enrollment(
                class_group_id=shared.id,
                student_id=applicant.id,
                status="REMOVED" if membership == "removed" else "ACTIVE",
            )
        )
        db.commit()
    assert request_registration(client, group, applicant).status_code == 201
    registration = db.scalar(select(StudentRegistration))
    app.dependency_overrides[get_current_user] = lambda: second
    assert client.get(f"/api/v1/classes/{group.id}/registrations").status_code == 404
    url = f"/api/v1/classes/{shared.id}/registrations"
    items = client.get(url).json()["items"]
    assert len(items) == (1 if membership == "active" else 0)
    payload = {"registration_ids": [registration.id], "decision": "APPROVED"}
    if membership == "active":
        shared.status = "ARCHIVED"
        db.commit()
    assert client.post(f"{url}/review", json=payload).status_code == (
        409 if membership == "active" else 404
    )
    assert registration.status == "PENDING"


def test_two_teachers_see_new_registrations_and_share_one_student_account(
    portal_context, portal_client, applicant, second_teacher_class
):
    db, first_teacher, _, first_class, unrelated = portal_context
    second_teacher, second_class = second_teacher_class
    client, app = portal_client
    newcomer = Student(student_number="011", name="New applicant")
    db.add(newcomer)
    db.flush()
    db.add_all(
        [
            Enrollment(class_group_id=second_class.id, student_id=applicant.id),
            Enrollment(class_group_id=first_class.id, student_id=newcomer.id),
            Enrollment(class_group_id=second_class.id, student_id=newcomer.id),
        ]
    )
    db.commit()

    assert request_registration(client, first_class, applicant).status_code == 201
    app.dependency_overrides[get_current_user] = lambda: second_teacher
    url = f"/api/v1/classes/{second_class.id}/registrations"
    item = client.get(url).json()["items"][0]
    assert (
        client.post(
            f"{url}/review", json={"registration_ids": [item["id"]], "decision": "APPROVED"}
        ).status_code
        == 200
    )

    assert request_registration(client, second_class, newcomer).status_code == 201

    def assert_refreshed(teacher, group):
        app.dependency_overrides[get_current_user] = lambda: teacher
        refreshed = client.get(
            f"/api/v1/classes/{group.id}/registrations", params={"status": "all"}
        )
        assert refreshed.status_code == 200
        assert {row["student_number"]: row["status"] for row in refreshed.json()["items"]} == {
            applicant.student_number: "APPROVED",
            newcomer.student_number: "PENDING",
        }

    assert_refreshed(first_teacher, first_class)
    assert_refreshed(second_teacher, second_class)

    del app.dependency_overrides[get_current_user]
    login = client.post(
        "/api/v1/auth/login",
        json={"username": applicant.student_number, "password": "Registration-pass-123"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    classes = client.get("/api/v1/student/classes", headers=headers).json()["items"]
    assert {(row["id"], row["teacher_name"]) for row in classes} == {
        (first_class.id, first_teacher.display_name),
        (second_class.id, second_teacher.display_name),
    }
    for group in (first_class, second_class):
        assert client.get(f"/api/v1/student/classes/{group.id}", headers=headers).status_code == 200
    assert client.get(f"/api/v1/student/classes/{unrelated.id}", headers=headers).status_code == 404


def test_shared_batch_cannot_include_students_outside_teacher_roster(
    portal_context, portal_client, applicant, second_teacher_class
):
    from attendance_api.models import StudentRegistration

    db, teacher, user, group, other = portal_context
    second, shared = second_teacher_class
    client, app = portal_client
    outsider = Student(student_number="011", name="Outside roster")
    db.add(outsider)
    db.flush()
    db.add_all(
        [
            Enrollment(class_group_id=group.id, student_id=outsider.id),
            Enrollment(class_group_id=shared.id, student_id=applicant.id),
        ]
    )
    db.commit()
    assert request_registration(client, group, applicant).status_code == 201
    assert request_registration(client, group, outsider).status_code == 201
    registrations = list(db.scalars(select(StudentRegistration)))
    app.dependency_overrides[get_current_user] = lambda: second
    url = f"/api/v1/classes/{shared.id}/registrations"
    items = client.get(url).json()["items"]
    assert [item["student_number"] for item in items] == [applicant.student_number]
    response = client.post(
        f"{url}/review",
        json={
            "registration_ids": [item.id for item in registrations],
            "decision": "APPROVED",
        },
    )
    assert response.status_code == 404
    for registration in registrations:
        db.refresh(registration)
        assert registration.status == "PENDING"
        assert db.scalar(select(User).where(User.student_id == registration.student_id)) is None


def test_monitor_grant_does_not_expand_to_other_courses_applications(
    portal_context, portal_client, applicant, second_teacher_class
):
    from attendance_api.models import RegistrationReviewer, StudentRegistration

    db, teacher, user, group, other = portal_context
    second, shared = second_teacher_class
    client, app = portal_client
    db.add_all(
        [
            Enrollment(class_group_id=shared.id, student_id=applicant.id),
            RegistrationReviewer(class_group_id=group.id, user_id=user.id, granted_by=teacher.id),
        ]
    )
    db.commit()
    assert request_registration(client, shared, applicant).status_code == 201
    registration = db.scalar(select(StudentRegistration))
    url = f"/api/v1/classes/{group.id}/registrations"
    assert client.get(url).json()["items"] == []
    assert (
        client.post(
            f"{url}/review",
            json={
                "registration_ids": [registration.id],
                "decision": "APPROVED",
            },
        ).status_code
        == 404
    )
    # The teacher of this same roster can review the student's global account.
    app.dependency_overrides[get_current_user] = lambda: teacher
    assert len(client.get(url).json()["items"]) == 1


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
