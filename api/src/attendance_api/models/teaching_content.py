from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, LargeBinary, String, Text
from sqlalchemy.dialects.mysql import MEDIUMBLOB
from sqlalchemy.orm import Mapped, mapped_column

from attendance_api.models.base import MYSQL_TABLE_OPTIONS, Base, UUIDPrimaryKeyMixin


class TeachingContent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "teaching_content"
    __table_args__ = (Index("ix_teaching_content_course", "course_id"), MYSQL_TABLE_OPTIONS)

    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    chapter: Mapped[str | None] = mapped_column(String(120))
    category: Mapped[str | None] = mapped_column(String(16))
    url: Mapped[str | None] = mapped_column(String(2048))
    due_at: Mapped[datetime | None] = mapped_column(DateTime)
    submission_method: Mapped[str | None] = mapped_column(String(500))
    resource_id: Mapped[str | None] = mapped_column(
        ForeignKey("teaching_content.id", ondelete="SET NULL")
    )
    attachment_name: Mapped[str | None] = mapped_column(String(255))
    attachment: Mapped[bytes | None] = mapped_column(
        LargeBinary().with_variant(MEDIUMBLOB(), "mysql"), deferred=True
    )


class TeachingPublication(Base):
    __tablename__ = "teaching_publications"
    __table_args__ = (Index("ix_teaching_publications_class", "class_id"), MYSQL_TABLE_OPTIONS)

    content_id: Mapped[str] = mapped_column(
        ForeignKey("teaching_content.id", ondelete="CASCADE"), primary_key=True
    )
    class_id: Mapped[str] = mapped_column(
        ForeignKey("class_groups.id", ondelete="CASCADE"), primary_key=True
    )
