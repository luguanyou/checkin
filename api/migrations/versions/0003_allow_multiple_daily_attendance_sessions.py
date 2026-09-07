"""allow multiple daily attendance sessions

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-07 22:45:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_attendance_sessions_class_date",
        "attendance_sessions",
        type_="unique",
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_attendance_sessions_class_date",
        "attendance_sessions",
        ["class_group_id", "session_date"],
    )
