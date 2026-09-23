import csv
from io import BytesIO, StringIO

from openpyxl import Workbook

from attendance_api.errors import ApiError
from attendance_api.modules.exports.service import ExportPayload, _safe_filename_base
from attendance_api.schemas.scores import CATEGORIES, ScoreBook

CATEGORY_LABELS = {
    "HOMEWORK": "作业",
    "CLASSROOM": "课堂表现",
    "LAB": "上机实验表现",
    "OTHER": "其他",
}
STATUS_LABELS = {"READY": "已完成", "RULES_PENDING": "规则待配置", "RECORDS_PENDING": "待评完整"}


def _safe_text(value: str) -> str:
    # Leading whitespace/control characters can be ignored by spreadsheet importers.
    return "'" + value if value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")) else value


def generate_export(book: ScoreBook, *, export_format: str, kind: str) -> ExportPayload:
    if kind == "summary" and not book.rules_ready:
        raise ApiError(409, "SCORE_RULES_PENDING", "请先配置基础分和全部类别系数，或导出原始明细")
    rows: list[list[str]] = []
    common = ["课程", "班级", "学号", "姓名", "名单状态"]
    if kind == "summary":
        columns = (
            common
            + ["基础分"]
            + [
                f"{CATEGORY_LABELS[category]}{label}"
                for category in CATEGORIES
                for label in ("净积分", "系数", "贡献", "待评项目")
            ]
            + ["原始总分", "平时成绩", "状态"]
        )
        summaries = {summary.enrollment_id: summary for summary in book.summaries}
        for student in book.students:
            summary = summaries[student.enrollment_id]
            row = [
                book.course.name,
                book.class_group.name,
                student.student_number,
                student.student_name,
                "在班" if student.enrollment_status == "ACTIVE" else "已移除",
                format(book.settings.base_score, "f")
                if book.settings.base_score is not None
                else "",
            ]
            for category in summary.categories:
                factor = book.settings.factors[category.category]
                row.extend(
                    [
                        category.points,
                        format(factor, "f") if factor is not None else "",
                        category.contribution or "",
                        str(category.pending),
                    ]
                )
            row.extend(
                [summary.raw_score or "", summary.final_score or "", STATUS_LABELS[summary.status]]
            )
            rows.append(row)
        suffix = "平时成绩汇总"
    else:
        columns = common + ["类别", "项目", "日期", "积分", "备注", "评价状态"]
        records = {(record.enrollment_id, record.item_id): record for record in book.records}
        for student in book.students:
            for item in book.items:
                record = records.get((student.enrollment_id, item.id))
                if student.enrollment_status == "REMOVED" and record is None:
                    continue
                points = record.points if record else None
                rows.append(
                    [
                        book.course.name,
                        book.class_group.name,
                        student.student_number,
                        student.student_name,
                        "在班" if student.enrollment_status == "ACTIVE" else "已移除",
                        CATEGORY_LABELS[item.category],
                        item.name,
                        item.occurred_on.isoformat(),
                        format(points, "f") if points is not None else "",
                        record.note if record else "",
                        "已评价" if points is not None else "尚未评价",
                    ]
                )
        suffix = "平时成绩原始明细"
    filename = _safe_filename_base(f"{book.course.name}_{book.class_group.name}_{suffix}")
    if export_format == "csv":
        output = StringIO(newline="")
        writer = csv.writer(output, lineterminator="\r\n")
        writer.writerow(columns)
        writer.writerows([[_safe_text(value) for value in row] for row in rows])
        return ExportPayload(
            content=("\ufeff" + output.getvalue()).encode("utf-8"),
            media_type="text/csv",
            filename=f"{filename}.csv",
        )
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "平时成绩"
    sheet.freeze_panes = "F2"
    for row_index, row in enumerate([columns, *rows], start=1):
        for column_index, value in enumerate(row, start=1):
            cell = sheet.cell(row=row_index, column=column_index, value=value)
            cell.data_type = "s"
    binary = BytesIO()
    workbook.save(binary)
    workbook.close()
    return ExportPayload(
        content=binary.getvalue(),
        filename=f"{filename}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
