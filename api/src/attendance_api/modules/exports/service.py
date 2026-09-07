import csv
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO, StringIO

from openpyxl import Workbook
from sqlalchemy.orm import Session

from attendance_api.errors import ApiError
from attendance_api.models import User
from attendance_api.modules.attendance.service import get_owned_session, session_records

EXPORT_COLUMNS = [
    "课程",
    "课程代码",
    "班级",
    "日期",
    "姓名",
    "学号",
    "考勤状态",
    "点名时间",
    "最后修改时间",
    "最后修改人",
]
FORMULA_PREFIXES = ("=", "+", "-", "@")
FORBIDDEN_FILENAME = re.compile(r"[<>:\"/\\|?*\x00-\x1f]")
REPEATED_UNDERSCORE = re.compile(r"_+")


@dataclass(frozen=True)
class ExportPayload:
    content: bytes
    media_type: str
    filename: str


def _timestamp(value: datetime | None) -> str:
    if value is None:
        return ""
    aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return aware.isoformat().replace("+00:00", "Z")


def _safe_csv_text(value: str) -> str:
    return f"'{value}" if value.startswith(FORMULA_PREFIXES) else value


def _safe_filename_base(value: str) -> str:
    sanitized = FORBIDDEN_FILENAME.sub("_", value)
    sanitized = REPEATED_UNDERSCORE.sub("_", sanitized).strip(" ._")
    return (sanitized or "attendance")[:180]


def _export_rows(db: Session, teacher: User, session_id: str) -> tuple[list[list[str]], str]:
    attendance_session, _class_group, course = get_owned_session(
        db, teacher_id=teacher.id, session_id=session_id
    )
    if attendance_session.status != "COMPLETED":
        raise ApiError(409, "ATTENDANCE_SESSION_NOT_COMPLETED", "只能导出已完成的考勤场次")
    records = session_records(db, attendance_session.id)
    rows = [
        [
            course.name,
            course.code,
            record.class_name_snapshot,
            attendance_session.session_date.isoformat(),
            record.student_name_snapshot,
            record.student_number_snapshot,
            record.status,
            _timestamp(record.marked_at),
            _timestamp(record.last_modified_at),
            modifier.display_name,
        ]
        for record, modifier in records
    ]
    class_name = records[0][0].class_name_snapshot if records else _class_group.name
    filename_base = _safe_filename_base(
        f"{course.name}_{class_name}_{attendance_session.session_date.isoformat()}_单次考勤"
    )
    return rows, filename_base


def _csv_content(rows: list[list[str]]) -> bytes:
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(EXPORT_COLUMNS)
    writer.writerows([[_safe_csv_text(value) for value in row] for row in rows])
    return ("\ufeff" + output.getvalue()).encode("utf-8")


def _xlsx_content(rows: list[list[str]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    if sheet is None:
        raise RuntimeError("workbook has no active sheet")
    for row_index, row in enumerate([EXPORT_COLUMNS, *rows], start=1):
        for column_index, value in enumerate(row, start=1):
            cell = sheet.cell(row=row_index, column=column_index, value=str(value))
            cell.data_type = "s"
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def generate_export(
    db: Session, *, teacher: User, session_id: str, export_format: str
) -> ExportPayload:
    rows, filename_base = _export_rows(db, teacher, session_id)
    if export_format == "csv":
        return ExportPayload(
            content=_csv_content(rows),
            media_type="text/csv",
            filename=f"{filename_base}.csv",
        )
    return ExportPayload(
        content=_xlsx_content(rows),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"{filename_base}.xlsx",
    )
