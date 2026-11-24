from collections.abc import Iterator
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from attendance_api.db import get_db
from attendance_api.models import User
from attendance_api.modules.auth.dependencies import require_password_changed, require_teacher
from attendance_api.modules.exports.course_service import generate_course_export
from attendance_api.modules.exports.scores_service import generate_scores_export
from attendance_api.modules.exports.service import generate_export
from attendance_api.modules.exports.template_service import generate_template_export

router = APIRouter(prefix="/api/v1", tags=["exports"])


@router.get(
    "/courses/{course_id}/scores-export",
    operation_id="exportCourseScores",
    response_class=StreamingResponse,
)
def export_course_scores(
    course_id: str,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    password_changed: Annotated[User, Depends(require_password_changed)],
    class_group_id: Annotated[str | None, Query()] = None,
) -> StreamingResponse:
    payload = generate_scores_export(
        db, teacher=teacher, course_id=course_id, class_group_id=class_group_id
    )
    disposition = f"attachment; filename*=UTF-8''{quote(payload.filename, safe='')}"
    return StreamingResponse(
        _stream(payload.content),
        media_type=payload.media_type,
        headers={"Content-Disposition": disposition, "X-Content-Type-Options": "nosniff"},
    )


def _stream(content: bytes) -> Iterator[bytes]:
    yield content


@router.get(
    "/attendance-sessions/{session_id}/export",
    operation_id="exportAttendanceSession",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "考勤导出文件",
            "content": {
                "text/csv": {"schema": {"type": "string", "format": "binary"}},
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
                    "schema": {"type": "string", "format": "binary"}
                },
            },
        }
    },
)
def export_attendance_session(
    session_id: str,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    password_changed: Annotated[User, Depends(require_password_changed)],
    format: Annotated[Literal["csv", "xlsx"], Query()],
) -> StreamingResponse:
    payload = generate_export(db, teacher=teacher, session_id=session_id, export_format=format)
    disposition = f"attachment; filename*=UTF-8''{quote(payload.filename, safe='')}"
    return StreamingResponse(
        _stream(payload.content),
        media_type=payload.media_type,
        headers={
            "Content-Disposition": disposition,
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/courses/{course_id}/attendance-export",
    operation_id="exportCourseAttendance",
    response_class=StreamingResponse,
)
def export_course_attendance(
    course_id: str,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    password_changed: Annotated[User, Depends(require_password_changed)],
    class_group_id: Annotated[str | None, Query()] = None,
) -> StreamingResponse:
    payload = generate_course_export(
        db, teacher=teacher, course_id=course_id, class_group_id=class_group_id
    )
    disposition = f"attachment; filename*=UTF-8''{quote(payload.filename, safe='')}"
    return StreamingResponse(
        _stream(payload.content),
        media_type=payload.media_type,
        headers={
            "Content-Disposition": disposition,
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/courses/{course_id}/attendance-template-export",
    operation_id="exportAttendanceTemplate",
    response_class=StreamingResponse,
)
def export_attendance_template(
    course_id: str,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    password_changed: Annotated[User, Depends(require_password_changed)],
    class_group_id: Annotated[str | None, Query()] = None,
) -> StreamingResponse:
    payload = generate_template_export(
        db, teacher=teacher, course_id=course_id, class_group_id=class_group_id
    )
    disposition = f"attachment; filename*=UTF-8''{quote(payload.filename, safe='')}"
    return StreamingResponse(
        _stream(payload.content),
        media_type=payload.media_type,
        headers={
            "Content-Disposition": disposition,
            "X-Content-Type-Options": "nosniff",
        },
    )
