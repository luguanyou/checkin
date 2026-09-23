from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from attendance_api.db import get_db
from attendance_api.models import User
from attendance_api.modules.auth.dependencies import require_password_changed, require_teacher
from attendance_api.modules.courses.router import _request_context
from attendance_api.modules.scores import service
from attendance_api.modules.scores.export import generate_export
from attendance_api.schemas.scores import (
    CreateScoreItemRequest,
    ScoreBook,
    ScoreHistoryResponse,
    SetScoreRecordsRequest,
    SetScoreSettingsRequest,
    UpdateScoreItemRequest,
)

router = APIRouter(
    prefix="/api/v1/classes/{class_group_id}/scores",
    tags=["scores"],
    dependencies=[Depends(require_password_changed)],
)
Database = Annotated[Session, Depends(get_db)]
Teacher = Annotated[User, Depends(require_teacher)]


@router.get("", response_model=ScoreBook, operation_id="getScoreBook")
def get_score_book(class_group_id: str, db: Database, teacher: Teacher) -> ScoreBook:
    return service.get_book(db, teacher_id=teacher.id, class_group_id=class_group_id)


def _mutate(
    class_group_id: str,
    payload: service.ScoreMutation,
    request: Request,
    db: Session,
    teacher: User,
    item_id: str | None = None,
) -> ScoreBook:
    ip_address, request_id = _request_context(request)
    return service.mutate_book(
        db,
        teacher=teacher,
        class_group_id=class_group_id,
        payload=payload,
        ip_address=ip_address,
        request_id=request_id,
        item_id=item_id,
    )


@router.put("/settings", response_model=ScoreBook, operation_id="setScoreSettings")
def set_score_settings(
    class_group_id: str,
    payload: SetScoreSettingsRequest,
    request: Request,
    db: Database,
    teacher: Teacher,
) -> ScoreBook:
    return _mutate(class_group_id, payload, request, db, teacher)


@router.post("/items", response_model=ScoreBook, status_code=201, operation_id="createScoreItem")
def create_score_item(
    class_group_id: str,
    payload: CreateScoreItemRequest,
    request: Request,
    db: Database,
    teacher: Teacher,
) -> ScoreBook:
    return _mutate(class_group_id, payload, request, db, teacher)


@router.patch("/items/{item_id}", response_model=ScoreBook, operation_id="updateScoreItem")
def update_score_item(
    class_group_id: str,
    item_id: str,
    payload: UpdateScoreItemRequest,
    request: Request,
    db: Database,
    teacher: Teacher,
) -> ScoreBook:
    return _mutate(class_group_id, payload, request, db, teacher, item_id)


@router.put("/items/{item_id}/records", response_model=ScoreBook, operation_id="setScoreRecords")
def set_score_records(
    class_group_id: str,
    item_id: str,
    payload: SetScoreRecordsRequest,
    request: Request,
    db: Database,
    teacher: Teacher,
) -> ScoreBook:
    return _mutate(class_group_id, payload, request, db, teacher, item_id)


@router.get("/history", response_model=ScoreHistoryResponse, operation_id="getScoreHistory")
def get_score_history(
    class_group_id: str,
    db: Database,
    teacher: Teacher,
    enrollment_id: Annotated[str | None, Query(max_length=36)] = None,
) -> ScoreHistoryResponse:
    return service.get_history(
        db, teacher_id=teacher.id, class_group_id=class_group_id, enrollment_id=enrollment_id
    )


@router.get(
    "/export",
    operation_id="exportScores",
    response_class=Response,
    responses={
        200: {
            "description": "平时成绩导出文件",
            "content": {
                "text/csv": {"schema": {"type": "string", "format": "binary"}},
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
                    "schema": {"type": "string", "format": "binary"},
                },
            },
        },
    },
)
def export_scores(
    class_group_id: str,
    db: Database,
    teacher: Teacher,
    format: Annotated[Literal["csv", "xlsx"], Query()],
    kind: Annotated[Literal["summary", "details"], Query()] = "summary",
) -> Response:
    book = service.get_book(db, teacher_id=teacher.id, class_group_id=class_group_id)
    payload = generate_export(book, export_format=format, kind=kind)
    disposition = f"attachment; filename*=UTF-8''{quote(payload.filename, safe='')}"
    return Response(
        payload.content,
        media_type=payload.media_type,
        headers={
            "Content-Disposition": disposition,
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )
