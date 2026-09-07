"""repair legacy partial schema

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-05 10:37:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())

    if "courses" not in existing_tables:
        op.create_table(
            "courses",
            sa.Column("owner_teacher_id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("code", sa.String(length=50), nullable=False),
            sa.Column("term", sa.String(length=50), nullable=False),
            sa.Column("status", sa.String(length=20), server_default="ACTIVE", nullable=False),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column(
                "created_at",
                mysql.DATETIME(fsp=6),
                server_default=sa.text("CURRENT_TIMESTAMP(6)"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                mysql.DATETIME(fsp=6),
                server_default=sa.text("CURRENT_TIMESTAMP(6)"),
                nullable=False,
            ),
            sa.CheckConstraint("status IN ('ACTIVE', 'ARCHIVED')", name=op.f("ck_courses_status")),
            sa.ForeignKeyConstraint(
                ["owner_teacher_id"],
                ["users.id"],
                name=op.f("fk_courses_owner_teacher_id_users"),
                onupdate="RESTRICT",
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_courses")),
            sa.UniqueConstraint(
                "owner_teacher_id", "code", "term", name="uq_courses_owner_code_term"
            ),
            mysql_charset="utf8mb4",
            mysql_engine="InnoDB",
        )
        op.create_index(
            "ix_courses_owner_status", "courses", ["owner_teacher_id", "status"], unique=False
        )

    if "login_sessions" not in existing_tables:
        op.create_table(
            "login_sessions",
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
            sa.Column("expires_at", mysql.DATETIME(fsp=6), nullable=False),
            sa.Column("revoked_at", mysql.DATETIME(fsp=6), nullable=True),
            sa.Column("last_used_at", mysql.DATETIME(fsp=6), nullable=False),
            sa.Column("ip_address", sa.String(length=45), nullable=False),
            sa.Column("user_agent", sa.String(length=255), nullable=False),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column(
                "created_at",
                mysql.DATETIME(fsp=6),
                server_default=sa.text("CURRENT_TIMESTAMP(6)"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                mysql.DATETIME(fsp=6),
                server_default=sa.text("CURRENT_TIMESTAMP(6)"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                name=op.f("fk_login_sessions_user_id_users"),
                onupdate="RESTRICT",
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_login_sessions")),
            sa.UniqueConstraint(
                "refresh_token_hash", name=op.f("uq_login_sessions_refresh_token_hash")
            ),
            mysql_charset="utf8mb4",
            mysql_engine="InnoDB",
        )
        op.create_index(
            "ix_login_sessions_user_active",
            "login_sessions",
            ["user_id", "revoked_at", "expires_at"],
            unique=False,
        )

    if "class_groups" not in existing_tables:
        op.create_table(
            "class_groups",
            sa.Column("course_id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("status", sa.String(length=20), server_default="ACTIVE", nullable=False),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column(
                "created_at",
                mysql.DATETIME(fsp=6),
                server_default=sa.text("CURRENT_TIMESTAMP(6)"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                mysql.DATETIME(fsp=6),
                server_default=sa.text("CURRENT_TIMESTAMP(6)"),
                nullable=False,
            ),
            sa.CheckConstraint(
                "status IN ('ACTIVE', 'ARCHIVED')", name=op.f("ck_class_groups_status")
            ),
            sa.ForeignKeyConstraint(
                ["course_id"],
                ["courses.id"],
                name=op.f("fk_class_groups_course_id_courses"),
                onupdate="RESTRICT",
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_class_groups")),
            sa.UniqueConstraint("course_id", "name", name="uq_class_groups_course_name"),
            mysql_charset="utf8mb4",
            mysql_engine="InnoDB",
        )
        op.create_index(
            "ix_class_groups_course_status",
            "class_groups",
            ["course_id", "status"],
            unique=False,
        )

    if "attendance_sessions" not in existing_tables:
        op.create_table(
            "attendance_sessions",
            sa.Column("class_group_id", sa.String(length=36), nullable=False),
            sa.Column("session_date", sa.Date(), nullable=False),
            sa.Column("status", sa.String(length=20), server_default="DRAFT", nullable=False),
            sa.Column("started_at", mysql.DATETIME(fsp=6), nullable=False),
            sa.Column("completed_at", mysql.DATETIME(fsp=6), nullable=True),
            sa.Column("created_by", sa.String(length=36), nullable=False),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column(
                "created_at",
                mysql.DATETIME(fsp=6),
                server_default=sa.text("CURRENT_TIMESTAMP(6)"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                mysql.DATETIME(fsp=6),
                server_default=sa.text("CURRENT_TIMESTAMP(6)"),
                nullable=False,
            ),
            sa.CheckConstraint(
                "(status = 'DRAFT' AND completed_at IS NULL) OR "
                "(status = 'COMPLETED' AND completed_at IS NOT NULL)",
                name=op.f("ck_attendance_sessions_completion_state"),
            ),
            sa.CheckConstraint(
                "status IN ('DRAFT', 'COMPLETED')",
                name=op.f("ck_attendance_sessions_status"),
            ),
            sa.ForeignKeyConstraint(
                ["class_group_id"],
                ["class_groups.id"],
                name=op.f("fk_attendance_sessions_class_group_id_class_groups"),
                onupdate="RESTRICT",
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["created_by"],
                ["users.id"],
                name=op.f("fk_attendance_sessions_created_by_users"),
                onupdate="RESTRICT",
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_attendance_sessions")),
            sa.UniqueConstraint(
                "class_group_id",
                "session_date",
                name="uq_attendance_sessions_class_date",
            ),
            mysql_charset="utf8mb4",
            mysql_engine="InnoDB",
        )
        op.create_index(
            "ix_attendance_sessions_class_status_date",
            "attendance_sessions",
            ["class_group_id", "status", "session_date"],
            unique=False,
        )
        op.create_index(
            "ix_attendance_sessions_creator_date",
            "attendance_sessions",
            ["created_by", "session_date"],
            unique=False,
        )

    if "enrollments" not in existing_tables:
        op.create_table(
            "enrollments",
            sa.Column("class_group_id", sa.String(length=36), nullable=False),
            sa.Column("student_id", sa.String(length=36), nullable=False),
            sa.Column("status", sa.String(length=20), server_default="ACTIVE", nullable=False),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column(
                "created_at",
                mysql.DATETIME(fsp=6),
                server_default=sa.text("CURRENT_TIMESTAMP(6)"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                mysql.DATETIME(fsp=6),
                server_default=sa.text("CURRENT_TIMESTAMP(6)"),
                nullable=False,
            ),
            sa.CheckConstraint(
                "status IN ('ACTIVE', 'REMOVED')", name=op.f("ck_enrollments_status")
            ),
            sa.ForeignKeyConstraint(
                ["class_group_id"],
                ["class_groups.id"],
                name=op.f("fk_enrollments_class_group_id_class_groups"),
                onupdate="RESTRICT",
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["student_id"],
                ["students.id"],
                name=op.f("fk_enrollments_student_id_students"),
                onupdate="RESTRICT",
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_enrollments")),
            sa.UniqueConstraint(
                "class_group_id", "student_id", name="uq_enrollments_class_student"
            ),
            mysql_charset="utf8mb4",
            mysql_engine="InnoDB",
        )
        op.create_index(
            "ix_enrollments_class_status",
            "enrollments",
            ["class_group_id", "status"],
            unique=False,
        )
        op.create_index("ix_enrollments_student", "enrollments", ["student_id"], unique=False)

    if "import_previews" not in existing_tables:
        op.create_table(
            "import_previews",
            sa.Column("class_group_id", sa.String(length=36), nullable=False),
            sa.Column("created_by", sa.String(length=36), nullable=False),
            sa.Column("source_filename", sa.String(length=255), nullable=False),
            sa.Column("normalized_rows", mysql.JSON(), nullable=False),
            sa.Column("validation_result", mysql.JSON(), nullable=False),
            sa.Column("expires_at", mysql.DATETIME(fsp=6), nullable=False),
            sa.Column("confirmed_at", mysql.DATETIME(fsp=6), nullable=True),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column(
                "created_at",
                mysql.DATETIME(fsp=6),
                server_default=sa.text("CURRENT_TIMESTAMP(6)"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                mysql.DATETIME(fsp=6),
                server_default=sa.text("CURRENT_TIMESTAMP(6)"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["class_group_id"],
                ["class_groups.id"],
                name=op.f("fk_import_previews_class_group_id_class_groups"),
                onupdate="RESTRICT",
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["created_by"],
                ["users.id"],
                name=op.f("fk_import_previews_created_by_users"),
                onupdate="RESTRICT",
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_import_previews")),
            mysql_charset="utf8mb4",
            mysql_engine="InnoDB",
        )
        op.create_index(
            "ix_import_previews_class_expiry",
            "import_previews",
            ["class_group_id", "expires_at"],
            unique=False,
        )
        op.create_index(
            "ix_import_previews_owner_expiry",
            "import_previews",
            ["created_by", "expires_at"],
            unique=False,
        )

    if "attendance_records" not in existing_tables:
        op.create_table(
            "attendance_records",
            sa.Column("session_id", sa.String(length=36), nullable=False),
            sa.Column("student_id", sa.String(length=36), nullable=False),
            sa.Column("student_number_snapshot", sa.String(length=50), nullable=False),
            sa.Column("student_name_snapshot", sa.String(length=100), nullable=False),
            sa.Column("class_name_snapshot", sa.String(length=120), nullable=False),
            sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
            sa.Column("marked_at", mysql.DATETIME(fsp=6), nullable=True),
            sa.Column("last_modified_by", sa.String(length=36), nullable=False),
            sa.Column("last_modified_at", mysql.DATETIME(fsp=6), nullable=True),
            sa.Column("version", mysql.INTEGER(unsigned=True), server_default="1", nullable=False),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column(
                "created_at",
                mysql.DATETIME(fsp=6),
                server_default=sa.text("CURRENT_TIMESTAMP(6)"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                mysql.DATETIME(fsp=6),
                server_default=sa.text("CURRENT_TIMESTAMP(6)"),
                nullable=False,
            ),
            sa.CheckConstraint(
                "(status = 'pending' AND marked_at IS NULL) OR "
                "(status <> 'pending' AND marked_at IS NOT NULL)",
                name=op.f("ck_attendance_records_marked_state"),
            ),
            sa.CheckConstraint(
                "status IN ('pending', 'present', 'absent', 'leave', 'late')",
                name=op.f("ck_attendance_records_status"),
            ),
            sa.CheckConstraint("version >= 1", name=op.f("ck_attendance_records_version_positive")),
            sa.ForeignKeyConstraint(
                ["last_modified_by"],
                ["users.id"],
                name=op.f("fk_attendance_records_last_modified_by_users"),
                onupdate="RESTRICT",
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["session_id"],
                ["attendance_sessions.id"],
                name=op.f("fk_attendance_records_session_id_attendance_sessions"),
                onupdate="RESTRICT",
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["student_id"],
                ["students.id"],
                name=op.f("fk_attendance_records_student_id_students"),
                onupdate="RESTRICT",
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_attendance_records")),
            sa.UniqueConstraint(
                "session_id",
                "student_id",
                name="uq_attendance_records_session_student",
            ),
            mysql_charset="utf8mb4",
            mysql_engine="InnoDB",
        )
        op.create_index(
            "ix_attendance_records_session_status",
            "attendance_records",
            ["session_id", "status"],
            unique=False,
        )
        op.create_index(
            "ix_attendance_records_student",
            "attendance_records",
            ["student_id"],
            unique=False,
        )


def downgrade() -> None:
    # This revision repairs schemas already stamped as 0001. The canonical 0001
    # migration contains these tables, so reverting the repair must retain them.
    pass
