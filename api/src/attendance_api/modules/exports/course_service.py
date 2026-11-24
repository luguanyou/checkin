"""Course-wide attendance matrices built from historical attendance snapshots."""

import re
from collections import defaultdict
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session

from attendance_api.errors import ApiError
from attendance_api.models import AttendanceRecord, AttendanceSession, ClassGroup, User
from attendance_api.modules.courses.service import get_owned_class_group, get_owned_course
from attendance_api.modules.exports.service import ExportPayload, _safe_filename_base

SYMBOLS = {"present": "√", "leave": "O", "absent": "×", "late": "迟", "pending": "待确认"}


def generate_course_export(
    db: Session, *, teacher: User, course_id: str, class_group_id: str | None = None
) -> ExportPayload:
    course = get_owned_course(db, teacher_id=teacher.id, course_id=course_id)
    if class_group_id:
        group, _ = get_owned_class_group(db, teacher_id=teacher.id, class_group_id=class_group_id)
        if group.course_id != course.id:
            raise ApiError(404, "RESOURCE_NOT_FOUND", "班级不存在")
    query = (
        select(AttendanceSession, ClassGroup)
        .join(ClassGroup, ClassGroup.id == AttendanceSession.class_group_id)
        .where(ClassGroup.course_id == course.id, AttendanceSession.status == "COMPLETED")
        .order_by(
            ClassGroup.name,
            ClassGroup.id,
            AttendanceSession.session_date,
            AttendanceSession.started_at,
            AttendanceSession.id,
        )
    )
    if class_group_id:
        query = query.where(ClassGroup.id == class_group_id)
    sessions = list(db.execute(query).tuples())
    if not sessions:
        raise ApiError(409, "NO_COMPLETED_ATTENDANCE", "所选课程或班级暂无已完成的考勤记录")

    # A join keeps the complete export independent of list pagination and large IN lists.
    records_query = (
        select(AttendanceRecord)
        .join(AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id)
        .join(ClassGroup, ClassGroup.id == AttendanceSession.class_group_id)
        .where(ClassGroup.course_id == course.id, AttendanceSession.status == "COMPLETED")
    )
    if class_group_id:
        records_query = records_query.where(ClassGroup.id == class_group_id)
    records_by_session: dict[str, list[AttendanceRecord]] = defaultdict(list)
    for record in db.scalars(records_query):
        records_by_session[record.session_id].append(record)
    groups: dict[str, tuple[ClassGroup, list[AttendanceSession]]] = {}
    for session, group in sessions:
        if group.id not in groups:
            groups[group.id] = (group, [])
        groups[group.id][1].append(session)

    workbook = Workbook()
    workbook.remove(workbook.active)  # type: ignore[arg-type]
    thin = Side(style="thin", color="CBD5E1")
    for group, class_sessions in groups.values():
        if len(class_sessions) > 16381:
            raise ApiError(409, "EXPORT_TOO_LARGE", "场次数超出 Excel 列数限制")
        title = re.sub(r"[\\/*?:\[\]]", "_", group.name).strip("'")[:31] or "班级"
        # openpyxl automatically suffixes duplicate sanitized names.
        sheet = workbook.create_sheet(title)
        last_col = len(class_sessions) + 3
        sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_col)
        sheet.cell(
            1, 1, f"{course.term} · {course.name} · {group.name} · {teacher.display_name}"
        ).data_type = "s"
        sheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=last_col)
        sheet.cell(
            2,
            1,
            "出勤 √  请假 O  缺勤 ×  迟到 迟  待确认：待确认；空白：该场次无记录。仅含已完成场次。",
        )
        headers = ["序号", "学号", "姓名"] + [
            f"第{i}次\n{session.session_date.isoformat()}"
            for i, session in enumerate(class_sessions, 1)
        ]
        sheet.append(headers)
        identities: dict[str, AttendanceRecord] = {}
        marks: dict[tuple[str, str], str] = {}
        for session in class_sessions:
            for record in records_by_session[session.id]:
                identities[record.student_id] = record
                marks[(record.student_id, session.id)] = SYMBOLS[record.status]
        students = sorted(
            identities.values(), key=lambda r: (r.student_number_snapshot, r.student_id)
        )
        if len(students) > 1048573:
            raise ApiError(409, "EXPORT_TOO_LARGE", "学生数超出 Excel 行数限制")
        for index, record in enumerate(students, 1):
            values = [record.student_number_snapshot, record.student_name_snapshot] + [
                marks.get((record.student_id, session.id), "") for session in class_sessions
            ]
            sheet.cell(index + 3, 1, index)
            for col, value in enumerate(values, 2):
                cell = sheet.cell(index + 3, col, value)
                cell.data_type = "s"
        sheet.freeze_panes = "D4"
        sheet.auto_filter.ref = f"A3:{get_column_letter(last_col)}{sheet.max_row}"
        sheet.row_dimensions[1].height = 30
        sheet.row_dimensions[2].height = 32
        sheet.row_dimensions[3].height = 36
        for col in range(1, last_col + 1):
            sheet.column_dimensions[get_column_letter(col)].width = (
                7 if col == 1 else 20 if col == 2 else 16 if col == 3 else 13
            )
        for row in sheet.iter_rows():
            for cell in row:
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                cell.font = Font(name="微软雅黑", size=10)
                if cell.row >= 3:
                    cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
                if cell.row == 3:
                    cell.fill = PatternFill("solid", fgColor="E2E8F0")
                    cell.font = Font(name="微软雅黑", size=10, bold=True)
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        sheet.page_setup.orientation = "landscape"
        sheet.page_setup.paperSize = sheet.PAPERSIZE_A3
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 0
        sheet.print_title_rows = "1:3"
        sheet.print_options.horizontalCentered = True
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    suffix = f"_{groups[class_group_id][0].name}" if class_group_id else ""
    filename = _safe_filename_base(f"{course.name}_{course.term}{suffix}_课程考勤汇总")
    return ExportPayload(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"{filename}.xlsx",
    )
