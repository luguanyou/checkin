from io import BytesIO

import pytest
import test_course_export
from openpyxl import load_workbook
from test_template_export import add_scores

from attendance_api.errors import ApiError

context = test_course_export.context


def test_course_scores_are_exported_without_attendance_columns(context):
    from attendance_api.modules.exports.scores_service import generate_scores_export

    db, teacher, _, course, groups = context
    for group in groups:
        add_scores(db, group)
    payload = generate_scores_export(db, teacher=teacher, course_id=course.id)
    book = load_workbook(BytesIO(payload.content))
    assert len(book.worksheets) == 2
    sheet = book.worksheets[0]
    assert [c.value for c in sheet[1]] == [
        "序号",
        "课程",
        "班级",
        "学号",
        "姓名",
        "平时分",
        "名单状态",
        "评价状态",
    ]
    assert sheet["D2"].value == "000" and sheet["D2"].data_type == "s"
    assert sheet["F2"].value == 65
    assert sheet["F3"].value == 76
    assert sheet["F2"].data_type == "n"
    assert "/" not in payload.filename
    filtered = generate_scores_export(
        db, teacher=teacher, course_id=course.id, class_group_id=groups[1].id
    )
    assert len(load_workbook(BytesIO(filtered.content)).worksheets) == 1


def test_rules_and_ownership_are_checked(context):
    from attendance_api.modules.exports.scores_service import generate_scores_export

    db, teacher, other, course, groups = context
    add_scores(db, groups[0])
    from attendance_api.models.scores import ScoreSettings

    db.query(ScoreSettings).delete()
    db.flush()
    for owner, class_id, expected in [
        (teacher, groups[0].id, 409),
        (other, None, 404),
        (teacher, "missing", 404),
    ]:
        with pytest.raises(ApiError) as error:
            generate_scores_export(db, teacher=owner, course_id=course.id, class_group_id=class_id)
        assert error.value.status_code == expected


def test_zero_score_exports_even_without_attendance(context):
    from decimal import Decimal

    from attendance_api.models import AttendanceRecord, AttendanceSession
    from attendance_api.models.scores import ScoreSettings
    from attendance_api.modules.exports.scores_service import generate_scores_export

    db, teacher, _, course, groups = context
    add_scores(db, groups[0])
    db.query(AttendanceRecord).delete()
    db.query(AttendanceSession).delete()
    settings = db.query(ScoreSettings).one()
    settings.base_score = Decimal(0)
    settings.homework_factor = settings.classroom_factor = Decimal(0)
    settings.lab_factor = settings.other_factor = Decimal(0)
    db.flush()
    payload = generate_scores_export(
        db, teacher=teacher, course_id=course.id, class_group_id=groups[0].id
    )
    sheet = load_workbook(BytesIO(payload.content)).active
    assert sheet["F2"].value == 0 and sheet["F2"].data_type == "n"
