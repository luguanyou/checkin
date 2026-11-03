"""Self-service student registrations and class-scoped reviewers.
Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def timestamps():
    return [
        sa.Column(
            name,
            mysql.DATETIME(fsp=6),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
        )
        for name in ("created_at", "updated_at")
    ]


def upgrade() -> None:
    op.create_table(
        "student_registrations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "student_id",
            sa.String(36),
            sa.ForeignKey("students.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "class_group_id",
            sa.String(36),
            sa.ForeignKey("class_groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("password_hash", sa.String(255)),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("reviewed_by", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("review_reason", sa.String(500)),
        *timestamps(),
        sa.UniqueConstraint("student_id", name="uq_student_registrations_student_id"),
        sa.CheckConstraint("status IN ('PENDING','APPROVED','REJECTED')", name="status"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_student_registrations_class_group_id", "student_registrations", ["class_group_id"]
    )
    op.create_table(
        "registration_reviewers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "class_group_id",
            sa.String(36),
            sa.ForeignKey("class_groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "granted_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        *timestamps(),
        sa.UniqueConstraint(
            "class_group_id", "user_id", name="uq_registration_reviewers_class_user"
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )


def downgrade() -> None:
    op.drop_table("registration_reviewers")
    op.drop_table("student_registrations")
