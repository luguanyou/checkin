import pytest

from attendance_api.modules.monitors.service import monitor_project

pytest_plugins = ('test_portal',)


def test_unauthorized_monitor_cannot_read_project(portal_context):
    from attendance_api.errors import ApiError

    db, teacher, user, group, other = portal_context
    with pytest.raises(ApiError) as error:
        monitor_project(db, user=user, class_id=group.id, item_id="unknown")
    assert error.value.status_code in (403, 404)


@pytest.fixture
def monitor_context(portal_context):
    from datetime import date

    from attendance_api.models import Enrollment, ScoreItem, ScoreRecord, Student

    db, teacher, user, group, other = portal_context
    peer = Student(student_number="009", name="Peer")
    db.add(peer)
    db.flush()
    peer_enrollment = Enrollment(class_group_id=group.id, student_id=peer.id)
    foreign_enrollment = Enrollment(class_group_id=other.id, student_id=peer.id)
    items = [
        ScoreItem(
            class_group_id=group.id,
            name=name,
            category="HOMEWORK",
            occurred_on=date(2026, 11, 2),
            description="",
        )
        for name in ["Allowed", "Secret"]
    ]
    foreign_item = ScoreItem(
        class_group_id=other.id,
        name="Foreign",
        category="HOMEWORK",
        occurred_on=date(2026, 11, 2),
        description="",
    )
    db.add_all([peer_enrollment, foreign_enrollment, *items, foreign_item])
    db.flush()
    db.add(
        ScoreRecord(
            item_id=items[1].id, enrollment_id=peer_enrollment.id, points=99, note="Secret grade"
        )
    )
    db.commit()
    return items, foreign_item, peer_enrollment, foreign_enrollment


def test_grant_save_audit_and_revoke(portal_context, portal_client, monitor_context):
    from sqlalchemy import select

    from attendance_api.models import AuditLog, Enrollment, ScoreRecord
    from attendance_api.modules.auth.dependencies import get_current_user

    db, teacher, user, group, other = portal_context
    items, foreign_item, peer, foreign_enrollment = monitor_context
    client, app = portal_client
    manage = f"/api/v1/classes/{group.id}/monitors"
    app.dependency_overrides[get_current_user] = lambda: teacher
    assert client.get(manage).status_code == 200
    assert client.put(f"{manage}/{user.id}", json={"item_ids": [items[0].id]}).status_code == 200
    app.dependency_overrides[get_current_user] = lambda: user
    projects = client.get("/api/v1/student/monitor-projects").json()["items"]
    assert [project["id"] for project in projects] == [items[0].id]
    assert client.get("/api/v1/student/classes").json()["items"][0]["can_record_scores"]
    url = f"/api/v1/student/classes/{group.id}/monitor-projects/{items[0].id}"
    response = client.get(url)
    assert response.status_code == 200
    assert "Secret" not in response.text
    assert "summaries" not in response.text
    assert not next(
        student
        for student in response.json()["students"]
        if student["student_id"] == user.student_id
    )["can_edit"]
    payload = {
        "expected_version": response.json()["version"],
        "records": [{"enrollment_id": peer.id, "points": "2.5", "note": "Recorded by monitor"}],
    }
    saved = client.put(url + "/records", json=payload)
    assert saved.status_code == 200, saved.text
    assert saved.json()["records"][0]["points"] == "2.5000"
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "SCORE_RECORD_UPDATED"))
    assert audit.actor_user_id == user.id
    assert client.put(url + "/records", json=payload).status_code == 409
    own = db.query(Enrollment).filter_by(student_id=user.student_id).one()
    payload["expected_version"] = saved.json()["version"]
    payload["records"][0]["enrollment_id"] = own.id
    assert client.put(url + "/records", json=payload).status_code == 403
    payload["records"][0]["enrollment_id"] = foreign_enrollment.id
    assert client.put(url + "/records", json=payload).status_code == 404
    assert (
        client.get(f"/api/v1/student/classes/{group.id}/monitor-projects/{items[1].id}").status_code
        == 403
    )
    assert (
        client.get(
            f"/api/v1/student/classes/{other.id}/monitor-projects/{foreign_item.id}"
        ).status_code
        == 403
    )
    app.dependency_overrides[get_current_user] = lambda: teacher
    assert client.put(f"{manage}/{user.id}", json={"item_ids": []}).status_code == 200
    app.dependency_overrides[get_current_user] = lambda: user
    assert client.get(url).status_code == 403
    assert client.put(url + "/records", json=payload).status_code == 403
    assert client.get("/api/v1/student/monitor-projects").json()["items"] == []
    assert (
        db.scalar(select(ScoreRecord).where(ScoreRecord.item_id == items[0].id)).note
        == "Recorded by monitor"
    )


def test_only_owner_can_manage_and_only_own_projects_can_be_granted(
    portal_context, portal_client, monitor_context
):
    from attendance_api.models import User
    from attendance_api.modules.auth.dependencies import get_current_user

    db, teacher, user, group, other = portal_context
    items, foreign_item, peer, foreign_enrollment = monitor_context
    client, app = portal_client
    url = f"/api/v1/classes/{group.id}/monitors"
    assert client.get(url).status_code == 403
    assert client.put(f"{url}/{user.id}", json={"item_ids": [items[0].id]}).status_code == 403
    app.dependency_overrides[get_current_user] = lambda: teacher
    assert client.put(f"{url}/{user.id}", json={"item_ids": [foreign_item.id]}).status_code == 400
    other_teacher = User(
        username="different",
        display_name="Other",
        password_hash="test",
        role="TEACHER",
        must_change_password=False,
    )
    db.add(other_teacher)
    db.commit()
    app.dependency_overrides[get_current_user] = lambda: other_teacher
    assert client.get(url).status_code == 404
    assert client.put(f"{url}/{user.id}", json={"item_ids": [items[0].id]}).status_code == 404


@pytest.mark.parametrize("state", ["REMOVED", "ARCHIVED", "DISABLED"])
def test_inactive_monitor_scope_cannot_read_or_save(
    portal_context, portal_client, monitor_context, state
):
    from attendance_api.models import Enrollment
    from attendance_api.modules.monitors.service import replace_grants

    db, teacher, user, group, other = portal_context
    items, foreign_item, peer, foreign_enrollment = monitor_context
    client, app = portal_client
    replace_grants(db, teacher=teacher, class_id=group.id, user_id=user.id, item_ids=[items[0].id])
    if state == "REMOVED":
        db.query(Enrollment).filter_by(student_id=user.student_id).one().status = state
    elif state == "ARCHIVED":
        group.status = state
    else:
        user.status = state
    db.commit()
    url = f"/api/v1/student/classes/{group.id}/monitor-projects/{items[0].id}"
    assert client.get(url).status_code == 403
    assert (
        client.put(
            url + "/records",
            json={
                "expected_version": 0,
                "records": [{"enrollment_id": peer.id, "points": "1", "note": ""}],
            },
        ).status_code
        == 403
    )
