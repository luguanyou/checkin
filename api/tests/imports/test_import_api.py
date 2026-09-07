from dataclasses import dataclass
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from attendance_api.models import ClassGroup, Course, Enrollment, ImportPreview, Student, User
from attendance_api.models.base import utc_now

PASSWORD = "teacher-password-123"
HEADER = "学号,姓名,性别,班级,专业\n"


@dataclass
class ImportContext:
    class_group: ClassGroup
    client: TestClient


@pytest.fixture
def import_context(client: TestClient, db_session: Session) -> ImportContext:
    teacher = User(
        username="import-teacher",
        password_hash=PasswordHasher().hash(PASSWORD),
        display_name="导入教师",
        role="TEACHER",
        status="ACTIVE",
        must_change_password=False,
    )
    db_session.add(teacher)
    db_session.flush()
    course = Course(
        owner_teacher_id=teacher.id,
        name="设计课",
        code="IMPORT",
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
    return ImportContext(class_group, client)


def preview(context: ImportContext, filename: str, content: bytes, content_type: str = "text/csv"):
    return context.client.post(
        f"/api/v1/classes/{context.class_group.id}/roster/import-preview",
        files={"file": (filename, content, content_type)},
    )


def test_preview_marks_required_duplicate_and_class_errors(import_context: ImportContext) -> None:
    content = (
        HEADER
        + "20260001,张敏,女,2024 级 2 班,工业设计\n"
        + "20260001,张敏,女,2024 级 2 班,工业设计\n"
        + "20260002,,男,2024 级 2 班,工业设计\n"
        + "20260003,李明,男,其他班,工业设计\n"
    ).encode()

    response = preview(import_context, "invalid.csv", content)

    assert response.status_code == 201
    body = response.json()
    assert body["summary"] == {
        "total": 4,
        "valid": 1,
        "errors": 2,
        "duplicates": 1,
        "importable": 1,
    }
    assert {row["code"] for row in body["rows"]} >= {
        "MISSING_REQUIRED_FIELD",
        "CLASS_MISMATCH",
        "DUPLICATE_IN_FILE",
    }


@pytest.mark.parametrize("encoding", ["utf-8-sig", "gb18030"])
def test_csv_encodings_are_supported(import_context: ImportContext, encoding: str) -> None:
    content = (HEADER + "20260001,张敏,女,2024 级 2 班,工业设计\n").encode(encoding)

    response = preview(import_context, "名单.csv", content)

    assert response.status_code == 201
    assert response.json()["summary"]["importable"] == 1
    assert response.json()["rows"][0]["name"] == "张敏"


def test_xlsx_is_supported(import_context: ImportContext) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["学号", "姓名", "性别", "班级", "专业"])
    sheet.append(["20260001", "张敏", "女", "2024 级 2 班", "工业设计"])
    output = BytesIO()
    workbook.save(output)

    response = preview(
        import_context,
        "名单.xlsx",
        output.getvalue(),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    assert response.status_code == 201
    assert response.json()["summary"]["importable"] == 1


@pytest.mark.parametrize(
    ("filename", "content"),
    [("名单.xlsx", b"not a workbook"), ("名单.txt", b"plain text")],
)
def test_spoofed_or_unsupported_files_are_rejected(
    import_context: ImportContext, filename: str, content: bytes
) -> None:
    response = preview(import_context, filename, content)

    assert response.status_code == 400
    assert response.json()["code"] in {"ROSTER_PARSE_FAILED", "UNSUPPORTED_FILE_TYPE"}


def test_more_than_500_rows_is_rejected(import_context: ImportContext) -> None:
    rows = [f"{20260000 + index},学生{index},,2024 级 2 班," for index in range(501)]
    content = (HEADER + "\n".join(rows)).encode()

    response = preview(import_context, "too-many.csv", content)

    assert response.status_code == 400
    assert response.json()["code"] == "ROSTER_ROW_LIMIT_EXCEEDED"


def test_system_identity_conflict_is_reported(
    import_context: ImportContext, db_session: Session
) -> None:
    db_session.add(Student(student_number="20260001", name="原姓名"))
    db_session.commit()
    content = (HEADER + "20260001,新姓名,,2024 级 2 班,\n").encode()

    response = preview(import_context, "conflict.csv", content)

    assert response.status_code == 201
    assert response.json()["rows"][0]["status"] == "identity_conflict"
    assert response.json()["rows"][0]["code"] == "STUDENT_IDENTITY_CONFLICT"


def test_preview_persists_no_original_file(
    import_context: ImportContext, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TemporaryDirectory(dir=Path.cwd()) as temp_directory:
        temp_file = Path(temp_directory) / "upload.csv"

        def fixed_temp_path() -> tuple[int, str]:
            import os

            descriptor = os.open(temp_file, os.O_CREAT | os.O_RDWR)
            return descriptor, str(temp_file)

        monkeypatch.setattr(
            "attendance_api.modules.imports.router.tempfile.mkstemp", fixed_temp_path
        )
        content = (HEADER + "20260001,张敏,,2024 级 2 班,\n").encode()

        response = preview(import_context, "../名单.csv", content)

        assert response.status_code == 201
        assert not temp_file.exists()
        saved = db_session.scalar(select(ImportPreview))
        assert saved is not None
        assert saved.source_filename == "名单.csv"


def test_confirm_creates_students_and_enrollments_atomically(
    import_context: ImportContext, db_session: Session
) -> None:
    content = (
        HEADER
        + "20260001,张敏,女,2024 级 2 班,工业设计\n"
        + "20260002,李明,男,2024 级 2 班,视觉传达\n"
    ).encode()
    preview_response = preview(import_context, "valid.csv", content)

    response = import_context.client.post(
        f"/api/v1/classes/{import_context.class_group.id}/roster/import-confirm",
        json={"preview_id": preview_response.json()["preview_id"], "duplicate_policy": "skip"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "preview_id": preview_response.json()["preview_id"],
        "created_students": 2,
        "created_enrollments": 2,
        "restored_enrollments": 0,
        "skipped": 0,
        "failed": 0,
    }
    assert db_session.scalar(select(func.count()).select_from(Student)) == 2
    assert db_session.scalar(select(func.count()).select_from(Enrollment)) == 2


def test_confirm_identity_conflict_rolls_back_every_row(
    import_context: ImportContext, db_session: Session
) -> None:
    db_session.add(Student(student_number="20260002", name="系统姓名"))
    db_session.commit()
    content = (
        HEADER
        + "20260001,张敏,女,2024 级 2 班,工业设计\n"
        + "20260002,导入姓名,男,2024 级 2 班,视觉传达\n"
    ).encode()
    preview_response = preview(import_context, "conflict.csv", content)
    student_count_before = db_session.scalar(select(func.count()).select_from(Student))
    enrollment_count_before = db_session.scalar(select(func.count()).select_from(Enrollment))

    response = import_context.client.post(
        f"/api/v1/classes/{import_context.class_group.id}/roster/import-confirm",
        json={
            "preview_id": preview_response.json()["preview_id"],
            "duplicate_policy": "replace",
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == "STUDENT_IDENTITY_CONFLICT"
    assert db_session.scalar(select(func.count()).select_from(Student)) == student_count_before
    assert (
        db_session.scalar(select(func.count()).select_from(Enrollment)) == enrollment_count_before
    )


@pytest.mark.parametrize(
    ("policy", "expected_status", "restored"),
    [
        ("skip", "REMOVED", 0),
        ("replace", "ACTIVE", 1),
    ],
)
def test_duplicate_policy_controls_removed_enrollment(
    import_context: ImportContext,
    db_session: Session,
    policy: str,
    expected_status: str,
    restored: int,
) -> None:
    student = Student(student_number="20260001", name="张敏")
    db_session.add(student)
    db_session.flush()
    enrollment = Enrollment(
        class_group_id=import_context.class_group.id,
        student_id=student.id,
        status="REMOVED",
    )
    db_session.add(enrollment)
    db_session.commit()
    content = (HEADER + "20260001,张敏,,2024 级 2 班,\n").encode()
    preview_response = preview(import_context, "duplicate.csv", content)

    response = import_context.client.post(
        f"/api/v1/classes/{import_context.class_group.id}/roster/import-confirm",
        json={"preview_id": preview_response.json()["preview_id"], "duplicate_policy": policy},
    )

    assert response.status_code == 200
    db_session.refresh(enrollment)
    assert enrollment.status == expected_status
    assert response.json()["restored_enrollments"] == restored
    assert response.json()["skipped"] == (0 if restored else 1)


def test_expired_and_confirmed_previews_are_rejected(
    import_context: ImportContext, db_session: Session
) -> None:
    content = (HEADER + "20260001,张敏,,2024 级 2 班,\n").encode()
    expired_response = preview(import_context, "expired.csv", content)
    expired = db_session.get(ImportPreview, expired_response.json()["preview_id"])
    assert expired is not None
    expired.expires_at = utc_now() - timedelta(seconds=1)
    db_session.commit()

    expired_confirm = import_context.client.post(
        f"/api/v1/classes/{import_context.class_group.id}/roster/import-confirm",
        json={"preview_id": expired.id, "duplicate_policy": "skip"},
    )
    assert expired_confirm.status_code == 409
    assert expired_confirm.json()["code"] == "IMPORT_PREVIEW_EXPIRED"

    valid_response = preview(import_context, "valid.csv", content)
    first = import_context.client.post(
        f"/api/v1/classes/{import_context.class_group.id}/roster/import-confirm",
        json={"preview_id": valid_response.json()["preview_id"], "duplicate_policy": "skip"},
    )
    second = import_context.client.post(
        f"/api/v1/classes/{import_context.class_group.id}/roster/import-confirm",
        json={"preview_id": valid_response.json()["preview_id"], "duplicate_policy": "skip"},
    )
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["code"] == "IMPORT_PREVIEW_ALREADY_CONFIRMED"
