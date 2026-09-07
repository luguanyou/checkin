from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from attendance_api.db import get_db
from attendance_api.models import ClassGroup, Course, User
from attendance_api.modules.auth.dependencies import require_password_changed, require_teacher
from attendance_api.modules.courses import service
from attendance_api.schemas.courses import (
    ClassGroupResponse,
    CourseListResponse,
    CourseResponse,
    CreateClassGroupRequest,
    CreateCourseRequest,
    UpdateClassGroupRequest,
    UpdateCourseRequest,
)

router = APIRouter(prefix="/api/v1/courses", tags=["courses"])
classes_router = APIRouter(prefix="/api/v1/classes", tags=["classes"])


def _request_context(request: Request) -> tuple[str, str]:
    ip_address = request.client.host if request.client is not None else "unknown"
    return ip_address, str(request.state.request_id)


def _class_response(item: tuple[ClassGroup, int]) -> ClassGroupResponse:
    class_group, active_count = item
    return ClassGroupResponse(
        id=class_group.id,
        name=class_group.name,
        status=class_group.status,
        active_student_count=active_count,
    )


def _course_response(course: Course, class_groups: list[tuple[ClassGroup, int]]) -> CourseResponse:
    return CourseResponse(
        id=course.id,
        name=course.name,
        code=course.code,
        term=course.term,
        status=course.status,
        classes=[_class_response(item) for item in class_groups],
        created_at=course.created_at,
        updated_at=course.updated_at,
    )


@router.get("", response_model=CourseListResponse, operation_id="listCourses")
def list_courses(
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    password_changed: Annotated[User, Depends(require_password_changed)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: Annotated[Literal["ACTIVE", "ARCHIVED"] | None, Query()] = None,
    term: Annotated[str | None, Query(max_length=50)] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> CourseListResponse:
    courses, total, summaries = service.list_courses(
        db,
        teacher_id=teacher.id,
        page=page,
        page_size=page_size,
        status=status,
        term=term,
        query=q,
    )
    return CourseListResponse(
        items=[_course_response(course, summaries.get(course.id, [])) for course in courses],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("", response_model=CourseResponse, status_code=201, operation_id="createCourse")
def create_course(
    payload: CreateCourseRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    password_changed: Annotated[User, Depends(require_password_changed)],
) -> CourseResponse:
    ip_address, request_id = _request_context(request)
    course = service.create_course(
        db,
        teacher=teacher,
        name=payload.name,
        code=payload.code,
        term=payload.term,
        ip_address=ip_address,
        request_id=request_id,
    )
    return _course_response(course, [])


@router.patch("/{course_id}", response_model=CourseResponse, operation_id="updateCourse")
def update_course(
    course_id: str,
    payload: UpdateCourseRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    password_changed: Annotated[User, Depends(require_password_changed)],
) -> CourseResponse:
    ip_address, request_id = _request_context(request)
    course = service.update_course(
        db,
        teacher=teacher,
        course_id=course_id,
        changes=payload.model_dump(exclude_unset=True),
        ip_address=ip_address,
        request_id=request_id,
    )
    _, _, summaries = service.list_courses(
        db,
        teacher_id=teacher.id,
        page=1,
        page_size=100,
        status=None,
        term=None,
        query=None,
    )
    return _course_response(course, summaries.get(course.id, []))


@router.delete("/{course_id}", status_code=204, operation_id="deleteCourse")
def delete_course(
    course_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    password_changed: Annotated[User, Depends(require_password_changed)],
) -> None:
    ip_address, request_id = _request_context(request)
    service.delete_course(
        db,
        teacher=teacher,
        course_id=course_id,
        ip_address=ip_address,
        request_id=request_id,
    )


@router.post(
    "/{course_id}/classes",
    response_model=ClassGroupResponse,
    status_code=201,
    operation_id="createClassGroup",
)
def create_class_group(
    course_id: str,
    payload: CreateClassGroupRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    password_changed: Annotated[User, Depends(require_password_changed)],
) -> ClassGroupResponse:
    ip_address, request_id = _request_context(request)
    class_group = service.create_class_group(
        db,
        teacher=teacher,
        course_id=course_id,
        name=payload.name,
        ip_address=ip_address,
        request_id=request_id,
    )
    return _class_response((class_group, 0))


@classes_router.patch(
    "/{class_group_id}",
    response_model=ClassGroupResponse,
    operation_id="updateClassGroup",
)
def update_class_group(
    class_group_id: str,
    payload: UpdateClassGroupRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    password_changed: Annotated[User, Depends(require_password_changed)],
) -> ClassGroupResponse:
    ip_address, request_id = _request_context(request)
    class_group = service.update_class_group(
        db,
        teacher=teacher,
        class_group_id=class_group_id,
        changes=payload.model_dump(exclude_unset=True),
        ip_address=ip_address,
        request_id=request_id,
    )
    return _class_response(service.class_summary(db, class_group))


@classes_router.delete("/{class_group_id}", status_code=204, operation_id="deleteClassGroup")
def delete_class_group(
    class_group_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    password_changed: Annotated[User, Depends(require_password_changed)],
) -> None:
    ip_address, request_id = _request_context(request)
    service.delete_class_group(
        db,
        teacher=teacher,
        class_group_id=class_group_id,
        ip_address=ip_address,
        request_id=request_id,
    )
