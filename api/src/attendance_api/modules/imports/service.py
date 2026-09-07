from datetime import timedelta
from pathlib import Path
from typing import cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from attendance_api.errors import ApiError
from attendance_api.models import Enrollment, ImportPreview, Student, User
from attendance_api.models.base import utc_now
from attendance_api.modules.audit.service import append_audit
from attendance_api.modules.courses.service import get_owned_class_group
from attendance_api.modules.imports.parser import (
    ParsedRoster,
    parse_roster,
    sanitize_filename,
    summarize_rows,
)


def _mark_database_conflicts(
    db: Session, class_group_id: str, parsed: ParsedRoster
) -> dict[str, object]:
    validation_rows = [dict(row) for row in parsed.validation["rows"]]
    numbers = [str(row["student_number"]) for row in validation_rows if row["student_number"]]
    students = {
        student.student_number: student
        for student in db.scalars(select(Student).where(Student.student_number.in_(numbers)))
    }
    enrolled_numbers = set(
        db.scalars(
            select(Student.student_number)
            .join(Enrollment, Enrollment.student_id == Student.id)
            .where(
                Enrollment.class_group_id == class_group_id,
                Student.student_number.in_(numbers),
            )
        )
    )
    for row in validation_rows:
        if row["status"] != "valid":
            continue
        number = str(row["student_number"])
        student = students.get(number)
        if student is not None and student.name != row["name"]:
            row.update(
                status="identity_conflict",
                code="STUDENT_IDENTITY_CONFLICT",
                fields=["student_number", "name"],
                message="系统中相同学号对应不同姓名",
            )
        elif number in enrolled_numbers:
            row.update(
                status="duplicate",
                code="DUPLICATE_ENROLLMENT",
                fields=["student_number"],
                message="班级中已存在该学生",
            )
    return {"summary": summarize_rows(validation_rows), "rows": validation_rows}


def preview_import(
    db: Session,
    *,
    teacher: User,
    class_group_id: str,
    path: Path,
    filename: str,
) -> ImportPreview:
    class_group, course = get_owned_class_group(
        db, teacher_id=teacher.id, class_group_id=class_group_id
    )
    if class_group.status != "ACTIVE" or course.status != "ACTIVE":
        raise ApiError(409, "RESOURCE_STATE_CONFLICT", "已归档课程或班级不能导入名单")
    parsed = parse_roster(path, filename, class_group.name)
    validation = _mark_database_conflicts(db, class_group.id, parsed)
    preview = ImportPreview(
        class_group_id=class_group.id,
        created_by=teacher.id,
        source_filename=sanitize_filename(filename),
        normalized_rows=parsed.rows,
        validation_result=validation,
        expires_at=utc_now() + timedelta(hours=1),
    )
    db.add(preview)
    db.commit()
    return preview


def confirm_import(
    db: Session,
    *,
    teacher: User,
    class_group_id: str,
    preview_id: str,
    duplicate_policy: str,
    ip_address: str,
    request_id: str,
) -> dict[str, int | str]:
    class_group, course = get_owned_class_group(
        db, teacher_id=teacher.id, class_group_id=class_group_id
    )
    if class_group.status != "ACTIVE" or course.status != "ACTIVE":
        raise ApiError(409, "RESOURCE_STATE_CONFLICT", "已归档课程或班级不能修改名单")
    preview = db.scalar(
        select(ImportPreview)
        .where(
            ImportPreview.id == preview_id,
            ImportPreview.class_group_id == class_group_id,
            ImportPreview.created_by == teacher.id,
        )
        .with_for_update()
    )
    if preview is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "导入预览不存在")
    now = utc_now()
    if preview.expires_at <= now:
        raise ApiError(409, "IMPORT_PREVIEW_EXPIRED", "导入预览已过期")
    if preview.confirmed_at is not None:
        raise ApiError(409, "IMPORT_PREVIEW_ALREADY_CONFIRMED", "导入预览已确认")

    validation_rows = cast(list[dict[str, object]], preview.validation_result["rows"])
    if any(row["status"] == "error" for row in validation_rows):
        raise ApiError(422, "ROSTER_VALIDATION_FAILED", "名单存在校验错误")

    unique_rows: list[dict[str, object]] = []
    seen: set[str] = set()
    duplicate_file_count = 0
    for row in validation_rows:
        number = str(row["student_number"])
        if number in seen or row["code"] == "DUPLICATE_IN_FILE":
            duplicate_file_count += 1
            continue
        seen.add(number)
        unique_rows.append(row)

    existing_students = {
        student.student_number: student
        for student in db.scalars(
            select(Student).where(Student.student_number.in_(seen)).with_for_update()
        )
    }
    conflicts = [
        {
            "student_number": str(row["student_number"]),
            "existing_name": existing_students[str(row["student_number"])].name,
            "imported_name": str(row["name"]),
        }
        for row in unique_rows
        if str(row["student_number"]) in existing_students
        and existing_students[str(row["student_number"])].name != str(row["name"])
    ]
    if conflicts:
        raise ApiError(
            409,
            "STUDENT_IDENTITY_CONFLICT",
            "相同学号对应不同姓名",
            {"conflicts": conflicts},
        )

    created_students = 0
    created_enrollments = 0
    restored_enrollments = 0
    skipped = duplicate_file_count
    try:
        for row in unique_rows:
            number = str(row["student_number"])
            student = existing_students.get(number)
            if student is None:
                student = Student(
                    student_number=number,
                    name=str(row["name"]),
                    gender=str(row["gender"]) if row.get("gender") else None,
                    major=str(row["major"]) if row.get("major") else None,
                )
                db.add(student)
                db.flush()
                existing_students[number] = student
                created_students += 1
            enrollment = db.scalar(
                select(Enrollment)
                .where(
                    Enrollment.class_group_id == class_group_id,
                    Enrollment.student_id == student.id,
                )
                .with_for_update()
            )
            if enrollment is None:
                db.add(
                    Enrollment(
                        class_group_id=class_group_id,
                        student_id=student.id,
                        status="ACTIVE",
                    )
                )
                created_enrollments += 1
            elif enrollment.status == "REMOVED" and duplicate_policy == "replace":
                enrollment.status = "ACTIVE"
                restored_enrollments += 1
            else:
                skipped += 1
        preview.confirmed_at = now
        counts: dict[str, int | str] = {
            "preview_id": preview.id,
            "created_students": created_students,
            "created_enrollments": created_enrollments,
            "restored_enrollments": restored_enrollments,
            "skipped": skipped,
            "failed": 0,
        }
        append_audit(
            db,
            actor_user_id=teacher.id,
            action="ROSTER_IMPORTED",
            entity_type="class_group",
            entity_id=class_group_id,
            before_value=None,
            after_value={key: value for key, value in counts.items() if key != "preview_id"},
            reason=None,
            ip_address=ip_address,
            request_id=request_id,
        )
        db.commit()
        return counts
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "STUDENT_IDENTITY_CONFLICT", "学生身份或名单关系发生冲突") from None
