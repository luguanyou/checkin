from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from attendance_api.db import get_db
from attendance_api.errors import ApiError
from attendance_api.models import AttendanceRecord, AttendanceSession, ClassGroup, Course, User
from attendance_api.modules.attendance import service
from attendance_api.modules.auth.dependencies import require_password_changed, require_teacher
from attendance_api.schemas.attendance import (
    AttendanceRecordResponse,
    AttendanceSessionBase,
    AttendanceSessionListResponse,
    AttendanceSessionResponse,
    AttendanceSummary,
    CourseSummary,
    CreateAttendanceSessionRequest,
    ModifierSummary,
    ResourceSummary,
    UpdateAttendanceRecordRequest,
)

classes_router = APIRouter(prefix="/api/v1/classes", tags=["attendance"])
router = APIRouter(prefix="/api/v1/attendance-sessions", tags=["attendance"])
records_router = APIRouter(prefix="/api/v1/attendance-records", tags=["attendance"])


def _record_response(record: AttendanceRecord, modifier: User) -> AttendanceRecordResponse:
    return AttendanceRecordResponse(
        id=record.id,
        student_id=record.student_id,
        student_number=record.student_number_snapshot,
        student_name=record.student_name_snapshot,
        class_name=record.class_name_snapshot,
        status=record.status,
        marked_at=record.marked_at,
        last_modified_at=record.last_modified_at,
        last_modified_by=ModifierSummary(id=modifier.id, display_name=modifier.display_name),
        version=record.version,
    )


def _session_base(
    attendance_session: AttendanceSession,
    class_group: ClassGroup,
    course: Course,
    records: list[tuple[AttendanceRecord, User]],
) -> AttendanceSessionBase:
    return AttendanceSessionBase(
        id=attendance_session.id,
        course=CourseSummary(id=course.id, name=course.name, code=course.code),
        class_group=ResourceSummary(id=class_group.id, name=class_group.name),
        session_date=attendance_session.session_date,
        status=attendance_session.status,
        started_at=attendance_session.started_at,
        completed_at=attendance_session.completed_at,
        summary=AttendanceSummary.model_validate(
            service.attendance_summary([record for record, _modifier in records])
        ),
        created_at=attendance_session.created_at,
        updated_at=attendance_session.updated_at,
    )


def session_response(
    attendance_session: AttendanceSession,
    class_group: ClassGroup,
    course: Course,
    records: list[tuple[AttendanceRecord, User]],
) -> AttendanceSessionResponse:
    base = _session_base(attendance_session, class_group, course, records)
    return AttendanceSessionResponse(
        **base.model_dump(),
        records=[_record_response(record, modifier) for record, modifier in records],
    )


@classes_router.post(
    "/{class_group_id}/attendance-sessions",
    response_model=AttendanceSessionResponse,
    status_code=201,
    operation_id="createAttendanceSession",
)
def create_attendance_session(
    class_group_id: str,
    payload: CreateAttendanceSessionRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    password_changed: Annotated[User, Depends(require_password_changed)],
) -> AttendanceSessionResponse:
    ip_address = request.client.host if request.client is not None else "unknown"
    attendance_session, class_group, course = service.create_attendance_session(
        db,
        teacher=teacher,
        class_group_id=class_group_id,
        session_date=payload.session_date,
        ip_address=ip_address,
        request_id=str(request.state.request_id),
    )
    records = service.session_records(db, attendance_session.id)
    return session_response(attendance_session, class_group, course, records)


@router.get("", response_model=AttendanceSessionListResponse, operation_id="listAttendanceSessions")
def list_attendance_sessions(
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    password_changed: Annotated[User, Depends(require_password_changed)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    course_id: str | None = None,
    class_group_id: str | None = None,
    status: Literal["DRAFT", "COMPLETED"] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> AttendanceSessionListResponse:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise ApiError(400, "INVALID_REQUEST", "起始日期不能晚于结束日期")
    rows, total = service.list_attendance_sessions(
        db,
        teacher_id=teacher.id,
        page=page,
        page_size=page_size,
        course_id=course_id,
        class_group_id=class_group_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )
    items = [
        _session_base(item, class_group, course, service.session_records(db, item.id))
        for item, class_group, course in rows
    ]
    return AttendanceSessionListResponse(items=items, page=page, page_size=page_size, total=total)


@router.get(
    "/{session_id}", response_model=AttendanceSessionResponse, operation_id="getAttendanceSession"
)
def get_attendance_session(
    session_id: str,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    password_changed: Annotated[User, Depends(require_password_changed)],
) -> AttendanceSessionResponse:
    attendance_session, class_group, course = service.get_owned_session(
        db, teacher_id=teacher.id, session_id=session_id
    )
    return session_response(
        attendance_session,
        class_group,
        course,
        service.session_records(db, attendance_session.id),
    )


@records_router.patch(
    "/{record_id}",
    response_model=AttendanceRecordResponse,
    operation_id="updateAttendanceRecord",
)
def update_attendance_record(
    record_id: str,
    payload: UpdateAttendanceRecordRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    password_changed: Annotated[User, Depends(require_password_changed)],
) -> AttendanceRecordResponse:
    ip_address = request.client.host if request.client is not None else "unknown"
    result = service.update_attendance_record(
        db,
        teacher=teacher,
        record_id=record_id,
        status=payload.status,
        expected_version=payload.expected_version,
        client_mutation_id=str(payload.client_mutation_id),
        reason=payload.reason,
        ip_address=ip_address,
        request_id=str(request.state.request_id),
    )
    return AttendanceRecordResponse.model_validate(result)


@router.post(
    "/{session_id}/complete",
    response_model=AttendanceSessionBase,
    operation_id="completeAttendanceSession",
)
def complete_attendance_session(
    session_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    password_changed: Annotated[User, Depends(require_password_changed)],
) -> AttendanceSessionBase:
    ip_address = request.client.host if request.client is not None else "unknown"
    attendance_session, class_group, course = service.complete_attendance_session(
        db,
        teacher=teacher,
        session_id=session_id,
        ip_address=ip_address,
        request_id=str(request.state.request_id),
    )
    records = service.session_records(db, attendance_session.id)
    return _session_base(attendance_session, class_group, course, records)
