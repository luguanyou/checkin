from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from attendance_api.db import get_db
from attendance_api.errors import ApiError
from attendance_api.models import StudentRegistration, User
from attendance_api.modules.audit.service import append_audit
from attendance_api.modules.auth.dependencies import (
    get_current_user,
    require_password_changed,
    require_teacher,
)
from attendance_api.modules.courses.service import get_owned_class_group
from attendance_api.modules.portal.service import (
    owned_student,
    student_class_data,
    student_classes,
    visibility,
)
from attendance_api.schemas.common import ApiModel
from attendance_api.security.passwords import hash_password


def no_cache(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(prefix="/api/v1", tags=["student-portal"], dependencies=[Depends(no_cache)])
DB = Annotated[Session, Depends(get_db)]
Teacher = Annotated[User, Depends(require_teacher)]
Changed = Annotated[User, Depends(require_password_changed)]


class VisibilityRequest(ApiModel):
    attendance_visible: bool
    score_visibility: Literal["HIDDEN", "TOTAL", "DETAILS"]


class AccountRequest(ApiModel):
    temporary_password: str = Field(min_length=12, max_length=128)


def require_student(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "STUDENT" or not user.student_id:
        raise ApiError(403, "RESOURCE_FORBIDDEN", "仅学生账号可访问")
    return user


def audit(
    db: Session,
    teacher: User,
    request: Request,
    action: str,
    entity_type: str,
    entity_id: str,
    before: Any,
    after: Any,
) -> None:
    append_audit(
        db,
        actor_user_id=teacher.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_value=before,
        after_value=after,
        reason=None,
        ip_address=request.client.host if request.client else "unknown",
        request_id=str(request.state.request_id),
    )


@router.get("/classes/{class_id}/student-visibility")
def get_visibility(class_id: str, db: DB, teacher: Teacher, changed: Changed) -> dict[str, Any]:
    group, _ = get_owned_class_group(db, teacher_id=teacher.id, class_group_id=class_id)
    return visibility(group)


@router.put("/classes/{class_id}/student-visibility")
def set_visibility(
    class_id: str,
    payload: VisibilityRequest,
    request: Request,
    db: DB,
    teacher: Teacher,
    changed: Changed,
) -> dict[str, Any]:
    group, _ = get_owned_class_group(db, teacher_id=teacher.id, class_group_id=class_id)
    before = visibility(group)
    group.attendance_visible = payload.attendance_visible
    group.score_visibility = payload.score_visibility
    audit(
        db,
        teacher,
        request,
        "STUDENT_VISIBILITY_CHANGED",
        "class_group",
        group.id,
        before,
        visibility(group),
    )
    db.commit()
    return visibility(group)


@router.post("/classes/{class_id}/students/{student_id}/account", status_code=201)
def create_account(
    class_id: str,
    student_id: str,
    payload: AccountRequest,
    request: Request,
    db: DB,
    teacher: Teacher,
    changed: Changed,
) -> dict[str, str]:
    student = owned_student(db, teacher=teacher, class_id=class_id, student_id=student_id)
    if db.scalar(
        select(StudentRegistration.id).where(
            StudentRegistration.student_id == student.id, StudentRegistration.status == "PENDING"
        )
    ):
        raise ApiError(409, "REGISTRATION_PENDING", "该学生已有注册申请，请在学生注册审核中处理")
    if db.scalar(select(User.id).where(User.student_id == student.id)):
        raise ApiError(
            409, "DUPLICATE_RESOURCE", "该学生已有账号，无需重复开通；忘记密码请联系管理员"
        )
    account = User(
        username=student.student_number.strip().lower(),
        display_name=student.name,
        student_id=student.id,
        password_hash=hash_password(payload.temporary_password),
        role="STUDENT",
        status="ACTIVE",
        must_change_password=True,
    )
    db.add(account)
    try:
        db.flush()
        audit(
            db,
            teacher,
            request,
            "STUDENT_ACCOUNT_CREATED",
            "user",
            account.id,
            None,
            {"student_id": student.id, "username": account.username},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "DUPLICATE_RESOURCE", "账号或学号已被使用，请联系管理员") from None
    return {"username": account.username}


@router.get("/student/classes")
def list_student_classes(
    db: DB, user: Annotated[User, Depends(require_student)], changed: Changed
) -> dict[str, Any]:
    return {"items": student_classes(db, user)}


@router.get("/student/classes/{class_id}")
def get_student_class(
    class_id: str, db: DB, user: Annotated[User, Depends(require_student)], changed: Changed
) -> dict[str, Any]:
    return student_class_data(db, user=user, class_id=class_id)
