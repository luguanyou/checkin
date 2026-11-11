from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from attendance_api.errors import ApiError
from attendance_api.models import (
    AttendanceRecord,
    AttendanceSession,
    ClassGroup,
    Course,
    Enrollment,
    RegistrationReviewer,
    Student,
    User,
)
from attendance_api.modules.courses.service import get_owned_class_group
from attendance_api.modules.scores.service import get_book


def visibility(group: ClassGroup) -> dict[str, Any]:
    return {
        "attendance_visible": group.attendance_visible,
        "score_visibility": group.score_visibility,
    }


def student_classes(db: Session, user: User) -> list[dict[str, Any]]:
    from attendance_api.modules.monitors.service import project_list

    monitor_classes = {item["class_id"] for item in project_list(db, user)}
    review_classes = set(
        db.scalars(
            select(RegistrationReviewer.class_group_id).where(
                RegistrationReviewer.user_id == user.id
            )
        )
    )
    rows = db.execute(
        select(ClassGroup, Course, User.display_name)
        .join(Course, Course.id == ClassGroup.course_id)
        .join(User, User.id == Course.owner_teacher_id)
        .join(Enrollment, Enrollment.class_group_id == ClassGroup.id)
        .where(Enrollment.student_id == user.student_id, Enrollment.status == "ACTIVE")
        .order_by(
            Course.term.desc(), Course.name, ClassGroup.name, User.display_name, ClassGroup.id
        )
    ).all()
    return [
        {
            "id": group.id,
            "name": group.name,
            "course_name": course.name,
            "term": course.term,
            "teacher_name": teacher_name,
            "can_record_scores": group.id in monitor_classes,
            "can_review_registrations": group.id in review_classes
            and group.status == "ACTIVE"
            and course.status == "ACTIVE",
            **visibility(group),
        }
        for group, course, teacher_name in rows
    ]


def get_enrolled_class(
    db: Session, *, user: User, class_id: str
) -> tuple[Enrollment, ClassGroup, Course]:
    row = db.execute(
        select(Enrollment, ClassGroup, Course)
        .join(ClassGroup, ClassGroup.id == Enrollment.class_group_id)
        .join(Course, Course.id == ClassGroup.course_id)
        .where(
            Enrollment.student_id == user.student_id,
            Enrollment.class_group_id == class_id,
            Enrollment.status == "ACTIVE",
        )
    ).one_or_none()
    if row is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "班级不存在或已不在名单中")
    return row[0], row[1], row[2]


def student_class_data(db: Session, *, user: User, class_id: str) -> dict[str, Any]:
    enrollment, group, course = get_enrolled_class(db, user=user, class_id=class_id)
    result: dict[str, Any] = {
        **visibility(group),
        "attendance": None,
        "score": None,
        "details": None,
    }
    if group.attendance_visible:
        rows = db.execute(
            select(AttendanceRecord, AttendanceSession)
            .join(AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id)
            .where(
                AttendanceRecord.student_id == user.student_id,
                AttendanceSession.class_group_id == class_id,
            )
            .order_by(AttendanceSession.session_date.desc(), AttendanceSession.started_at.desc())
        ).all()
        result["attendance"] = [
            {
                "id": record.id,
                "date": str(session.session_date),
                "status": record.status,
                "session_status": session.status,
            }
            for record, session in rows
        ]
    if group.score_visibility in {"TOTAL", "DETAILS"}:
        book = get_book(
            db,
            teacher_id=course.owner_teacher_id,
            class_group_id=class_id,
            enrollment_id=enrollment.id,
        )
        summary = next(
            (item for item in book.summaries if item.enrollment_id == enrollment.id), None
        )
        result["score"] = (
            {"final_score": summary.final_score, "status": summary.status} if summary else None
        )
        if group.score_visibility == "DETAILS":
            result["details"] = {
                "settings": book.settings.model_dump(mode="json"),
                "summary": summary.model_dump(mode="json") if summary else None,
                "items": [item.model_dump(mode="json") for item in book.items],
                "records": [
                    record.model_dump(mode="json")
                    for record in book.records
                    if record.enrollment_id == enrollment.id
                ],
            }
    return result


def owned_student(db: Session, *, teacher: User, class_id: str, student_id: str) -> Student:
    group, course = get_owned_class_group(db, teacher_id=teacher.id, class_group_id=class_id)
    if group.status != "ACTIVE" or course.status != "ACTIVE":
        raise ApiError(409, "RESOURCE_STATE_CONFLICT", "归档课程或班级不可管理学生账号")
    student = db.scalar(
        select(Student)
        .join(Enrollment, Enrollment.student_id == Student.id)
        .where(
            Student.id == student_id,
            Enrollment.class_group_id == class_id,
            Enrollment.status == "ACTIVE",
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if student is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "学生不在当前班级中")
    return student
