"""Fill the original register layout without changing its row/column geometry."""

import re
from io import BytesIO
from math import ceil
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.comments import Comment
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy import select
from sqlalchemy.orm import Session

from attendance_api.errors import ApiError
from attendance_api.models import AttendanceRecord, AttendanceSession, ClassGroup, User
from attendance_api.modules.courses.service import get_owned_class_group, get_owned_course
from attendance_api.modules.exports.course_service import SYMBOLS
from attendance_api.modules.exports.service import ExportPayload, _safe_filename_base
from attendance_api.modules.scores.service import get_book
from attendance_api.schemas.scores import ScoreItem, ScoreRecord

TEMPLATE_PATH = Path(__file__).with_name("templates") / "attendance-register.xlsx"


def _text(sheet: Worksheet, row: int, col: int, value: str) -> None:
    cell = sheet.cell(row, col, value)
    cell.data_type = "s"


def _score_cells(
    sheet: Worksheet,
    row: int,
    enrollment_id: str,
    lookup: dict[tuple[str, str], ScoreRecord],
    removed: bool,
    items: list[ScoreItem],
    col: int,
) -> None:
    for offset, item in enumerate(items):
        record = lookup.get((enrollment_id, item.id))
        if removed and record is None:
            continue
        points = record.points if record else item.default_points
        cell = sheet.cell(row, col + offset)
        # Match get_book: an explicit ungraded record overrides the project default.
        cell.value = float(points) if points is not None else 0
        note = f"{item.occurred_on.isoformat()} · {item.name}"
        if points is None:
            note += "；尚未评价，按系统规则暂计 0 分"
        if record and record.note:
            note += f"；{record.note}"
        cell.comment = Comment(note, "考勤系统")


def generate_template_export(
    db: Session,
    *,
    teacher: User,
    course_id: str,
    class_group_id: str | None = None,
) -> ExportPayload:
    course = get_owned_course(db, teacher_id=teacher.id, course_id=course_id)
    if class_group_id:
        group, _ = get_owned_class_group(db, teacher_id=teacher.id, class_group_id=class_group_id)
        if group.course_id != course.id:
            raise ApiError(404, "RESOURCE_NOT_FOUND", "班级不存在")
    groups_query = select(ClassGroup).where(ClassGroup.course_id == course.id)
    if class_group_id:
        groups_query = groups_query.where(ClassGroup.id == class_group_id)
    groups = list(db.scalars(groups_query.order_by(ClassGroup.name, ClassGroup.id)))
    workbook = load_workbook(TEMPLATE_PATH)
    template = workbook.active
    assert isinstance(template, Worksheet)
    count = 0
    for group in groups:
        book = get_book(db, teacher_id=teacher.id, class_group_id=group.id)
        sessions = list(
            db.scalars(
                select(AttendanceSession)
                .where(
                    AttendanceSession.class_group_id == group.id,
                    AttendanceSession.status == "COMPLETED",
                )
                .order_by(
                    AttendanceSession.session_date,
                    AttendanceSession.started_at,
                    AttendanceSession.id,
                )
            )
        )
        records = list(
            db.scalars(
                select(AttendanceRecord)
                .join(AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id)
                .where(
                    AttendanceSession.class_group_id == group.id,
                    AttendanceSession.status == "COMPLETED",
                )
            )
        )
        records_by_session: dict[str, list[AttendanceRecord]] = {}
        for record in records:
            records_by_session.setdefault(record.session_id, []).append(record)
        identities = {s.student_id: (s.student_number, s.student_name) for s in book.students}
        for session in sessions:
            for record in records_by_session.get(session.id, []):
                identities[record.student_id] = (
                    record.student_number_snapshot,
                    record.student_name_snapshot,
                )
        if not identities:
            continue
        if not book.rules_ready:
            raise ApiError(
                409,
                "SCORE_RULES_PENDING",
                f"请先在“平时成绩”配置 {group.name} 的基础分和全部类别系数",
            )
        students = sorted(identities, key=lambda sid: (identities[sid][0], sid))
        enrollment_by_student = {s.student_id: s.enrollment_id for s in book.students}
        removed_students = {s.student_id for s in book.students if s.enrollment_status == "REMOVED"}
        score_records = {(r.enrollment_id, r.item_id): r for r in book.records}
        summaries = {s.enrollment_id: s for s in book.summaries}
        marks = {(r.student_id, r.session_id): SYMBOLS[r.status] for r in records}
        classroom = [item for item in book.items if item.category == "CLASSROOM"]
        homework = [item for item in book.items if item.category == "HOMEWORK"]
        data_pages = max(
            1, ceil(len(sessions) / 25), ceil(len(classroom) / 6), ceil(len(homework) / 6)
        )
        student_pages = ceil(len(students) / 41)
        for student_page in range(student_pages):
            for data_page in range(data_pages):
                sheet = workbook.copy_worksheet(template)
                title = re.sub(r"[\\/*?:\[\]]", "_", group.name).strip("'") or "班级"
                sheet.title = f"{title[:22]}-{student_page + 1}-{data_page + 1}"
                count += 1
                continuation = (
                    f"（名单{student_page + 1}/{student_pages}·记录{data_page + 1}/{data_pages}）"
                    if student_pages > 1 or data_pages > 1
                    else ""
                )
                _text(
                    sheet,
                    1,
                    1,
                    f"{course.term}    {group.name}    {course.name}    {teacher.display_name}"
                    f"    辅导员：________    出勤“√”  请假“O”  未到“×”  病假“假”"
                    f"  迟到“迟”  待确认“待”{continuation}",
                )
                page_sessions = sessions[data_page * 25 : (data_page + 1) * 25]
                for i in range(25):
                    _text(sheet, 3, i + 4, f"{data_page * 25 + i + 1}次")
                for i, session in enumerate(page_sessions):
                    sheet.cell(3, i + 4).comment = Comment(
                        f"{session.session_date.isoformat()}；场次 {session.id}", "考勤系统"
                    )
                for offset, sid in enumerate(students[student_page * 41 : (student_page + 1) * 41]):
                    row = offset + 4
                    sheet.cell(row, 1, student_page * 41 + offset + 1)
                    _text(sheet, row, 2, identities[sid][0])
                    _text(sheet, row, 3, identities[sid][1])
                    for i, session in enumerate(page_sessions):
                        mark = marks.get((sid, session.id), "")
                        _text(sheet, row, i + 4, "待" if mark == "待确认" else mark)
                    enrollment_id = enrollment_by_student.get(sid)
                    if enrollment_id:
                        _score_cells(
                            sheet,
                            row,
                            enrollment_id,
                            score_records,
                            sid in removed_students,
                            classroom[data_page * 6 : (data_page + 1) * 6],
                            29,
                        )
                        _score_cells(
                            sheet,
                            row,
                            enrollment_id,
                            score_records,
                            sid in removed_students,
                            homework[data_page * 6 : (data_page + 1) * 6],
                            35,
                        )
                        summary = summaries[enrollment_id]
                        if summary.final_score is not None:
                            sheet.cell(row, 41, float(summary.final_score))
                            sheet.cell(row, 41).comment = Comment(
                                "百分制平时成绩，尚未乘 40%。沿用系统基础分及作业、课堂、实验、"
                                "其他四类系数，限制在 0–100。未评项目按系统规则暂计 0 分。"
                                f"当前状态：{summary.status}",
                                "考勤系统",
                            )
    if not count:
        raise ApiError(409, "EXPORT_EMPTY", "所选课程或班级暂无学生或考勤数据")
    workbook.remove(template)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    filename = _safe_filename_base(f"{course.name}_{course.term}_考勤与日常考察记录表")
    return ExportPayload(
        content=output.getvalue(),
        filename=f"{filename}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
