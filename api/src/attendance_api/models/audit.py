from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from attendance_api.models.base import (
    MYSQL_TABLE_OPTIONS,
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class AuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        UniqueConstraint("client_mutation_id", name="uq_audit_logs_client_mutation"),
        Index("ix_audit_logs_actor_created", "actor_user_id", "created_at"),
        Index("ix_audit_logs_entity_created", "entity_type", "entity_id", "created_at"),
        Index("ix_audit_logs_request", "request_id"),
        MYSQL_TABLE_OPTIONS,
    )

    actor_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(String(36))
    before_value: Mapped[dict[str, object] | None] = mapped_column(JSON)
    after_value: Mapped[dict[str, object] | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(String(500))
    ip_address: Mapped[str] = mapped_column(String(45))
    request_id: Mapped[str] = mapped_column(String(64))
    client_mutation_id: Mapped[str | None] = mapped_column(String(36))
