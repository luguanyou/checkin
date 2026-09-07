from collections import defaultdict

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from attendance_api.errors import ApiError
from attendance_api.models import (
    AttendanceSession,
    ClassGroup,
    Course,
    Enrollment,
    ImportPreview,
    User,
)
from attendance_api.modules.audit.service import append_audit


def _duplicate_error() -> ApiError:
    return ApiError(409, "DUPLICATE_RESOURCE", "同一范围内已存在相同记录")


def _resource_state_error(message: str) -> ApiError:
    return ApiError(409, "RESOURCE_STATE_CONFLICT", message)


def get_owned_course(db: Session, *, teacher_id: str, course_id: str) -> Course:
    course = db.scalar(
        select(Course).where(Course.id == course_id, Course.owner_teacher_id == teacher_id)
    )
    if course is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "课程不存在")
    return course


def get_owned_class_group(
    db: Session, *, teacher_id: str, class_group_id: str
) -> tuple[ClassGroup, Course]:
    row = db.execute(
        select(ClassGroup, Course)
        .join(Course, Course.id == ClassGroup.course_id)
        .where(ClassGroup.id == class_group_id, Course.owner_teacher_id == teacher_id)
    ).one_or_none()
    if row is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "班级不存在")
    return row[0], row[1]


def list_courses(
    db: Session,
    *,
    teacher_id: str,
    page: int,
    page_size: int,
    status: str | None,
    term: str | None,
    query: str | None,
) -> tuple[list[Course], int, dict[str, list[tuple[ClassGroup, int]]]]:
    filters = [Course.owner_teacher_id == teacher_id]
    if status:
        filters.append(Course.status == status)
    normalized_term = term.strip() if term else ""
    if normalized_term:
        filters.append(Course.term == normalized_term)
    normalized_query = query.strip() if query else ""
    if normalized_query:
        pattern = f"%{normalized_query}%"
        filters.append(or_(Course.name.like(pattern), Course.code.like(pattern)))

    total = db.scalar(select(func.count()).select_from(Course).where(*filters)) or 0
    courses = list(
        db.scalars(
            select(Course)
            .where(*filters)
            .order_by(Course.created_at.desc(), Course.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    summaries: dict[str, list[tuple[ClassGroup, int]]] = defaultdict(list)
    course_ids = [course.id for course in courses]
    if course_ids:
        rows = db.execute(
            select(ClassGroup, func.count(Enrollment.id))
            .outerjoin(
                Enrollment,
                and_(
                    Enrollment.class_group_id == ClassGroup.id,
                    Enrollment.status == "ACTIVE",
                ),
            )
            .where(ClassGroup.course_id.in_(course_ids))
            .group_by(ClassGroup.id)
            .order_by(ClassGroup.created_at, ClassGroup.id)
        )
        for class_group, active_count in rows:
            summaries[class_group.course_id].append((class_group, active_count))
    return courses, total, dict(summaries)


def class_summary(db: Session, class_group: ClassGroup) -> tuple[ClassGroup, int]:
    count = db.scalar(
        select(func.count())
        .select_from(Enrollment)
        .where(
            Enrollment.class_group_id == class_group.id,
            Enrollment.status == "ACTIVE",
        )
    )
    return class_group, count or 0


def create_course(
    db: Session,
    *,
    teacher: User,
    name: str,
    code: str,
    term: str,
    ip_address: str,
    request_id: str,
) -> Course:
    duplicate = db.scalar(
        select(Course.id).where(
            Course.owner_teacher_id == teacher.id, Course.code == code, Course.term == term
        )
    )
    if duplicate is not None:
        raise _duplicate_error()
    course = Course(owner_teacher_id=teacher.id, name=name, code=code, term=term, status="ACTIVE")
    db.add(course)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise _duplicate_error() from None
    append_audit(
        db,
        actor_user_id=teacher.id,
        action="COURSE_CREATED",
        entity_type="course",
        entity_id=course.id,
        before_value=None,
        after_value={"name": name, "code": code, "term": term, "status": "ACTIVE"},
        reason=None,
        ip_address=ip_address,
        request_id=request_id,
    )
    db.commit()
    return course


def update_course(
    db: Session,
    *,
    teacher: User,
    course_id: str,
    changes: dict[str, str | None],
    ip_address: str,
    request_id: str,
) -> Course:
    course = get_owned_course(db, teacher_id=teacher.id, course_id=course_id)
    if course.status == "ARCHIVED" and changes.get("status") == "ACTIVE":
        raise _resource_state_error("已归档课程不能重新启用")
    target_code = changes.get("code") or course.code
    target_term = changes.get("term") or course.term
    duplicate = db.scalar(
        select(Course.id).where(
            Course.owner_teacher_id == teacher.id,
            Course.code == target_code,
            Course.term == target_term,
            Course.id != course.id,
        )
    )
    if duplicate is not None:
        raise _duplicate_error()
    before = {key: getattr(course, key) for key in changes}
    for key, value in changes.items():
        if value is not None:
            setattr(course, key, value)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise _duplicate_error() from None
    append_audit(
        db,
        actor_user_id=teacher.id,
        action="COURSE_UPDATED",
        entity_type="course",
        entity_id=course.id,
        before_value=before,
        after_value={key: getattr(course, key) for key in changes},
        reason=None,
        ip_address=ip_address,
        request_id=request_id,
    )
    db.commit()
    return course


def create_class_group(
    db: Session,
    *,
    teacher: User,
    course_id: str,
    name: str,
    ip_address: str,
    request_id: str,
) -> ClassGroup:
    course = get_owned_course(db, teacher_id=teacher.id, course_id=course_id)
    if course.status != "ACTIVE":
        raise _resource_state_error("已归档课程不能创建班级")
    duplicate = db.scalar(
        select(ClassGroup.id).where(ClassGroup.course_id == course.id, ClassGroup.name == name)
    )
    if duplicate is not None:
        raise _duplicate_error()
    class_group = ClassGroup(course_id=course.id, name=name, status="ACTIVE")
    db.add(class_group)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise _duplicate_error() from None
    append_audit(
        db,
        actor_user_id=teacher.id,
        action="CLASS_GROUP_CREATED",
        entity_type="class_group",
        entity_id=class_group.id,
        before_value=None,
        after_value={"course_id": course.id, "name": name, "status": "ACTIVE"},
        reason=None,
        ip_address=ip_address,
        request_id=request_id,
    )
    db.commit()
    return class_group


def update_class_group(
    db: Session,
    *,
    teacher: User,
    class_group_id: str,
    changes: dict[str, str | None],
    ip_address: str,
    request_id: str,
) -> ClassGroup:
    class_group, _course = get_owned_class_group(
        db, teacher_id=teacher.id, class_group_id=class_group_id
    )
    if class_group.status == "ARCHIVED" and changes.get("status") == "ACTIVE":
        raise _resource_state_error("已归档班级不能重新启用")
    target_name = changes.get("name") or class_group.name
    duplicate = db.scalar(
        select(ClassGroup.id).where(
            ClassGroup.course_id == class_group.course_id,
            ClassGroup.name == target_name,
            ClassGroup.id != class_group.id,
        )
    )
    if duplicate is not None:
        raise _duplicate_error()
    before = {key: getattr(class_group, key) for key in changes}
    for key, value in changes.items():
        if value is not None:
            setattr(class_group, key, value)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise _duplicate_error() from None
    append_audit(
        db,
        actor_user_id=teacher.id,
        action="CLASS_GROUP_UPDATED",
        entity_type="class_group",
        entity_id=class_group.id,
        before_value=before,
        after_value={key: getattr(class_group, key) for key in changes},
        reason=None,
        ip_address=ip_address,
        request_id=request_id,
    )
    db.commit()
    return class_group


def delete_course(
    db: Session,
    *,
    teacher: User,
    course_id: str,
    ip_address: str,
    request_id: str,
) -> None:
    course = get_owned_course(db, teacher_id=teacher.id, course_id=course_id)
    child_count = (
        db.scalar(
            select(func.count()).select_from(ClassGroup).where(ClassGroup.course_id == course.id)
        )
        or 0
    )
    if child_count:
        raise _resource_state_error("课程仍包含班级，无法删除")
    append_audit(
        db,
        actor_user_id=teacher.id,
        action="COURSE_DELETED",
        entity_type="course",
        entity_id=course.id,
        before_value={
            "name": course.name,
            "code": course.code,
            "term": course.term,
            "status": course.status,
        },
        after_value=None,
        reason=None,
        ip_address=ip_address,
        request_id=request_id,
    )
    db.delete(course)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _resource_state_error("课程存在关联数据，无法删除") from None


def delete_class_group(
    db: Session,
    *,
    teacher: User,
    class_group_id: str,
    ip_address: str,
    request_id: str,
) -> None:
    class_group, _course = get_owned_class_group(
        db, teacher_id=teacher.id, class_group_id=class_group_id
    )
    enrollment_count = (
        db.scalar(
            select(func.count())
            .select_from(Enrollment)
            .where(Enrollment.class_group_id == class_group.id)
        )
        or 0
    )
    session_count = (
        db.scalar(
            select(func.count())
            .select_from(AttendanceSession)
            .where(AttendanceSession.class_group_id == class_group.id)
        )
        or 0
    )
    preview_count = (
        db.scalar(
            select(func.count())
            .select_from(ImportPreview)
            .where(ImportPreview.class_group_id == class_group.id)
        )
        or 0
    )
    if enrollment_count or session_count or preview_count:
        raise _resource_state_error("班级存在名单或考勤数据，无法删除")
    append_audit(
        db,
        actor_user_id=teacher.id,
        action="CLASS_GROUP_DELETED",
        entity_type="class_group",
        entity_id=class_group.id,
        before_value={
            "course_id": class_group.course_id,
            "name": class_group.name,
            "status": class_group.status,
        },
        after_value=None,
        reason=None,
        ip_address=ip_address,
        request_id=request_id,
    )
    db.delete(class_group)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _resource_state_error("班级存在关联数据，无法删除") from None
