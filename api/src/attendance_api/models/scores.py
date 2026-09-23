from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from attendance_api.models.base import (
    MYSQL_TABLE_OPTIONS,
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class ScoreSettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "score_settings"
    __table_args__ = (
        CheckConstraint("version >= 1", name="version_positive"),
        *(
            CheckConstraint(f"{category}_factor >= 0", name=f"{category}_factor_nonnegative")
            for category in ("homework", "classroom", "lab", "other")
        ),
        MYSQL_TABLE_OPTIONS,
    )

    class_group_id: Mapped[str] = mapped_column(
        ForeignKey("class_groups.id", ondelete="RESTRICT", onupdate="RESTRICT"), unique=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    base_score: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    homework_factor: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    classroom_factor: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    lab_factor: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    other_factor: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))


class ScoreItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "score_items"
    __table_args__ = (
        CheckConstraint("category IN ('HOMEWORK','CLASSROOM','LAB','OTHER')", name="category"),
        Index("ix_score_items_class_date", "class_group_id", "occurred_on"),
        MYSQL_TABLE_OPTIONS,
    )

    class_group_id: Mapped[str] = mapped_column(
        ForeignKey("class_groups.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    category: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    occurred_on: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(500), default="")
    default_points: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))


class ScoreRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "score_records"
    __table_args__ = (
        UniqueConstraint("item_id", "enrollment_id", name="uq_score_records_item_enrollment"),
        Index("ix_score_records_enrollment", "enrollment_id"),
        MYSQL_TABLE_OPTIONS,
    )

    item_id: Mapped[str] = mapped_column(
        ForeignKey("score_items.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    enrollment_id: Mapped[str] = mapped_column(
        ForeignKey("enrollments.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    points: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    note: Mapped[str] = mapped_column(String(500), default="")
