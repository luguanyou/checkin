"""Student accounts and per-class portal visibility.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(op.f("ck_users_role"), "users", type_="check")
    op.create_check_constraint("role", "users", "role IN ('ADMIN', 'TEACHER', 'STUDENT')")
    op.add_column("users", sa.Column("student_id", sa.String(36), nullable=True))
    op.create_foreign_key(
        "fk_users_student_id_students",
        "users",
        "students",
        ["student_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint("uq_users_student_id", "users", ["student_id"])
    op.add_column(
        "class_groups",
        sa.Column("attendance_visible", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "class_groups",
        sa.Column("score_visibility", sa.String(20), nullable=False, server_default="HIDDEN"),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM users WHERE role = 'STUDENT'")):
        raise RuntimeError("Remove student accounts before downgrading")
    # Student users must be removed explicitly before downgrading the role constraint.
    op.drop_column("class_groups", "score_visibility")
    op.drop_column("class_groups", "attendance_visible")
    op.drop_constraint("fk_users_student_id_students", "users", type_="foreignkey")
    op.drop_constraint("uq_users_student_id", "users", type_="unique")
    op.drop_column("users", "student_id")
    op.drop_constraint(op.f("ck_users_role"), "users", type_="check")
    op.create_check_constraint("role", "users", "role IN ('ADMIN', 'TEACHER')")
