from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
import test_course_export
from openpyxl import load_workbook
from sqlalchemy import select

from attendance_api.errors import ApiError
from attendance_api.models import Enrollment, Student
from attendance_api.models.scores import ScoreItem, ScoreRecord, ScoreSettings

context = test_course_export.context


def add_scores(db, group):
    students = list(db.scalars(select(Student).order_by(Student.student_number)))
    for student in students:
        db.add(Enrollment(class_group_id=group.id, student_id=student.id, status="ACTIVE"))
    db.add(
        ScoreSettings(
            class_group_id=group.id,
            base_score=Decimal(70),
            homework_factor=Decimal(2),
            classroom_factor=Decimal(3),
            lab_factor=Decimal(1),
            other_factor=Decimal(0),
        )
    )
    items = [
        ScoreItem(
            class_group_id=group.id,
            category=category,
            name=category,
            occurred_on=date(2026, 9, 3),
            default_points=Decimal(1),
        )
        for category in ["HOMEWORK", "CLASSROOM", "LAB"]
    ]
    db.add_all(items)
    db.flush()
    enrollment = db.scalar(
        select(Enrollment).where(
            Enrollment.class_group_id == group.id, Enrollment.student_id == students[0].id
        )
    )
    db.add(ScoreRecord(item_id=items[0].id, enrollment_id=enrollment.id, points=Decimal(0)))
    db.add(ScoreRecord(item_id=items[1].id, enrollment_id=enrollment.id, points=Decimal(-2)))
    db.flush()


def test_template_matches_format_and_uses_existing_score_calculation(context):
    from attendance_api.modules.exports.template_service import (
        TEMPLATE_PATH,
        generate_template_export,
    )

    db, teacher, _, course, groups = context
    add_scores(db, groups[0])
    payload = generate_template_export(
        db, teacher=teacher, course_id=course.id, class_group_id=groups[0].id
    )
    book = load_workbook(BytesIO(payload.content))
    s = book.active
    template = load_workbook(TEMPLATE_PATH).active
    assert (s.max_row, s.max_column) == (44, 43)
    assert set(map(str, s.merged_cells.ranges)) == set(map(str, template.merged_cells.ranges))
    assert s["D4"].value == "√" and s["E4"].value == "O"
    assert s["AC4"].value == -2 and s["AI4"].value == 0
    assert s["AO4"].value == 65  # 70 + 0*2 - 2*3 + 1*1
    assert s["AO5"].value == 76  # All three project defaults contribute.
    assert s["AP4"].value is None and s["AQ4"].value is None
    assert s["B4"].data_type == "s" and s["C4"].data_type == "s"
    assert "HOMEWORK" in s["AI4"].comment.text
    for row in range(1, 45):
        assert s.row_dimensions[row].height == template.row_dimensions[row].height
        for col in range(1, 44):
            assert s.cell(row, col)._style == template.cell(row, col)._style
    for col in template.column_dimensions:
        assert s.column_dimensions[col].width == template.column_dimensions[col].width
    assert s.page_setup == template.page_setup
    book.close()


def test_rules_missing_blocks_export(context):
    from attendance_api.modules.exports.template_service import generate_template_export

    db, teacher, _, course, groups = context
    with pytest.raises(ApiError) as error:
        generate_template_export(
            db, teacher=teacher, course_id=course.id, class_group_id=groups[0].id
        )
    assert error.value.code == "SCORE_RULES_PENDING"


def test_overflow_projects_uses_continuation_without_changing_layout(context):
    from attendance_api.modules.exports.template_service import generate_template_export

    db, teacher, _, course, groups = context
    add_scores(db, groups[0])
    db.add_all(
        [
            ScoreItem(
                class_group_id=groups[0].id,
                category="HOMEWORK",
                name=f"作业{i}",
                occurred_on=date(2026, 9, 4),
                default_points=Decimal(i),
            )
            for i in range(7)
        ]
    )
    db.flush()
    output = generate_template_export(
        db, teacher=teacher, course_id=course.id, class_group_id=groups[0].id
    )
    book = load_workbook(BytesIO(output.content))
    assert len(book.worksheets) == 2
    assert all((s.max_row, s.max_column) == (44, 43) for s in book)
    assert book.worksheets[1]["AI4"].value is not None
    assert book.worksheets[0]["AO4"].value == book.worksheets[1]["AO4"].value


def test_student_and_attendance_overflow_are_not_truncated(context):
    from attendance_api.models import AttendanceRecord, AttendanceSession
    from attendance_api.models.base import utc_now
    from attendance_api.modules.exports.template_service import generate_template_export

    db, teacher, _, course, groups = context
    add_scores(db, groups[0])
    for i in range(41):
        student = Student(student_number=f"1{i:03}", name=f"新增{i}")
        db.add(student)
        db.flush()
        db.add(Enrollment(class_group_id=groups[0].id, student_id=student.id, status="ACTIVE"))
    student = db.scalar(select(Student).where(Student.student_number == "000"))
    for _i in range(24):
        session = AttendanceSession(
            class_group_id=groups[0].id,
            session_date=date(2026, 9, 4),
            started_at=utc_now(),
            completed_at=utc_now(),
            status="COMPLETED",
            created_by=teacher.id,
        )
        db.add(session)
        db.flush()
        db.add(
            AttendanceRecord(
                session_id=session.id,
                student_id=student.id,
                student_number_snapshot="000",
                student_name_snapshot="=姓名",
                class_name_snapshot=groups[0].name,
                status="late",
                marked_at=utc_now(),
                last_modified_by=teacher.id,
                version=1,
            )
        )
    db.flush()
    payload = generate_template_export(
        db, teacher=teacher, course_id=course.id, class_group_id=groups[0].id
    )
    book = load_workbook(BytesIO(payload.content))
    assert len(book.worksheets) == 4  # 43 students and 26 completed sessions.
    assert book.worksheets[1]["D3"].value == "26次"
    assert book.worksheets[1]["D4"].value == "迟"
    assert book.worksheets[2]["A4"].value == 42
    assert book.worksheets[2]["A5"].value == 43
    assert book.worksheets[2]["D4"].value is None
    assert all((s.max_row, s.max_column) == (44, 43) for s in book)


def test_foreign_course_is_denied(context):
    from attendance_api.modules.exports.template_service import generate_template_export

    db, _, other, course, _ = context
    with pytest.raises(ApiError) as error:
        generate_template_export(db, teacher=other, course_id=course.id)
    assert error.value.status_code == 404
