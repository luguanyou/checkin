from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import Field
from sqlalchemy.orm import Session

from attendance_api.db import get_db
from attendance_api.models import User
from attendance_api.modules.auth.dependencies import require_password_changed, require_teacher
from attendance_api.modules.monitors import service
from attendance_api.modules.portal.router import audit, no_cache, require_student
from attendance_api.schemas.common import ApiModel
from attendance_api.schemas.scores import SetScoreRecordsRequest

router = APIRouter(
    prefix="/api/v1",
    tags=["monitors"],
    dependencies=[Depends(require_password_changed), Depends(no_cache)],
)
DB = Annotated[Session, Depends(get_db)]
Teacher = Annotated[User, Depends(require_teacher)]
StudentUser = Annotated[User, Depends(require_student)]


class GrantRequest(ApiModel):
    item_ids: list[str] = Field(max_length=1000)
    can_review_registrations: bool = False


@router.get("/classes/{class_id}/monitors")
def manage(class_id: str, db: DB, teacher: Teacher) -> dict[str, Any]:
    return service.manage_data(db, teacher=teacher, class_id=class_id)


@router.put("/classes/{class_id}/monitors/{user_id}")
def grant(
    class_id: str, user_id: str, payload: GrantRequest, request: Request, db: DB, teacher: Teacher
) -> dict[str, Any]:
    before, after, before_review = service.replace_grants(
        db,
        teacher=teacher,
        class_id=class_id,
        user_id=user_id,
        item_ids=payload.item_ids,
        can_review_registrations=payload.can_review_registrations,
    )
    audit(
        db,
        teacher,
        request,
        "MONITOR_GRANTS_CHANGED",
        "class_group",
        class_id,
        {"user_id": user_id, "item_ids": before, "can_review_registrations": before_review},
        {
            "user_id": user_id,
            "item_ids": after,
            "can_review_registrations": payload.can_review_registrations,
        },
    )
    db.commit()
    return service.manage_data(db, teacher=teacher, class_id=class_id)


@router.get("/student/monitor-projects")
def projects(db: DB, user: StudentUser) -> dict[str, Any]:
    return {"items": service.project_list(db, user)}


@router.get("/student/classes/{class_id}/monitor-projects/{item_id}")
def project(class_id: str, item_id: str, db: DB, user: StudentUser) -> dict[str, Any]:
    return service.monitor_project(db, user=user, class_id=class_id, item_id=item_id)


@router.put("/student/classes/{class_id}/monitor-projects/{item_id}/records")
def save(
    class_id: str,
    item_id: str,
    payload: SetScoreRecordsRequest,
    request: Request,
    db: DB,
    user: StudentUser,
) -> dict[str, Any]:
    return service.save_project(
        db,
        user=user,
        class_id=class_id,
        item_id=item_id,
        payload=payload,
        ip_address=request.client.host if request.client else "unknown",
        request_id=str(request.state.request_id),
    )
