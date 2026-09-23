from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from attendance_api.errors import ApiError
from attendance_api.models import (
    AuditLog,
    ClassGroup,
    Course,
    ScoreItem,
    ScoreRecord,
    ScoreSettings,
    User,
)
from attendance_api.modules.scores.service import get_book, mutate_book
from attendance_api.schemas.scores import CreateScoreItemRequest, SetScoreSettingsRequest


@pytest.fixture
def committed_scope(engine):
    """Independent committed fixture for real MySQL transactions; remove only its own rows."""
    with Session(engine, expire_on_commit=False) as db:
        teacher = User(
            username=f"score-race-{uuid4()}",
            password_hash="not-used",
            display_name="Concurrency",
            role="TEACHER",
            status="ACTIVE",
            must_change_password=False,
        )
        db.add(teacher)
        db.flush()
        course = Course(
            owner_teacher_id=teacher.id,
            name="Concurrency",
            code=str(uuid4()),
            term="test",
            status="ACTIVE",
        )
        db.add(course)
        db.flush()
        group = ClassGroup(course_id=course.id, name="Race", status="ACTIVE")
        db.add(group)
        db.commit()
        teacher_id, course_id, group_id = teacher.id, course.id, group.id
    try:
        yield teacher_id, group_id
    finally:
        with Session(engine) as db:
            item_ids = select(ScoreItem.id).where(ScoreItem.class_group_id == group_id)
            db.execute(delete(ScoreRecord).where(ScoreRecord.item_id.in_(item_ids)))
            db.execute(delete(ScoreItem).where(ScoreItem.class_group_id == group_id))
            db.execute(delete(ScoreSettings).where(ScoreSettings.class_group_id == group_id))
            db.execute(delete(AuditLog).where(AuditLog.actor_user_id == teacher_id))
            db.execute(delete(ClassGroup).where(ClassGroup.id == group_id))
            db.execute(delete(Course).where(Course.id == course_id))
            db.execute(delete(User).where(User.id == teacher_id))
            db.commit()


def test_simultaneous_initial_settings_writes_have_one_winner(engine, committed_scope) -> None:
    teacher_id, group_id = committed_scope
    barrier = Barrier(2)

    def save(base: str) -> str:
        with Session(engine, expire_on_commit=False) as db:
            # This read deliberately establishes an old snapshot before acquiring the lock.
            teacher = db.scalar(select(User).where(User.id == teacher_id))
            barrier.wait(timeout=10)
            try:
                mutate_book(
                    db,
                    teacher=teacher,
                    class_group_id=group_id,
                    payload=SetScoreSettingsRequest(
                        expected_version=0,
                        base_score=base,
                        factors={c: "1" for c in ("HOMEWORK", "CLASSROOM", "LAB", "OTHER")},
                    ),
                    ip_address="test",
                    request_id=str(uuid4()),
                )
                return "SAVED"
            except ApiError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, ["70", "80"]))
    assert sorted(results) == ["SAVED", "SCORE_VERSION_CONFLICT"]
    with Session(engine) as db:
        book = get_book(db, teacher_id=teacher_id, class_group_id=group_id)
        assert book.version == 1
        assert str(book.settings.base_score) in {"70.0000", "80.0000"}
        audits = list(db.scalars(select(AuditLog).where(AuditLog.entity_id == group_id)))
        assert len(audits) == 1


def test_mutation_response_reads_new_snapshot_after_waiting_on_class(
    engine, committed_scope
) -> None:
    teacher_id, group_id = committed_scope
    with Session(engine, expire_on_commit=False) as old_snapshot:
        teacher = old_snapshot.scalar(select(User).where(User.id == teacher_id))
        assert get_book(old_snapshot, teacher_id=teacher_id, class_group_id=group_id).version == 0
        with Session(engine, expire_on_commit=False) as other:
            other_teacher = other.get(User, teacher_id)
            mutate_book(
                other,
                teacher=other_teacher,
                class_group_id=group_id,
                payload=CreateScoreItemRequest(
                    expected_version=0,
                    category="HOMEWORK",
                    name="First",
                    occurred_on=date(2026, 9, 22),
                ),
                ip_address="test",
                request_id=str(uuid4()),
            )
        book = mutate_book(
            old_snapshot,
            teacher=teacher,
            class_group_id=group_id,
            payload=CreateScoreItemRequest(
                expected_version=1, category="LAB", name="Second", occurred_on=date(2026, 9, 22)
            ),
            ip_address="test",
            request_id=str(uuid4()),
        )
        assert book.version == 2
        assert {item.name for item in book.items} == {"First", "Second"}
