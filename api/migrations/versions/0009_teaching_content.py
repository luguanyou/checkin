"""Add class publications for course materials and assignments."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import MEDIUMBLOB

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "teaching_content",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "course_id",
            sa.String(36),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("chapter", sa.String(120)),
        sa.Column("category", sa.String(16)),
        sa.Column("url", sa.String(2048)),
        sa.Column("due_at", sa.DateTime()),
        sa.Column("submission_method", sa.String(500)),
        sa.Column(
            "resource_id", sa.String(36), sa.ForeignKey("teaching_content.id", ondelete="SET NULL")
        ),
        sa.Column("attachment_name", sa.String(255)),
        sa.Column("attachment", sa.LargeBinary().with_variant(MEDIUMBLOB(), "mysql")),
        sa.Index("ix_teaching_content_course", "course_id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_table(
        "teaching_publications",
        sa.Column(
            "content_id",
            sa.String(36),
            sa.ForeignKey("teaching_content.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "class_id",
            sa.String(36),
            sa.ForeignKey("class_groups.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Index("ix_teaching_publications_class", "class_id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )


def downgrade() -> None:
    op.drop_table("teaching_publications")
    op.drop_table("teaching_content")
