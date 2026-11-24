"""A compact course-wide grade list using the canonical score summaries."""

import re
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session

from attendance_api.errors import ApiError
from attendance_api.models import ClassGroup, User
from attendance_api.modules.courses.service import get_owned_class_group, get_owned_course
from attendance_api.modules.exports.service import ExportPayload, _safe_filename_base
from attendance_api.modules.scores.export import STATUS_LABELS
from attendance_api.modules.scores.service import get_book


def generate_scores_export(
    db: Session, *, teacher: User, course_id: str, class_group_id: str | None = None
) -> ExportPayload:
    course = get_owned_course(db, teacher_id=teacher.id, course_id=course_id)
    if class_group_id:
        group, _ = get_owned_class_group(db, teacher_id=teacher.id, class_group_id=class_group_id)
        if group.course_id != course.id:
            raise ApiError(404, "RESOURCE_NOT_FOUND", "班级不存在")
    query = select(ClassGroup).where(ClassGroup.course_id == course.id)
    if class_group_id:
        query = query.where(ClassGroup.id == class_group_id)
    workbook = Workbook()
    default_sheet = workbook.active
    assert default_sheet is not None
    for group in db.scalars(query.order_by(ClassGroup.name, ClassGroup.id)):
        book = get_book(db, teacher_id=teacher.id, class_group_id=group.id)
        if not book.students:
            continue
        if not book.rules_ready:
            raise ApiError(
                409, "SCORE_RULES_PENDING", f"请先配置 {group.name} 的基础分和全部类别系数"
            )
        title = re.sub(r"[\\/*?:\[\]]", "_", group.name).strip("'")[:28] or "班级"
        sheet = workbook.create_sheet(title)
        sheet.append(["序号", "课程", "班级", "学号", "姓名", "平时分", "名单状态", "评价状态"])
        summaries = {s.enrollment_id: s for s in book.summaries}
        for index, student in enumerate(book.students, 1):
            summary = summaries[student.enrollment_id]
            values = [
                course.name,
                group.name,
                student.student_number,
                student.student_name,
                "已移除" if student.enrollment_status == "REMOVED" else "在班",
                STATUS_LABELS[summary.status],
            ]
            sheet.cell(index + 1, 1, index)
            for col, value in zip((2, 3, 4, 5, 7, 8), values, strict=True):
                cell = sheet.cell(index + 1, col, value)
                cell.data_type = "s"
            if summary.final_score is not None:
                cell = sheet.cell(index + 1, 6, float(summary.final_score))
                cell.number_format = "0.00"
        for cell in sheet[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor="E2E8F0")
        for col, width in enumerate((8, 28, 24, 20, 18, 14, 14, 18), 1):
            sheet.column_dimensions[get_column_letter(col)].width = width
        sheet.freeze_panes = "F2"
        sheet.auto_filter.ref = sheet.dimensions
    if len(workbook.worksheets) == 1:
        raise ApiError(409, "EXPORT_EMPTY", "所选课程或班级暂无学生成绩数据")
    workbook.remove(default_sheet)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    filename = _safe_filename_base(f"{course.name}_{course.term}_平时分")
    return ExportPayload(
        content=output.getvalue(),
        filename=f"{filename}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
