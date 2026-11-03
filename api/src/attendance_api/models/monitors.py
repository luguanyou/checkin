from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from attendance_api.models.base import (
    MYSQL_TABLE_OPTIONS,
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class MonitorGrant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "monitor_grants"
    __table_args__ = (
        UniqueConstraint("user_id", "item_id", name="uq_monitor_grants_user_item"),
        MYSQL_TABLE_OPTIONS,
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    item_id: Mapped[str] = mapped_column(ForeignKey("score_items.id", ondelete="CASCADE"))
    granted_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
