from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from attendance_api.errors import ApiError
from attendance_api.models import ClassGroup, Course, Enrollment, Student, User
from attendance_api.modules.audit.service import append_audit
from attendance_api.modules.courses.service import get_owned_class_group
from attendance_api.schemas.rosters import CreateRosterMemberRequest


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


def create_roster_member(
    db: Session,
    *,
    teacher: User,
    class_group_id: str,
    payload: "CreateRosterMemberRequest",
    ip_address: str,
    request_id: str,
) -> tuple[Enrollment, Student]:
    class_group, course = get_owned_class_group(
        db, teacher_id=teacher.id, class_group_id=class_group_id
    )
    if class_group.status != "ACTIVE" or course.status != "ACTIVE":
        raise ApiError(409, "RESOURCE_STATE_CONFLICT", "已归档课程或班级不能修改名单")
    try:
        student = db.scalar(
            select(Student)
            .where(Student.student_number == payload.student_number)
            .with_for_update()
        )
        if student is None:
            student = Student(**payload.model_dump())
            db.add(student)
            db.flush()
        elif student.name != payload.name:
            raise ApiError(409, "DUPLICATE_RESOURCE", "该学号已存在且姓名不一致，请核对学号和姓名")
        enrollment = db.scalar(
            select(Enrollment)
            .where(Enrollment.class_group_id == class_group_id, Enrollment.student_id == student.id)
            .with_for_update()
        )
        previous = enrollment.status if enrollment else None
        if previous == "ACTIVE":
            raise ApiError(409, "DUPLICATE_RESOURCE", "该学生已在当前班级名单中")
        if enrollment is None:
            enrollment = Enrollment(
                class_group_id=class_group_id, student_id=student.id, status="ACTIVE"
            )
            db.add(enrollment)
        else:
            enrollment.status = "ACTIVE"
        db.flush()
        append_audit(
            db,
            actor_user_id=teacher.id,
            action="ROSTER_MEMBER_ADDED",
            entity_type="enrollment",
            entity_id=enrollment.id,
            before_value={"status": previous},
            after_value={"status": "ACTIVE"},
            reason=None,
            ip_address=ip_address,
            request_id=request_id,
        )
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise ApiError(409, "DUPLICATE_RESOURCE", "该学号或名单成员已存在，请刷新后重试") from error
    return enrollment, student


def update_roster_member(
    db: Session,
    *,
    teacher: User,
    class_group_id: str,
    enrollment_id: str,
    payload: CreateRosterMemberRequest,
    ip_address: str,
    request_id: str,
) -> tuple[Enrollment, Student]:
    row = db.execute(
        select(Enrollment, Student, ClassGroup, Course)
        .join(Student, Student.id == Enrollment.student_id)
        .join(ClassGroup, ClassGroup.id == Enrollment.class_group_id)
        .join(Course, Course.id == ClassGroup.course_id)
        .where(
            Enrollment.id == enrollment_id,
            ClassGroup.id == class_group_id,
            Course.owner_teacher_id == teacher.id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one_or_none()
    if row is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "名单成员不存在")
    enrollment, student, group, course = row
    if group.status != "ACTIVE" or course.status != "ACTIVE":
        raise ApiError(409, "RESOURCE_STATE_CONFLICT", "已归档课程或班级不能编辑名单")
    from attendance_api.schemas.rosters import StudentResponse

    before = StudentResponse.model_validate(student).model_dump(mode="json")
    account = db.scalar(select(User).where(User.student_id == student.id).with_for_update())
    number_changed = student.student_number != payload.student_number
    duplicate = db.scalar(
        select(Student.id).where(
            Student.student_number == payload.student_number, Student.id != student.id
        )
    )
    if duplicate:
        raise ApiError(409, "DUPLICATE_RESOURCE", "该学号已存在，请核对后重试")
    if (
        account is not None
        and number_changed
        and db.scalar(
            select(User.id).where(
                User.username == payload.student_number.lower(), User.id != account.id
            )
        )
    ):
        raise ApiError(409, "DUPLICATE_RESOURCE", "该学号已被其他登录账号使用，请核对后重试")
    try:
        student.student_number = payload.student_number
        student.name = payload.name
        student.gender = payload.gender or None
        student.major = payload.major or None
        if account is not None:
            account.display_name = payload.name
            if number_changed:
                account.username = payload.student_number.lower()
        db.flush()
        append_audit(
            db,
            actor_user_id=teacher.id,
            action="STUDENT_PROFILE_UPDATED",
            entity_type="student",
            entity_id=student.id,
            before_value=before,
            after_value=StudentResponse.model_validate(student).model_dump(mode="json"),
            reason=None,
            ip_address=ip_address,
            request_id=request_id,
        )
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise ApiError(409, "DUPLICATE_RESOURCE", "学号或登录账号已存在，请核对后重试") from error
    return enrollment, student
