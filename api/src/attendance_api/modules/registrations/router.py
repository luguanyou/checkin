from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field
from sqlalchemy.orm import Session

from attendance_api.db import get_db
from attendance_api.models import User
from attendance_api.modules.auth.dependencies import get_current_user, require_password_changed
from attendance_api.modules.portal.router import no_cache
from attendance_api.modules.registrations import service
from attendance_api.schemas.common import ApiModel
from attendance_api.schemas.rosters import CreateRosterMemberRequest

router = APIRouter(
    prefix="/api/v1", tags=["student-registrations"], dependencies=[Depends(no_cache)]
)
DB = Annotated[Session, Depends(get_db)]
Actor = Annotated[User, Depends(get_current_user)]
Changed = Annotated[User, Depends(require_password_changed)]


class LookupRequest(CreateRosterMemberRequest):
    pass


class RegisterRequest(LookupRequest):
    class_id: str = Field(min_length=1, max_length=36)
    password: str = Field(min_length=12, max_length=128)


class ReviewRequest(ApiModel):
    registration_ids: list[str] = Field(min_length=1, max_length=100)
    decision: Literal["APPROVED", "REJECTED"]
    reason: str | None = Field(default=None, max_length=500)


@router.post("/auth/student-registration/classes")
def lookup(payload: LookupRequest, db: DB) -> dict[str, Any]:
    student = service.find_student(db, payload.student_number, payload.name)
    return {"items": service.eligible_classes(db, student.id)}


@router.post("/auth/student-register", status_code=201)
def register(payload: RegisterRequest, db: DB) -> dict[str, str]:
    return service.submit(
        db,
        number=payload.student_number,
        name=payload.name,
        class_id=payload.class_id,
        password=payload.password,
    )


@router.get("/classes/{class_id}/registrations")
def applications(
    class_id: str,
    db: DB,
    actor: Actor,
    changed: Changed,
    status: Annotated[Literal["PENDING", "APPROVED", "REJECTED", "all"], Query()] = "PENDING",
) -> dict[str, Any]:
    return {"items": service.list_applications(db, actor=actor, class_id=class_id, status=status)}


@router.post("/classes/{class_id}/registrations/review")
def decide(
    class_id: str, payload: ReviewRequest, request: Request, db: DB, actor: Actor, changed: Changed
) -> dict[str, int]:
    return {
        "reviewed": service.review(
            db,
            actor=actor,
            class_id=class_id,
            ids=payload.registration_ids,
            decision=payload.decision,
            reason=payload.reason,
            ip=request.client.host if request.client else "unknown",
            request_id=str(request.state.request_id),
        )
    }
