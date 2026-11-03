from typing import Any
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from attendance_api.errors import ApiError
from attendance_api.models import (
    AuditLog,
    ClassGroup,
    Course,
    Enrollment,
    RegistrationReviewer,
    Student,
    StudentRegistration,
    User,
)
from attendance_api.models.base import utc_now
from attendance_api.modules.audit.service import append_audit
from attendance_api.security.passwords import hash_password


def find_student(db: Session, number: str, name: str, lock: bool = False) -> Student:
    query = select(Student).where(
        func.lower(Student.student_number) == number.strip().lower(), Student.name == name.strip()
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    student = db.scalar(query)
    if student is None:
        raise ApiError(400, "ROSTER_NOT_MATCHED", "学号与姓名未匹配到名单，请核对或联系任课老师")
    return student


def eligible_classes(db: Session, student_id: str) -> list[dict[str, Any]]:
    rows = db.execute(
        select(ClassGroup, Course)
        .join(Course, Course.id == ClassGroup.course_id)
        .join(Enrollment, Enrollment.class_group_id == ClassGroup.id)
        .where(
            Enrollment.student_id == student_id,
            Enrollment.status == "ACTIVE",
            ClassGroup.status == "ACTIVE",
            Course.status == "ACTIVE",
        )
        .order_by(Course.name, ClassGroup.name)
    ).all()
    return [
        {"id": group.id, "name": group.name, "course_name": course.name, "term": course.term}
        for group, course in rows
    ]


def submit(db: Session, *, number: str, name: str, class_id: str, password: str) -> dict[str, str]:
    student = find_student(db, number, name, lock=True)
    if db.scalar(
        select(User.id).where(
            (User.student_id == student.id) | (User.username == student.student_number.lower())
        )
    ):
        raise ApiError(409, "ACCOUNT_EXISTS", "账号已存在，请直接登录；忘记密码请联系管理员")
    if class_id not in {item["id"] for item in eligible_classes(db, student.id)}:
        raise ApiError(400, "INVALID_CLASS", "不在该班级的有效名单中，请重新匹配班级")
    registration = db.scalar(
        select(StudentRegistration)
        .where(StudentRegistration.student_id == student.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if registration and registration.status != "REJECTED":
        raise ApiError(
            409, "REGISTRATION_EXISTS", "申请已提交，请等待审核；可在登录页面查看审核提示"
        )
    if registration is None:
        registration = StudentRegistration(student_id=student.id, class_group_id=class_id)
        db.add(registration)
    else:
        # A reapplication gets a new identity; stale review pages cannot approve it.
        registration.id = str(uuid4())
    registration.class_group_id = class_id
    registration.password_hash = hash_password(password)
    registration.status = "PENDING"
    registration.reviewed_by = None
    registration.review_reason = None
    registration.created_at = utc_now()
    registration.updated_at = utc_now()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "REGISTRATION_EXISTS", "申请已存在，请勿重复提交") from None
    return {"status": "PENDING", "message": "注册申请已提交，审核通过后可使用学号和自设密码登录"}


def require_reviewer(db: Session, *, actor: User, class_id: str) -> ClassGroup:
    row = db.execute(
        select(ClassGroup, Course)
        .join(Course, Course.id == ClassGroup.course_id)
        .where(ClassGroup.id == class_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one_or_none()
    if row is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "班级不存在")
    group, course = row._tuple()
    if actor.role == "TEACHER":
        if course.owner_teacher_id != actor.id:
            raise ApiError(404, "RESOURCE_NOT_FOUND", "班级不存在")
    elif actor.role == "STUDENT" and actor.status == "ACTIVE":
        grant = db.scalar(
            select(RegistrationReviewer.id)
            .where(
                RegistrationReviewer.class_group_id == class_id,
                RegistrationReviewer.user_id == actor.id,
            )
            .with_for_update()
        )
        enrolled = db.scalar(
            select(Enrollment.id).where(
                Enrollment.class_group_id == class_id,
                Enrollment.student_id == actor.student_id,
                Enrollment.status == "ACTIVE",
            )
        )
        if not grant or not enrolled:
            raise ApiError(403, "RESOURCE_FORBIDDEN", "未获授权审核本班注册申请")
    else:
        raise ApiError(403, "RESOURCE_FORBIDDEN", "无注册审核权限")
    if group.status != "ACTIVE" or course.status != "ACTIVE":
        raise ApiError(409, "RESOURCE_STATE_CONFLICT", "归档课程或班级不能审核注册")
    return group


def list_applications(
    db: Session, *, actor: User, class_id: str, status: str
) -> list[dict[str, Any]]:
    require_reviewer(db, actor=actor, class_id=class_id)
    query = select(StudentRegistration, Student, User.display_name).join(
        Student, Student.id == StudentRegistration.student_id
    )
    query = query.outerjoin(User, User.id == StudentRegistration.reviewed_by).where(
        application_scope(actor=actor, class_id=class_id)
    )
    if status != "all":
        query = query.where(StudentRegistration.status == status)
    rows = db.execute(query.order_by(StudentRegistration.created_at, StudentRegistration.id)).all()
    events = db.execute(
        select(AuditLog, User.display_name)
        .join(User, User.id == AuditLog.actor_user_id)
        .where(
            AuditLog.entity_type == "student_registration",
            AuditLog.action == "REGISTRATION_REVIEWED",
            AuditLog.after_value["student_id"].as_string().in_([row[1].id for row in rows]),
        )
        .order_by(AuditLog.created_at, AuditLog.id)
    ).all()
    history: dict[str, list[dict[str, Any]]] = {}
    for event, actor_name in events:
        value = event.after_value or {}
        if actor.role == "TEACHER" or value.get("class_id") == class_id:
            history.setdefault(str(value.get("student_id")), []).append(
                {
                    "reviewer_name": actor_name,
                    "status": value.get("status"),
                    "reason": value.get("reason"),
                    "created_at": event.created_at.isoformat(),
                }
            )
    return [
        {
            "id": application.id,
            "student_number": student.student_number,
            "name": student.name,
            "status": application.status,
            "created_at": application.created_at.isoformat(),
            "updated_at": application.updated_at.isoformat(),
            "reviewer_name": reviewer,
            "reason": application.review_reason,
            "history": history.get(student.id, []),
            "can_review": application.status == "PENDING" and student.id != actor.student_id,
        }
        for application, student, reviewer in rows
    ]


def application_scope(*, actor: User, class_id: str) -> ColumnElement[bool]:
    """Account registration follows the student across teachers' active rosters.

    Call only after require_reviewer has authorized the requested class. Monitor
    grants remain limited to applications submitted through their specific class.
    Keep source-class applications visible even after removal for review history.
    """
    submitted_here = StudentRegistration.class_group_id == class_id
    if actor.role != "TEACHER":
        return submitted_here
    enrolled_here = (
        select(Enrollment.id)
        .where(
            Enrollment.student_id == StudentRegistration.student_id,
            Enrollment.class_group_id == class_id,
            Enrollment.status == "ACTIVE",
        )
        .exists()
    )
    return or_(submitted_here, enrolled_here)


def review(
    db: Session,
    *,
    actor: User,
    class_id: str,
    ids: list[str],
    decision: str,
    reason: str | None,
    ip: str,
    request_id: str,
) -> int:
    require_reviewer(db, actor=actor, class_id=class_id)
    ids = sorted(set(ids))
    rows = db.execute(
        select(StudentRegistration, Student)
        .join(Student, Student.id == StudentRegistration.student_id)
        .where(StudentRegistration.id.in_(ids), application_scope(actor=actor, class_id=class_id))
        .order_by(StudentRegistration.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    if len(rows) != len(ids):
        raise ApiError(404, "RESOURCE_NOT_FOUND", "申请不属于当前班级")
    # Validate the complete batch before changing any application or creating accounts.
    for application, student in rows:
        if student.id == actor.student_id:
            raise ApiError(403, "SELF_REVIEW_FORBIDDEN", "不能审核自己的注册申请")
        if application.status != "PENDING":
            raise ApiError(409, "REGISTRATION_ALREADY_REVIEWED", "申请状态已更新，请刷新后重试")
        if decision == "APPROVED":
            enrolled = db.scalar(
                select(Enrollment.id).where(
                    Enrollment.class_group_id == class_id,
                    Enrollment.student_id == student.id,
                    Enrollment.status == "ACTIVE",
                )
            )
            if not enrolled or not application.password_hash:
                raise ApiError(409, "RESOURCE_STATE_CONFLICT", "学生已移出名单或申请失效")
            if db.scalar(
                select(User.id).where(
                    (User.student_id == student.id)
                    | (User.username == student.student_number.lower())
                )
            ):
                raise ApiError(409, "ACCOUNT_EXISTS", "学生账号已存在，不会覆盖密码；请驳回旧申请")
    try:
        for application, student in rows:
            if decision == "APPROVED":
                db.add(
                    User(
                        username=student.student_number.lower(),
                        student_id=student.id,
                        display_name=student.name,
                        password_hash=application.password_hash,
                        role="STUDENT",
                        status="ACTIVE",
                        must_change_password=False,
                    )
                )
                application.password_hash = None
            application.status = decision
            application.reviewed_by = actor.id
            application.review_reason = reason.strip() if reason else None
            application.updated_at = utc_now()
            append_audit(
                db,
                actor_user_id=actor.id,
                action="REGISTRATION_REVIEWED",
                entity_type="student_registration",
                entity_id=application.id,
                before_value={"status": "PENDING"},
                after_value={
                    "status": decision,
                    "student_id": student.id,
                    "class_id": application.class_group_id,
                    "review_class_id": class_id,
                    "reason": application.review_reason,
                },
                reason=application.review_reason,
                ip_address=ip,
                request_id=request_id,
            )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "ACCOUNT_EXISTS", "账号已被其他操作开通，请刷新申请列表") from None
    return len(rows)
