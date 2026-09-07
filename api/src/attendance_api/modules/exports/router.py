from collections.abc import Iterator
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from attendance_api.db import get_db
from attendance_api.models import User
from attendance_api.modules.auth.dependencies import require_password_changed, require_teacher
from attendance_api.modules.exports.service import generate_export

router = APIRouter(prefix="/api/v1/attendance-sessions", tags=["exports"])


def _stream(content: bytes) -> Iterator[bytes]:
    yield content


@router.get(
    "/{session_id}/export",
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
