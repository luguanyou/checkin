from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from attendance_api.db import get_db
from attendance_api.models import Enrollment, Student, User
from attendance_api.modules.auth.dependencies import require_password_changed, require_teacher
from attendance_api.modules.rosters.service import (
    create_roster_member,
    get_roster,
    update_enrollment_status,
    update_roster_member,
)
from attendance_api.schemas.rosters import (
    CreateRosterMemberRequest,
    RosterListResponse,
    RosterMemberResponse,
    StudentResponse,
    UpdateEnrollmentStatusRequest,
)

router = APIRouter(prefix="/api/v1/classes", tags=["rosters"])
enrollments_router = APIRouter(prefix="/api/v1/enrollments", tags=["rosters"])


def roster_member_response(enrollment: Enrollment, student: Student) -> RosterMemberResponse:
    return RosterMemberResponse(
        enrollment_id=enrollment.id,
        enrollment_status=enrollment.status,
        student=StudentResponse.model_validate(student),
        created_at=enrollment.created_at,
        updated_at=enrollment.updated_at,
    )


@router.get(
    "/{class_group_id}/roster",
    response_model=RosterListResponse,
    operation_id="getClassRoster",
)
def class_roster(
    class_group_id: str,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    password_changed: Annotated[User, Depends(require_password_changed)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: Annotated[Literal["ACTIVE", "REMOVED", "all"], Query()] = "ACTIVE",
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> RosterListResponse:
    rows, total = get_roster(
        db,
        teacher_id=teacher.id,
        class_group_id=class_group_id,
        page=page,
        page_size=page_size,
        status=status,
        query=q,
    )
    return RosterListResponse(
        items=[roster_member_response(enrollment, student) for enrollment, student in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@enrollments_router.patch(
    "/{enrollment_id}/status",
    response_model=RosterMemberResponse,
    operation_id="updateEnrollmentStatus",
)
def change_enrollment_status(
    enrollment_id: str,
    payload: UpdateEnrollmentStatusRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    password_changed: Annotated[User, Depends(require_password_changed)],
) -> RosterMemberResponse:
    ip_address = request.client.host if request.client is not None else "unknown"
    enrollment, student = update_enrollment_status(
        db,
        teacher=teacher,
        enrollment_id=enrollment_id,
        status=payload.status,
        ip_address=ip_address,
        request_id=str(request.state.request_id),
    )
    return roster_member_response(enrollment, student)


@router.post(
    "/{class_group_id}/roster",
    response_model=RosterMemberResponse,
    status_code=201,
    operation_id="createRosterMember",
)
def add_roster_member(
    class_group_id: str,
    payload: CreateRosterMemberRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    password_changed: Annotated[User, Depends(require_password_changed)],
) -> RosterMemberResponse:
    enrollment, student = create_roster_member(
        db,
        teacher=teacher,
        class_group_id=class_group_id,
        payload=payload,
        ip_address=request.client.host if request.client else "unknown",
        request_id=str(request.state.request_id),
    )
    return roster_member_response(enrollment, student)


@router.put(
    "/{class_group_id}/roster/{enrollment_id}",
    response_model=RosterMemberResponse,
    operation_id="updateRosterMember",
)
def edit_roster_member(
    class_group_id: str,
    enrollment_id: str,
    payload: CreateRosterMemberRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    password_changed: Annotated[User, Depends(require_password_changed)],
) -> RosterMemberResponse:
    enrollment, student = update_roster_member(
        db,
        teacher=teacher,
        class_group_id=class_group_id,
        enrollment_id=enrollment_id,
        payload=payload,
        ip_address=request.client.host if request.client else "unknown",
        request_id=str(request.state.request_id),
    )
    return roster_member_response(enrollment, student)
