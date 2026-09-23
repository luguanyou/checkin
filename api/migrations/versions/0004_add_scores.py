"""Add independent class score settings, projects and enrollment records.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:  # type: ignore[type-arg]
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
        "score_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "class_group_id",
            sa.String(36),
            sa.ForeignKey("class_groups.id", ondelete="RESTRICT", onupdate="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("base_score", sa.Numeric(20, 4), nullable=True),
        *(
            sa.Column(f"{category}_factor", sa.Numeric(20, 4), nullable=True)
            for category in ("homework", "classroom", "lab", "other")
        ),
        *_timestamps(),
        sa.UniqueConstraint("class_group_id", name="uq_score_settings_class_group_id"),
        sa.CheckConstraint("version >= 1", name="version_positive"),
        *(
            sa.CheckConstraint(f"{category}_factor >= 0", name=f"{category}_factor_nonnegative")
            for category in ("homework", "classroom", "lab", "other")
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_table(
        "score_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "class_group_id",
            sa.String(36),
            sa.ForeignKey("class_groups.id", ondelete="RESTRICT", onupdate="RESTRICT"),
            nullable=False,
        ),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("category IN ('HOMEWORK','CLASSROOM','LAB','OTHER')", name="category"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_score_items_class_date", "score_items", ["class_group_id", "occurred_on"])
    op.create_table(
        "score_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "item_id",
            sa.String(36),
            sa.ForeignKey("score_items.id", ondelete="RESTRICT", onupdate="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "enrollment_id",
            sa.String(36),
            sa.ForeignKey("enrollments.id", ondelete="RESTRICT", onupdate="RESTRICT"),
            nullable=False,
        ),
        sa.Column("points", sa.Numeric(20, 4), nullable=True),
        sa.Column("note", sa.String(500), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("item_id", "enrollment_id", name="uq_score_records_item_enrollment"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_score_records_enrollment", "score_records", ["enrollment_id"])


def downgrade() -> None:
    op.drop_table("score_records")
    op.drop_table("score_items")
    op.drop_table("score_settings")
