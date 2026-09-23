from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Literal, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from attendance_api.errors import ApiError
from attendance_api.models import AuditLog, ClassGroup, Course, Enrollment, Student, User
from attendance_api.models.scores import ScoreItem, ScoreRecord, ScoreSettings
from attendance_api.modules.attendance.service import _iso_timestamp
from attendance_api.modules.audit.service import append_audit
from attendance_api.modules.courses.service import get_owned_class_group
from attendance_api.schemas import scores as schema


def display_decimal(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f")


def rules_ready(settings: schema.ScoreSettings) -> bool:
    return settings.base_score is not None and all(
        value is not None for value in settings.factors.values()
    )


def calculate_summary(
    enrollment_id: str,
    settings: schema.ScoreSettings,
    values: Mapping[str, Sequence[Decimal | None]],
) -> schema.ScoreSummary:
    # Inputs are NUMERIC(20,4); preserve full products and sums until display rounding.
    with localcontext() as context:
        context.prec = 80
        ready = rules_ready(settings)
        categories = []
        raw = settings.base_score or Decimal(0)
        pending_total = 0
        for category in schema.CATEGORIES:
            points = values.get(category, [])
            # An ungraded item contributes the default score of zero while the
            # pending count remains available to signal incomplete evaluation.
            total = sum(
                (point if point is not None else Decimal(0) for point in points), Decimal(0)
            )
            pending = sum(point is None for point in points)
            factor = settings.factors[category]
            contribution = total * factor if factor is not None else None
            # An explicitly disabled category contributes zero even with ungraded records.
            if factor != 0 and pending:
                pending_total += pending
            if contribution is not None:
                raw += contribution
            categories.append(
                schema.ScoreCategorySummary(
                    category=category,
                    points=format(total, "f"),
                    contribution=display_decimal(contribution)
                    if contribution is not None
                    else None,
                    pending=pending,
                )
            )
        status: Literal["RULES_PENDING", "RECORDS_PENDING", "READY"]
        status = "RULES_PENDING" if not ready else "RECORDS_PENDING" if pending_total else "READY"
        return schema.ScoreSummary(
            enrollment_id=enrollment_id,
            categories=categories,
            raw_score=display_decimal(raw) if ready else None,
            final_score=display_decimal(max(Decimal(0), min(Decimal(100), raw)))
            if ready
            else None,
            status=status,
        )


def _settings_response(settings: ScoreSettings | None) -> schema.ScoreSettings:
    return schema.ScoreSettings(
        base_score=settings.base_score if settings else Decimal(70),
        factors={
            category: getattr(settings, f"{category.lower()}_factor") if settings else None
            for category in schema.CATEGORIES
        },
    )


def _item_response(item: ScoreItem) -> schema.ScoreItem:
    return schema.ScoreItem.model_validate(item)


def _record_response(record: ScoreRecord) -> schema.ScoreRecord:
    return schema.ScoreRecord(
        id=record.id,
        item_id=record.item_id,
        enrollment_id=record.enrollment_id,
        points=record.points,
        note=record.note,
        updated_at=_iso_timestamp(record.updated_at) or "",
    )


def get_book(db: Session, *, teacher_id: str, class_group_id: str) -> schema.ScoreBook:
    class_group, course = get_owned_class_group(
        db, teacher_id=teacher_id, class_group_id=class_group_id
    )
    settings = db.scalar(
        select(ScoreSettings).where(ScoreSettings.class_group_id == class_group_id)
    )
    items = list(
        db.scalars(
            select(ScoreItem)
            .where(ScoreItem.class_group_id == class_group_id)
            .order_by(ScoreItem.occurred_on, ScoreItem.created_at, ScoreItem.id)
        )
    )
    roster = db.execute(
        select(Enrollment, Student)
        .join(Student, Student.id == Enrollment.student_id)
        .where(Enrollment.class_group_id == class_group_id)
        .order_by(Student.student_number, Enrollment.id)
    ).all()
    records = list(
        db.scalars(
            select(ScoreRecord)
            .join(ScoreItem, ScoreItem.id == ScoreRecord.item_id)
            .where(ScoreItem.class_group_id == class_group_id)
            .order_by(ScoreRecord.id)
        )
    )
    record_lookup = {(record.enrollment_id, record.item_id): record for record in records}
    rules = _settings_response(settings)
    students = []
    summaries = []
    for enrollment, student in roster:
        students.append(
            schema.ScoreStudent(
                enrollment_id=enrollment.id,
                student_id=student.id,
                student_number=student.student_number,
                student_name=student.name,
                enrollment_status=enrollment.status,
            )
        )
        values: dict[str, list[Decimal | None]] = defaultdict(list)
        for item in items:
            record = record_lookup.get((enrollment.id, item.id))
            # Removed members retain only existing rows; future projects never affect them.
            if enrollment.status == "ACTIVE" or record is not None:
                values[item.category].append(record.points if record else item.default_points)
        summaries.append(calculate_summary(enrollment.id, rules, values))
    return schema.ScoreBook(
        class_group=schema.ScoreScope.model_validate(class_group),
        course=schema.ScoreScope.model_validate(course),
        version=settings.version if settings else 0,
        readonly=class_group.status != "ACTIVE" or course.status != "ACTIVE",
        rules_ready=rules_ready(rules),
        settings=rules,
        items=[_item_response(item) for item in items],
        students=students,
        records=[_record_response(record) for record in records],
        summaries=summaries,
    )


def _lock_book(
    db: Session, teacher: User, class_group_id: str, expected_version: int
) -> ScoreSettings:
    # The class exists even before settings do: lock it to serialize first writes too.
    scope = db.execute(
        select(ClassGroup, Course)
        .join(Course, Course.id == ClassGroup.course_id)
        .where(ClassGroup.id == class_group_id, Course.owner_teacher_id == teacher.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one_or_none()
    if scope is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "班级不存在")
    if scope[0].status != "ACTIVE" or scope[1].status != "ACTIVE":
        raise ApiError(409, "RESOURCE_STATE_CONFLICT", "已归档课程或班级的成绩只读")
    settings = db.scalar(
        select(ScoreSettings)
        .where(ScoreSettings.class_group_id == class_group_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    version = settings.version if settings else 0
    if version != expected_version:
        raise ApiError(
            409,
            "SCORE_VERSION_CONFLICT",
            "成绩已被其他操作更新，请刷新后重新核对",
            {
                "current_version": version,
            },
        )
    if settings is None:
        settings = ScoreSettings(class_group_id=class_group_id, base_score=Decimal(70), version=1)
        db.add(settings)
    else:
        settings.version += 1
    return settings


ScoreMutation = (
    schema.SetScoreSettingsRequest
    | schema.CreateScoreItemRequest
    | schema.UpdateScoreItemRequest
    | schema.SetScoreRecordsRequest
)


def mutate_book(
    db: Session,
    *,
    teacher: User,
    class_group_id: str,
    payload: ScoreMutation,
    ip_address: str,
    request_id: str,
    item_id: str | None = None,
) -> schema.ScoreBook:
    transaction = db.begin_nested()
    try:
        settings = _lock_book(db, teacher, class_group_id, payload.expected_version)

        def audit(action: str, before: dict[str, object] | None, after: dict[str, object]) -> None:
            append_audit(
                db,
                actor_user_id=teacher.id,
                action=action,
                entity_type="score_book",
                entity_id=class_group_id,
                before_value=before,
                after_value=after,
                reason=None,
                ip_address=ip_address,
                request_id=request_id,
            )

        if isinstance(payload, schema.SetScoreSettingsRequest):
            before = _settings_response(settings).model_dump(mode="json")
            settings.base_score = payload.base_score
            for category, factor in payload.factors.items():
                setattr(settings, f"{category.lower()}_factor", factor)
            audit(
                "SCORE_SETTINGS_UPDATED",
                before,
                _settings_response(settings).model_dump(mode="json"),
            )
        elif isinstance(payload, schema.CreateScoreItemRequest):
            created_item = ScoreItem(
                class_group_id=class_group_id,
                category=payload.category,
                name=payload.name,
                occurred_on=payload.occurred_on,
                description=payload.description,
                default_points=payload.default_points,
            )
            db.add(created_item)
            db.flush()
            enrollment_ids = db.scalars(
                select(Enrollment.id)
                .where(Enrollment.class_group_id == class_group_id, Enrollment.status == "ACTIVE")
                .with_for_update()
            ).all()
            db.add_all(
                [
                    ScoreRecord(
                        item_id=created_item.id,
                        enrollment_id=enrollment_id,
                        points=payload.default_points,
                        note="",
                    )
                    for enrollment_id in enrollment_ids
                ]
            )
            audit("SCORE_ITEM_CREATED", None, _item_response(created_item).model_dump(mode="json"))
        else:
            item = db.scalar(
                select(ScoreItem)
                .where(ScoreItem.id == item_id, ScoreItem.class_group_id == class_group_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if item is None:
                raise ApiError(404, "RESOURCE_NOT_FOUND", "评分项目不存在")
            if isinstance(payload, schema.UpdateScoreItemRequest):
                before = _item_response(item).model_dump(mode="json")
                for key, value in payload.model_dump(exclude_unset=True).items():
                    if key != "expected_version":
                        setattr(item, key, value)
                audit("SCORE_ITEM_UPDATED", before, _item_response(item).model_dump(mode="json"))
            else:
                _save_records(db, class_group_id, item, payload, audit)
        db.flush()
        transaction.commit()
        db.commit()
        # Auth may have established a REPEATABLE READ snapshot before the class lock.
        # Read the response in a fresh transaction, clearing ORM identity-map state too.
        teacher_id = teacher.id
        db.expire_all()
        return get_book(db, teacher_id=teacher_id, class_group_id=class_group_id)
    except Exception:
        if transaction.is_active:
            transaction.rollback()
        raise


def _save_records(
    db: Session,
    class_group_id: str,
    item: ScoreItem,
    payload: schema.SetScoreRecordsRequest,
    audit: "AuditCallback",
) -> None:
    enrollment_ids = [record.enrollment_id for record in payload.records]
    enrollments = list(
        db.scalars(
            select(Enrollment)
            .where(Enrollment.id.in_(enrollment_ids), Enrollment.class_group_id == class_group_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )
    if len(enrollments) != len(enrollment_ids):
        raise ApiError(404, "RESOURCE_NOT_FOUND", "名单成员不存在于当前班级")
    if any(enrollment.status != "ACTIVE" for enrollment in enrollments):
        raise ApiError(409, "RESOURCE_STATE_CONFLICT", "已移除学生的历史成绩只读")
    existing = {
        record.enrollment_id: record
        for record in db.scalars(
            select(ScoreRecord)
            .where(ScoreRecord.item_id == item.id, ScoreRecord.enrollment_id.in_(enrollment_ids))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    }
    for change in payload.records:
        record = existing.get(change.enrollment_id)
        before = _record_response(record).model_dump(mode="json") if record else None
        if record is None:
            record = ScoreRecord(item_id=item.id, enrollment_id=change.enrollment_id)
            db.add(record)
        record.points = change.points
        record.note = change.note
        db.flush()
        audit("SCORE_RECORD_UPDATED", before, _record_response(record).model_dump(mode="json"))


AuditCallback = Callable[[str, dict[str, object] | None, dict[str, object]], None]


def get_history(
    db: Session, *, teacher_id: str, class_group_id: str, enrollment_id: str | None
) -> schema.ScoreHistoryResponse:
    get_owned_class_group(db, teacher_id=teacher_id, class_group_id=class_group_id)
    if (
        enrollment_id is not None
        and db.scalar(
            select(Enrollment.id).where(
                Enrollment.id == enrollment_id, Enrollment.class_group_id == class_group_id
            )
        )
        is None
    ):
        raise ApiError(404, "RESOURCE_NOT_FOUND", "名单成员不存在于当前班级")
    query = (
        select(AuditLog, User.display_name)
        .join(User, User.id == AuditLog.actor_user_id)
        .where(AuditLog.entity_type == "score_book", AuditLog.entity_id == class_group_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    )
    rows = db.execute(query).all()
    return schema.ScoreHistoryResponse(
        items=[
            schema.ScoreHistory(
                id=audit.id,
                action=audit.action,
                actor_name=actor_name,
                created_at=_iso_timestamp(audit.created_at) or "",
                before_value=audit.before_value,
                after_value=audit.after_value,
            )
            for audit, actor_name in rows
            if enrollment_id is None
            or (
                audit.action != "SCORE_RECORD_UPDATED"
                or cast(dict[str, object], audit.after_value or {}).get("enrollment_id")
                == enrollment_id
            )
        ]
    )
