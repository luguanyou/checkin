from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from attendance_api.errors import ApiError
from attendance_api.models import (
    ClassGroup,
    Course,
    Enrollment,
    MonitorGrant,
    RegistrationReviewer,
    ScoreItem,
    Student,
    User,
)
from attendance_api.modules.courses.service import get_owned_class_group
from attendance_api.modules.scores import service as scores
from attendance_api.schemas.scores import SetScoreRecordsRequest


def manage_data(db: Session, *, teacher: User, class_id: str) -> dict[str, Any]:
    group, course = get_owned_class_group(db, teacher_id=teacher.id, class_group_id=class_id)
    items = list(
        db.scalars(
            select(ScoreItem)
            .where(ScoreItem.class_group_id == class_id)
            .order_by(ScoreItem.occurred_on, ScoreItem.id)
        )
    )
    rows = db.execute(
        select(Enrollment, Student, User)
        .join(Student, Student.id == Enrollment.student_id)
        .outerjoin(User, (User.student_id == Student.id) & (User.role == "STUDENT"))
        .where(Enrollment.class_group_id == class_id)
        .order_by(Student.student_number)
    ).all()
    grants = list(
        db.scalars(
            select(MonitorGrant)
            .join(ScoreItem, ScoreItem.id == MonitorGrant.item_id)
            .where(ScoreItem.class_group_id == class_id)
        )
    )
    reviewer_ids = set(
        db.scalars(
            select(RegistrationReviewer.user_id).where(
                RegistrationReviewer.class_group_id == class_id
            )
        )
    )
    return {
        "readonly": group.status != "ACTIVE" or course.status != "ACTIVE",
        "items": [item_data(item) for item in items],
        "members": [
            {
                "student": {
                    "id": student.id,
                    "student_number": student.student_number,
                    "name": student.name,
                    "gender": student.gender,
                    "major": student.major,
                },
                "enrollment_status": enrollment.status,
                "user_id": user.id if user else None,
                "username": user.username if user else None,
                "account_status": user.status if user else None,
                "can_review_registrations": bool(user and user.id in reviewer_ids),
                "item_ids": [
                    grant.item_id for grant in grants if user and grant.user_id == user.id
                ],
            }
            for enrollment, student, user in rows
        ],
    }


def item_data(item: ScoreItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "category": item.category,
        "occurred_on": str(item.occurred_on),
        "description": item.description,
        "default_points": str(item.default_points) if item.default_points is not None else None,
    }


def replace_grants(
    db: Session,
    *,
    teacher: User,
    class_id: str,
    user_id: str,
    item_ids: list[str],
    can_review_registrations: bool = False,
) -> tuple[list[str], list[str], bool]:
    # All grant writes and monitor saves lock the class first, so revocation and saving serialize.
    scope = db.execute(
        select(ClassGroup, Course)
        .join(Course, Course.id == ClassGroup.course_id)
        .where(ClassGroup.id == class_id, Course.owner_teacher_id == teacher.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one_or_none()
    if scope is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "班级不存在")
    group, course = scope
    user = db.scalar(select(User).where(User.id == user_id, User.role == "STUDENT"))
    enrollment = db.scalar(
        select(Enrollment).where(
            Enrollment.student_id == (user.student_id if user else None),
            Enrollment.class_group_id == class_id,
        )
    )
    if not user or not enrollment:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "学生账号不属于当前班级")
    if (item_ids or can_review_registrations) and (
        group.status != "ACTIVE"
        or course.status != "ACTIVE"
        or user.status != "ACTIVE"
        or enrollment.status != "ACTIVE"
    ):
        raise ApiError(
            409, "RESOURCE_STATE_CONFLICT", "班级、课程、学生账号和名单关系均须启用才能授权"
        )
    allowed = set(db.scalars(select(ScoreItem.id).where(ScoreItem.class_group_id == class_id)))
    if not set(item_ids).issubset(allowed):
        raise ApiError(400, "INVALID_REQUEST", "只能授权当前班级的评分项目")
    current = list(
        db.scalars(
            select(MonitorGrant)
            .where(MonitorGrant.user_id == user_id, MonitorGrant.item_id.in_(allowed))
            .with_for_update()
        )
    )
    before = [grant.item_id for grant in current]
    db.execute(
        delete(MonitorGrant).where(
            MonitorGrant.user_id == user_id, MonitorGrant.item_id.in_(allowed)
        )
    )
    db.add_all(
        [
            MonitorGrant(user_id=user_id, item_id=item_id, granted_by=teacher.id)
            for item_id in sorted(set(item_ids))
        ]
    )
    reviewer = db.scalar(
        select(RegistrationReviewer)
        .where(
            RegistrationReviewer.class_group_id == class_id, RegistrationReviewer.user_id == user_id
        )
        .with_for_update()
    )
    before_review = reviewer is not None
    if can_review_registrations and reviewer is None:
        db.add(
            RegistrationReviewer(class_group_id=class_id, user_id=user_id, granted_by=teacher.id)
        )
    elif not can_review_registrations and reviewer is not None:
        db.delete(reviewer)
    return before, sorted(set(item_ids)), before_review


def authorized_item(
    db: Session, *, user: User, class_id: str, item_id: str, lock: bool = False
) -> tuple[ScoreItem, Course]:
    if user.role != "STUDENT" or not user.student_id or user.status != "ACTIVE":
        raise ApiError(403, "RESOURCE_FORBIDDEN", "无班长登记权限")
    if lock:
        db.execute(select(ClassGroup).where(ClassGroup.id == class_id).with_for_update()).first()
    query = (
        select(ScoreItem, Course)
        .join(ClassGroup, ClassGroup.id == ScoreItem.class_group_id)
        .join(Course, Course.id == ClassGroup.course_id)
        .join(MonitorGrant, MonitorGrant.item_id == ScoreItem.id)
        .join(Enrollment, Enrollment.class_group_id == ClassGroup.id)
        .where(
            ScoreItem.id == item_id,
            ClassGroup.id == class_id,
            MonitorGrant.user_id == user.id,
            Enrollment.student_id == user.student_id,
            Enrollment.status == "ACTIVE",
            ClassGroup.status == "ACTIVE",
            Course.status == "ACTIVE",
        )
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.execute(query).one_or_none()
    if row is None:
        raise ApiError(403, "RESOURCE_FORBIDDEN", "项目未授权或授权已失效，请联系任课老师")
    return row[0], row[1]


def project_list(db: Session, user: User) -> list[dict[str, Any]]:
    if user.role != "STUDENT" or user.status != "ACTIVE" or not user.student_id:
        return []
    rows = db.execute(
        select(ScoreItem, ClassGroup, Course)
        .join(ClassGroup, ClassGroup.id == ScoreItem.class_group_id)
        .join(Course, Course.id == ClassGroup.course_id)
        .join(MonitorGrant, MonitorGrant.item_id == ScoreItem.id)
        .join(Enrollment, Enrollment.class_group_id == ClassGroup.id)
        .where(
            MonitorGrant.user_id == user.id,
            Enrollment.student_id == user.student_id,
            Enrollment.status == "ACTIVE",
            ClassGroup.status == "ACTIVE",
            Course.status == "ACTIVE",
        )
        .order_by(Course.name, ClassGroup.name, ScoreItem.occurred_on, ScoreItem.id)
    ).all()
    return [
        {
            **item_data(item),
            "class_id": group.id,
            "class_name": group.name,
            "course_name": course.name,
        }
        for item, group, course in rows
    ]


def monitor_project(db: Session, *, user: User, class_id: str, item_id: str) -> dict[str, Any]:
    item, course = authorized_item(db, user=user, class_id=class_id, item_id=item_id)
    book = scores.get_book(db, teacher_id=course.owner_teacher_id, class_group_id=class_id)
    return {
        "version": book.version,
        "item": item_data(item),
        "students": [
            {
                **student.model_dump(mode="json"),
                "can_edit": student.student_id != user.student_id
                and student.enrollment_status == "ACTIVE",
            }
            for student in book.students
            if student.enrollment_status == "ACTIVE"
        ],
        "records": [
            record.model_dump(mode="json")
            for record in book.records
            if record.item_id == item_id
            and any(
                student.enrollment_id == record.enrollment_id
                and student.enrollment_status == "ACTIVE"
                for student in book.students
            )
        ],
    }


def save_project(
    db: Session,
    *,
    user: User,
    class_id: str,
    item_id: str,
    payload: SetScoreRecordsRequest,
    ip_address: str,
    request_id: str,
) -> dict[str, Any]:
    _, course = authorized_item(db, user=user, class_id=class_id, item_id=item_id, lock=True)
    own = db.scalar(
        select(Enrollment.id).where(
            Enrollment.class_group_id == class_id, Enrollment.student_id == user.student_id
        )
    )
    if any(record.enrollment_id == own for record in payload.records):
        raise ApiError(403, "RESOURCE_FORBIDDEN", "班长本人的分数由任课老师登记")
    teacher = db.get(User, course.owner_teacher_id)
    if teacher is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "任课老师不存在")
    scores.mutate_book(
        db,
        teacher=teacher,
        actor=user,
        class_group_id=class_id,
        payload=payload,
        item_id=item_id,
        ip_address=ip_address,
        request_id=request_id,
    )
    return monitor_project(db, user=user, class_id=class_id, item_id=item_id)
