from datetime import datetime

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.mysql import DATETIME, JSON
from sqlalchemy.orm import Mapped, mapped_column

from attendance_api.models.base import (
    MYSQL_TABLE_OPTIONS,
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class ImportPreview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "import_previews"
    __table_args__ = (
        Index("ix_import_previews_owner_expiry", "created_by", "expires_at"),
        Index("ix_import_previews_class_expiry", "class_group_id", "expires_at"),
        MYSQL_TABLE_OPTIONS,
    )

    class_group_id: Mapped[str] = mapped_column(
        ForeignKey("class_groups.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    created_by: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    source_filename: Mapped[str] = mapped_column(String(255))
    normalized_rows: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    validation_result: Mapped[dict[str, object]] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6))
    confirmed_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
