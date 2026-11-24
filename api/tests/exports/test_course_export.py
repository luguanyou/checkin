from datetime import date, timedelta
from io import BytesIO

import pytest
from openpyxl import load_workbook
from sqlalchemy import LargeBinary, MetaData, create_engine
from sqlalchemy.dialects.mysql import MEDIUMBLOB
from sqlalchemy.orm import Session

from attendance_api.errors import ApiError
from attendance_api.models import (
    AttendanceRecord,
    AttendanceSession,
    ClassGroup,
    Course,
    Student,
    User,
)
from attendance_api.models.base import Base, utc_now


@pytest.fixture
def context():
    engine = create_engine("sqlite://")
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        cloned = table.to_metadata(metadata)
        for column in cloned.columns:
            if column.name in ("created_at", "updated_at"):
                column.server_default = None
            if isinstance(column.type, MEDIUMBLOB):
                column.type = LargeBinary()
    metadata.create_all(engine)
    with Session(engine) as db:
        teacher = User(
            username="teacher",
            password_hash="unused",
            display_name="教师",
            role="TEACHER",
            status="ACTIVE",
            must_change_password=False,
        )
        other = User(
            username="other",
            password_hash="unused",
            display_name="其他",
            role="TEACHER",
            status="ACTIVE",
            must_change_password=False,
        )
        db.add_all([teacher, other])
        db.flush()
        course = Course(
            owner_teacher_id=teacher.id,
            name="数据库/应用",
            code="DB",
            term="2026秋",
            status="ACTIVE",
        )
        db.add(course)
        db.flush()
        groups = [
            ClassGroup(course_id=course.id, name=name, status="ACTIVE")
            for name in ["一/班", "二班"]
        ]
        students = [Student(student_number=f"00{i}", name=f"学生{i}") for i in range(2)]
        db.add_all([*groups, *students])
        db.flush()
        sessions = []
        for i, (group, status) in enumerate(
            [
                (groups[0], "COMPLETED"),
                (groups[0], "COMPLETED"),
                (groups[0], "DRAFT"),
                (groups[1], "COMPLETED"),
            ]
        ):
            session = AttendanceSession(
                class_group_id=group.id,
                session_date=date(2026, 9, 3),
                status=status,
                started_at=utc_now() + timedelta(hours=i),
                completed_at=utc_now() if status == "COMPLETED" else None,
                created_by=teacher.id,
            )
            db.add(session)
            db.flush()
            sessions.append(session)
            # Student 1 has only historical attendance in the first session.
            for j in [0, 1] if i == 0 else [0]:
                db.add(
                    AttendanceRecord(
                        session_id=session.id,
                        student_id=students[j].id,
                        student_number_snapshot=students[j].student_number,
                        student_name_snapshot="=姓名" if j == 0 else students[j].name,
                        class_name_snapshot=group.name,
                        status="leave" if i == 1 else "present",
                        marked_at=utc_now(),
                        last_modified_by=teacher.id,
                        version=1,
                    )
                )
        db.flush()
        yield db, teacher, other, course, groups
    engine.dispose()


def test_all_sessions_class_sheets_and_historical_roster(context):
    from attendance_api.modules.exports.course_service import generate_course_export

    db, teacher, _, course, _ = context
    payload = generate_course_export(db, teacher=teacher, course_id=course.id)
    book = load_workbook(BytesIO(payload.content))
    assert len(book.worksheets) == 2
    sheet = book.worksheets[0]
    assert sheet.max_column == 5  # Draft excluded, same-day sessions retained separately.
    assert sheet.cell(3, 4).value == "第1次\n2026-09-03"
    assert sheet.cell(3, 5).value == "第2次\n2026-09-03"
    assert [sheet.cell(4, i).value for i in range(1, 6)] == [1, "000", "=姓名", "√", "O"]
    assert sheet.cell(4, 2).data_type == sheet.cell(4, 3).data_type == "s"
    assert sheet.cell(5, 4).value == "√"
    assert sheet.cell(5, 5).value is None
    assert sheet.freeze_panes == "D4"
    assert "/" not in payload.filename
    book.close()


def test_filter_and_ownership(context):
    from attendance_api.modules.exports.course_service import generate_course_export

    db, teacher, other, course, groups = context
    payload = generate_course_export(
        db, teacher=teacher, course_id=course.id, class_group_id=groups[1].id
    )
    assert len(load_workbook(BytesIO(payload.content)).worksheets) == 1
    for owner, course_id, class_id, status in [
        (other, course.id, None, 404),
        (teacher, course.id, "missing", 404),
    ]:
        with pytest.raises(ApiError) as error:
            generate_course_export(db, teacher=owner, course_id=course_id, class_group_id=class_id)
        assert error.value.status_code == status


def test_no_completed_sessions(context):
    from attendance_api.modules.exports.course_service import generate_course_export

    db, teacher, _, course, _ = context
    for session in db.query(AttendanceSession).all():
        session.status = "DRAFT"
        session.completed_at = None
    db.flush()
    with pytest.raises(ApiError) as error:
        generate_course_export(db, teacher=teacher, course_id=course.id)
    assert error.value.status_code == 409
