from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from attendance_api.errors import ApiError
from attendance_api.models import ClassGroup, Course, Enrollment, Student, User
from attendance_api.modules.audit.service import append_audit
from attendance_api.modules.courses.service import get_owned_class_group


def get_roster(
    db: Session,
    *,
    teacher_id: str,
    class_group_id: str,
    page: int,
    page_size: int,
    status: str,
    query: str | None,
) -> tuple[list[tuple[Enrollment, Student]], int]:
    get_owned_class_group(db, teacher_id=teacher_id, class_group_id=class_group_id)
    filters = [Enrollment.class_group_id == class_group_id]
    if status != "all":
        filters.append(Enrollment.status == status)
    normalized_query = query.strip() if query else ""
    if normalized_query:
        pattern = f"%{normalized_query}%"
        filters.append(
            or_(
                Student.name.like(pattern),
                Student.student_number.like(pattern),
                Student.major.like(pattern),
            )
        )
    total = (
        db.scalar(
            select(func.count())
            .select_from(Enrollment)
            .join(Student, Student.id == Enrollment.student_id)
            .where(*filters)
        )
        or 0
    )
    rows = list(
        db.execute(
            select(Enrollment, Student)
            .join(Student, Student.id == Enrollment.student_id)
            .where(*filters)
            .order_by(Student.student_number, Enrollment.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).tuples()
    )
    return rows, total


def update_enrollment_status(
    db: Session,
    *,
    teacher: User,
    enrollment_id: str,
    status: str,
    ip_address: str,
    request_id: str,
) -> tuple[Enrollment, Student]:
    row = db.execute(
        select(Enrollment, Student, ClassGroup, Course)
        .join(Student, Student.id == Enrollment.student_id)
        .join(ClassGroup, ClassGroup.id == Enrollment.class_group_id)
        .join(Course, Course.id == ClassGroup.course_id)
        .where(Enrollment.id == enrollment_id, Course.owner_teacher_id == teacher.id)
        .with_for_update()
    ).one_or_none()
    if row is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "名单成员不存在")
    enrollment, student, class_group, course = row
    if class_group.status != "ACTIVE" or course.status != "ACTIVE":
        raise ApiError(409, "RESOURCE_STATE_CONFLICT", "已归档课程或班级不能修改名单")
    previous_status = enrollment.status
    enrollment.status = status
    append_audit(
        db,
        actor_user_id=teacher.id,
        action="ENROLLMENT_STATUS_CHANGED",
        entity_type="enrollment",
        entity_id=enrollment.id,
        before_value={"status": previous_status},
        after_value={"status": status},
        reason=None,
        ip_address=ip_address,
        request_id=request_id,
    )
    db.commit()
    return enrollment, student
