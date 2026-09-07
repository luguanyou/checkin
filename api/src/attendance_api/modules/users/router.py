from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from attendance_api.db import get_db
from attendance_api.models import User
from attendance_api.modules.auth.dependencies import require_admin, require_password_changed
from attendance_api.modules.users.service import create_teacher as create_teacher_service
from attendance_api.modules.users.service import list_users as list_users_service
from attendance_api.modules.users.service import reset_user_password, update_user_status
from attendance_api.schemas.auth import UserResponse
from attendance_api.schemas.users import (
    CreateTeacherRequest,
    ResetUserPasswordRequest,
    UpdateUserStatusRequest,
    UserListResponse,
)

router = APIRouter(prefix="/api/v1/admin/users", tags=["admin-users"])


def _request_context(request: Request) -> tuple[str, str]:
    ip_address = request.client.host if request.client is not None else "unknown"
    return ip_address, str(request.state.request_id)


@router.get("", response_model=UserListResponse, operation_id="listUsers")
def list_users(
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
    password_changed: Annotated[User, Depends(require_password_changed)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    role: Annotated[Literal["ADMIN", "TEACHER"] | None, Query()] = None,
    status: Annotated[Literal["ACTIVE", "DISABLED"] | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> UserListResponse:
    users, total = list_users_service(
        db, page=page, page_size=page_size, role=role, status=status, query=q
    )
    return UserListResponse(
        items=[UserResponse.model_validate(user) for user in users],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("", response_model=UserResponse, status_code=201, operation_id="createTeacher")
def create_teacher(
    payload: CreateTeacherRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
    password_changed: Annotated[User, Depends(require_password_changed)],
) -> UserResponse:
    ip_address, request_id = _request_context(request)
    user = create_teacher_service(
        db,
        actor=admin,
        username=payload.username,
        display_name=payload.display_name,
        temporary_password=payload.temporary_password,
        ip_address=ip_address,
        request_id=request_id,
    )
    return UserResponse.model_validate(user)


@router.patch("/{user_id}/status", response_model=UserResponse, operation_id="updateUserStatus")
def change_user_status(
    user_id: str,
    payload: UpdateUserStatusRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
    password_changed: Annotated[User, Depends(require_password_changed)],
) -> UserResponse:
    ip_address, request_id = _request_context(request)
    user = update_user_status(
        db,
        actor=admin,
        user_id=user_id,
        status=payload.status,
        ip_address=ip_address,
        request_id=request_id,
    )
    return UserResponse.model_validate(user)


@router.post("/{user_id}/reset-password", status_code=204, operation_id="resetUserPassword")
def reset_password(
    user_id: str,
    payload: ResetUserPasswordRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
    password_changed: Annotated[User, Depends(require_password_changed)],
) -> Response:
    ip_address, request_id = _request_context(request)
    reset_user_password(
        db,
        actor=admin,
        user_id=user_id,
        temporary_password=payload.temporary_password,
        ip_address=ip_address,
        request_id=request_id,
    )
    return Response(status_code=204)
