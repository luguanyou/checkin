from datetime import UTC, date, datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from attendance_api.errors import ApiError
from attendance_api.models import (
    AttendanceRecord,
    AttendanceSession,
    AuditLog,
    ClassGroup,
    Course,
    Enrollment,
    Student,
    User,
)
from attendance_api.models.base import utc_now
from attendance_api.modules.audit.service import append_audit
from attendance_api.modules.courses.service import get_owned_class_group

STATUS_VALUES = ("pending", "present", "absent", "leave", "late")


def attendance_summary(records: list[AttendanceRecord]) -> dict[str, int]:
    counts = {status: 0 for status in STATUS_VALUES}
    for record in records:
        counts[record.status] += 1
    return {
        "total": len(records),
        **counts,
        "exceptions": counts["absent"] + counts["leave"] + counts["late"],
    }


def get_owned_session(
    db: Session, *, teacher_id: str, session_id: str
) -> tuple[AttendanceSession, ClassGroup, Course]:
    row = db.execute(
        select(AttendanceSession, ClassGroup, Course)
        .join(ClassGroup, ClassGroup.id == AttendanceSession.class_group_id)
        .join(Course, Course.id == ClassGroup.course_id)
        .where(
            AttendanceSession.id == session_id,
            Course.owner_teacher_id == teacher_id,
        )
    ).one_or_none()
    if row is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "考勤场次不存在")
    return row[0], row[1], row[2]


def create_attendance_session(
    db: Session,
    *,
    teacher: User,
    class_group_id: str,
    session_date: date,
    ip_address: str,
    request_id: str,
) -> tuple[AttendanceSession, ClassGroup, Course]:
    class_group, course = get_owned_class_group(
        db, teacher_id=teacher.id, class_group_id=class_group_id
    )
    if class_group.status != "ACTIVE" or course.status != "ACTIVE":
        raise ApiError(409, "RESOURCE_STATE_CONFLICT", "已归档课程或班级不能创建考勤")
    roster = list(
        db.execute(
            select(Enrollment, Student)
            .join(Student, Student.id == Enrollment.student_id)
            .where(
                Enrollment.class_group_id == class_group_id,
                Enrollment.status == "ACTIVE",
            )
            .order_by(Student.student_number, Student.id)
        ).tuples()
    )
    if not roster:
        raise ApiError(409, "ROSTER_EMPTY", "当前班级没有有效名单成员")

    now = utc_now()
    attendance_session = AttendanceSession(
        class_group_id=class_group_id,
        session_date=session_date,
        status="DRAFT",
        started_at=now,
        created_by=teacher.id,
    )
    db.add(attendance_session)
    db.flush()
    for _enrollment, student in roster:
        db.add(
            AttendanceRecord(
                session_id=attendance_session.id,
                student_id=student.id,
                student_number_snapshot=student.student_number,
                student_name_snapshot=student.name,
                class_name_snapshot=class_group.name,
                status="pending",
                last_modified_by=teacher.id,
                version=1,
            )
        )
    append_audit(
        db,
        actor_user_id=teacher.id,
        action="ATTENDANCE_SESSION_CREATED",
        entity_type="attendance_session",
        entity_id=attendance_session.id,
        before_value=None,
        after_value={
            "class_group_id": class_group.id,
            "session_date": session_date.isoformat(),
            "status": "DRAFT",
            "record_count": len(roster),
        },
        reason=None,
        ip_address=ip_address,
        request_id=request_id,
    )
    db.commit()
    return attendance_session, class_group, course


def list_attendance_sessions(
    db: Session,
    *,
    teacher_id: str,
    page: int,
    page_size: int,
    course_id: str | None,
    class_group_id: str | None,
    status: str | None,
    date_from: date | None,
    date_to: date | None,
) -> tuple[list[tuple[AttendanceSession, ClassGroup, Course]], int]:
    filters = [Course.owner_teacher_id == teacher_id]
    if course_id:
        filters.append(Course.id == course_id)
    if class_group_id:
        filters.append(ClassGroup.id == class_group_id)
    if status:
        filters.append(AttendanceSession.status == status)
    if date_from:
        filters.append(AttendanceSession.session_date >= date_from)
    if date_to:
        filters.append(AttendanceSession.session_date <= date_to)
    base = (
        select(AttendanceSession, ClassGroup, Course)
        .join(ClassGroup, ClassGroup.id == AttendanceSession.class_group_id)
        .join(Course, Course.id == ClassGroup.course_id)
        .where(*filters)
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(
        db.execute(
            base.order_by(AttendanceSession.created_at.desc(), AttendanceSession.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).tuples()
    )
    return rows, total


def session_records(db: Session, session_id: str) -> list[tuple[AttendanceRecord, User]]:
    return list(
        db.execute(
            select(AttendanceRecord, User)
            .join(User, User.id == AttendanceRecord.last_modified_by)
            .where(AttendanceRecord.session_id == session_id)
            .order_by(AttendanceRecord.student_number_snapshot, AttendanceRecord.id)
        ).tuples()
    )


def _iso_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return aware.isoformat().replace("+00:00", "Z")


def _record_snapshot(record: AttendanceRecord, modifier: User) -> dict[str, object]:
    return {
        "id": record.id,
        "student_id": record.student_id,
        "student_number": record.student_number_snapshot,
        "student_name": record.student_name_snapshot,
        "class_name": record.class_name_snapshot,
        "status": record.status,
        "marked_at": _iso_timestamp(record.marked_at),
        "last_modified_at": _iso_timestamp(record.last_modified_at),
        "last_modified_by": {"id": modifier.id, "display_name": modifier.display_name},
        "version": record.version,
    }


def _owned_record(
    db: Session, *, teacher_id: str, record_id: str
) -> tuple[AttendanceRecord, AttendanceSession]:
    row = db.execute(
        select(AttendanceRecord, AttendanceSession)
        .join(AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id)
        .join(ClassGroup, ClassGroup.id == AttendanceSession.class_group_id)
        .join(Course, Course.id == ClassGroup.course_id)
        .where(AttendanceRecord.id == record_id, Course.owner_teacher_id == teacher_id)
    ).one_or_none()
    if row is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "考勤记录不存在")
    return row[0], row[1]


def update_attendance_record(
    db: Session,
    *,
    teacher: User,
    record_id: str,
    status: str,
    expected_version: int,
    client_mutation_id: str,
    reason: str | None,
    ip_address: str,
    request_id: str,
) -> dict[str, object]:
    existing_audit = db.scalar(
        select(AuditLog).where(AuditLog.client_mutation_id == client_mutation_id)
    )
    if existing_audit is not None:
        if (
            existing_audit.action == "ATTENDANCE_STATUS_CHANGED"
            and existing_audit.entity_id == record_id
            and existing_audit.actor_user_id == teacher.id
            and existing_audit.after_value is not None
        ):
            return existing_audit.after_value
        raise ApiError(400, "INVALID_REQUEST", "变更 ID 已被其他操作使用")

    record, attendance_session = _owned_record(db, teacher_id=teacher.id, record_id=record_id)
    normalized_reason = reason.strip() if reason is not None else None
    if attendance_session.status == "COMPLETED" and not normalized_reason:
        raise ApiError(400, "INVALID_REQUEST", "修正已完成考勤时必须填写原因")

    before: dict[str, object] = {
        "id": record.id,
        "status": record.status,
        "marked_at": _iso_timestamp(record.marked_at),
        "last_modified_at": _iso_timestamp(record.last_modified_at),
        "last_modified_by": record.last_modified_by,
        "version": record.version,
    }
    now = utc_now()
    result = db.execute(
        update(AttendanceRecord)
        .where(
            AttendanceRecord.id == record.id,
            AttendanceRecord.version == expected_version,
        )
        .values(
            status=status,
            marked_at=func.coalesce(AttendanceRecord.marked_at, now),
            last_modified_by=teacher.id,
            last_modified_at=now,
            version=AttendanceRecord.version + 1,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    if getattr(result, "rowcount", 0) != 1:
        db.expire(record)
        current = db.get(AttendanceRecord, record.id)
        if current is None:
            raise ApiError(404, "RESOURCE_NOT_FOUND", "考勤记录不存在")
        raise ApiError(
            409,
            "ATTENDANCE_RECORD_CONFLICT",
            "该记录已被其他操作更新，请刷新后重试",
            {
                "current_record": {
                    "id": current.id,
                    "status": current.status,
                    "version": current.version,
                }
            },
        )

    db.refresh(record)
    after = _record_snapshot(record, teacher)
    try:
        append_audit(
            db,
            actor_user_id=teacher.id,
            action="ATTENDANCE_STATUS_CHANGED",
            entity_type="attendance_record",
            entity_id=record.id,
            before_value=before,
            after_value=after,
            reason=normalized_reason,
            ip_address=ip_address,
            request_id=request_id,
            client_mutation_id=client_mutation_id,
        )
        db.commit()
        return after
    except IntegrityError:
        db.rollback()
        replay = db.scalar(
            select(AuditLog).where(AuditLog.client_mutation_id == client_mutation_id)
        )
        if (
            replay is not None
            and replay.entity_id == record_id
            and replay.action == "ATTENDANCE_STATUS_CHANGED"
            and replay.after_value is not None
        ):
            return replay.after_value
        raise ApiError(400, "INVALID_REQUEST", "变更 ID 已被其他操作使用") from None


def complete_attendance_session(
    db: Session,
    *,
    teacher: User,
    session_id: str,
    ip_address: str,
    request_id: str,
) -> tuple[AttendanceSession, ClassGroup, Course]:
    row = db.execute(
        select(AttendanceSession, ClassGroup, Course)
        .join(ClassGroup, ClassGroup.id == AttendanceSession.class_group_id)
        .join(Course, Course.id == ClassGroup.course_id)
        .where(
            AttendanceSession.id == session_id,
            Course.owner_teacher_id == teacher.id,
        )
        .with_for_update()
    ).one_or_none()
    if row is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "考勤场次不存在")
    attendance_session, class_group, course = row
    if attendance_session.status == "COMPLETED":
        return attendance_session, class_group, course
    completed_at = utc_now()
    attendance_session.status = "COMPLETED"
    attendance_session.completed_at = completed_at
    append_audit(
        db,
        actor_user_id=teacher.id,
        action="ATTENDANCE_SESSION_COMPLETED",
        entity_type="attendance_session",
        entity_id=attendance_session.id,
        before_value={"status": "DRAFT", "completed_at": None},
        after_value={
            "status": "COMPLETED",
            "completed_at": _iso_timestamp(completed_at),
        },
        reason=None,
        ip_address=ip_address,
        request_id=request_id,
    )
    db.commit()
    return attendance_session, class_group, course
