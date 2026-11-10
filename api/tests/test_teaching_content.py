import json

from attendance_api.models import ClassGroup, Course, Enrollment, TeachingContent, User
from attendance_api.modules.auth.dependencies import get_current_user

pytest_plugins = ["test_portal"]


def test_material_is_shared_and_scope_changes_revoke_download(portal_client, portal_context):
    client, app = portal_client
    db, teacher, student, first, second = portal_context
    db.add(Enrollment(class_group_id=second.id, student_id=student.student_id))
    db.commit()
    app.dependency_overrides[get_current_user] = lambda: teacher
    teacher_url = f"/api/v1/classes/{first.id}/teaching-content"
    payload = {
        "kind": "MATERIAL",
        "title": "Chapter 3",
        "chapter": "3",
        "category": "SELF_STUDY",
        "class_ids": [first.id, second.id],
    }
    created = client.post(
        teacher_url,
        data={"payload": json.dumps(payload)},
        files={"file": ("讲义.pdf", b"%PDF-1.7", "application/pdf")},
    )
    assert created.status_code == 201, created.text
    item_id = created.json()["id"]
    first_url = f"/api/v1/student/classes/{first.id}/teaching-content"
    second_url = f"/api/v1/student/classes/{second.id}/teaching-content"
    app.dependency_overrides[get_current_user] = lambda: student
    for url in (first_url, second_url):
        assert client.get(url).json()["items"][0]["id"] == item_id
        download = client.get(f"{url}/{item_id}/attachment")
        assert download.content == b"%PDF-1.7"
        assert download.headers["cache-control"] == "no-store"
    assert client.post(teacher_url, data={"payload": json.dumps(payload)}).status_code == 403

    app.dependency_overrides[get_current_user] = lambda: teacher
    payload.update(title="Revised", class_ids=[second.id])
    assert (
        client.put(f"{teacher_url}/{item_id}", data={"payload": json.dumps(payload)}).status_code
        == 200
    )
    app.dependency_overrides[get_current_user] = lambda: student
    assert client.get(first_url).json()["items"] == []
    assert client.get(f"{first_url}/{item_id}/attachment").status_code == 404
    assert client.get(second_url).json()["items"][0]["title"] == "Revised"

    db.query(Enrollment).filter_by(class_group_id=second.id).one().status = "REMOVED"
    db.commit()
    assert client.get(second_url).status_code == 404
    assert client.get(f"{second_url}/{item_id}/attachment").status_code == 404


def test_assignment_requires_one_class_and_a_visible_resource(portal_client, portal_context):
    client, app = portal_client
    db, teacher, student, first, second = portal_context
    app.dependency_overrides[get_current_user] = lambda: teacher
    first_url = f"/api/v1/classes/{first.id}/teaching-content"
    second_url = f"/api/v1/classes/{second.id}/teaching-content"
    material = {
        "kind": "MATERIAL",
        "title": "Reading",
        "category": "CLASSROOM",
        "url": "https://example.org/reading",
        "class_ids": [second.id],
    }
    created = client.post(second_url, data={"payload": json.dumps(material)})
    assert created.status_code == 201, created.text
    material_id = created.json()["id"]
    assignment = {
        "kind": "ASSIGNMENT",
        "title": "Exercise",
        "description": "Solve question 1",
        "due_at": "2026-12-01T18:00:00+08:00",
        "submission_method": "Bring to class",
        "resource_id": material_id,
        "class_ids": [first.id, second.id],
    }
    assert client.post(first_url, data={"payload": json.dumps(assignment)}).status_code == 400
    assignment["class_ids"] = [first.id]
    assert client.post(first_url, data={"payload": json.dumps(assignment)}).status_code == 400
    material["class_ids"] = [first.id, second.id]
    response = client.put(f"{second_url}/{material_id}", data={"payload": json.dumps(material)})
    assert response.status_code == 200, response.text
    created = client.post(first_url, data={"payload": json.dumps(assignment)})
    assert created.status_code == 201, created.text
    item_id = created.json()["id"]
    assert created.json()["due_at"] == "2026-12-01T10:00:00Z"
    student_url = f"/api/v1/student/classes/{first.id}/teaching-content"
    app.dependency_overrides[get_current_user] = lambda: student
    items = {item["id"]: item for item in client.get(student_url).json()["items"]}
    assert items[item_id]["resource_id"] == material_id
    assert material_id in items
    app.dependency_overrides[get_current_user] = lambda: teacher
    material["class_ids"] = [second.id]
    response = client.put(f"{second_url}/{material_id}", data={"payload": json.dumps(material)})
    assert response.status_code == 200, response.text
    app.dependency_overrides[get_current_user] = lambda: student
    items = client.get(student_url).json()["items"]
    assert [item["id"] for item in items] == [item_id]
    assert items[0]["resource_id"] is None
    app.dependency_overrides[get_current_user] = lambda: teacher
    assert client.delete(f"{first_url}/{item_id}").status_code == 204
    app.dependency_overrides[get_current_user] = lambda: student
    assert client.get(student_url).json()["items"] == []


def test_teachers_cannot_publish_across_courses_or_manage_another_teachers_class(
    portal_client, portal_context
):
    client, app = portal_client
    db, teacher, _, first, _ = portal_context
    other_teacher = User(
        username="other",
        display_name="Other",
        password_hash="test",
        role="TEACHER",
        must_change_password=False,
    )
    db.add(other_teacher)
    db.flush()
    course = Course(owner_teacher_id=other_teacher.id, name="Other", code="C", term="2026")
    db.add(course)
    db.flush()
    foreign_class = ClassGroup(course_id=course.id, name=first.name)
    db.add(foreign_class)
    db.commit()
    url = f"/api/v1/classes/{first.id}/teaching-content"
    app.dependency_overrides[get_current_user] = lambda: teacher
    payload = {
        "kind": "MATERIAL",
        "title": "Reading",
        "category": "SELF_STUDY",
        "description": "Read chapter 3",
        "class_ids": [foreign_class.id],
    }
    assert client.post(url, data={"payload": json.dumps(payload)}).status_code == 400
    app.dependency_overrides[get_current_user] = lambda: other_teacher
    assert client.get(url).status_code == 404


def test_deleting_classes_preserves_shared_material_until_last_publication(
    portal_client, portal_context
):
    client, app = portal_client
    db, teacher, _, first, second = portal_context
    app.dependency_overrides[get_current_user] = lambda: teacher
    first_class = f"/api/v1/classes/{first.id}"
    second_class = f"/api/v1/classes/{second.id}"
    payload = {
        "kind": "MATERIAL",
        "title": "Notes",
        "category": "CLASSROOM",
        "description": "Read first",
        "class_ids": [first.id, second.id],
    }
    created = client.post(f"{first_class}/teaching-content", data={"payload": json.dumps(payload)})
    assert created.status_code == 201, created.text
    item_id = created.json()["id"]
    assert client.delete(f"{first_class}?delete_related_data=true").status_code == 204
    items = client.get(f"{second_class}/teaching-content").json()["items"]
    assert [item["class_ids"] for item in items] == [[second.id]]
    assert client.delete(second_class).status_code == 409
    assert client.delete(f"{second_class}?delete_related_data=true").status_code == 204
    assert db.get(TeachingContent, item_id) is None
