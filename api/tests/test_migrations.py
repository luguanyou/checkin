from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

EXPECTED_TABLES = {
    "users",
    "login_sessions",
    "courses",
    "class_groups",
    "students",
    "enrollments",
    "import_previews",
    "attendance_sessions",
    "attendance_records",
    "audit_logs",
    "alembic_version",
}


def test_initial_migration_creates_all_tables(engine: Engine) -> None:
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES


def test_attendance_constraints_exist(engine: Engine) -> None:
    inspector = inspect(engine)
    session_unique_names = {
        item["name"] for item in inspector.get_unique_constraints("attendance_sessions")
    }
    assert "uq_attendance_sessions_class_date" not in session_unique_names
    unique_names = {item["name"] for item in inspector.get_unique_constraints("attendance_records")}
    assert "uq_attendance_records_session_student" in unique_names
    index_names = {item["name"] for item in inspector.get_indexes("attendance_records")}
    assert "ix_attendance_records_session_status" in index_names


def test_initial_migration_round_trip(engine: Engine) -> None:
    config = Config("alembic.ini")

    command.downgrade(config, "base")
    assert not (set(inspect(engine).get_table_names()) - {"alembic_version"})

    command.upgrade(config, "head")
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES


def test_upgrade_repairs_legacy_partial_0001_schema(engine: Engine) -> None:
    config = Config("alembic.ini")
    command.downgrade(config, "0001")

    missing_from_legacy_schema = [
        "attendance_records",
        "import_previews",
        "enrollments",
        "attendance_sessions",
        "class_groups",
        "login_sessions",
        "courses",
    ]
    with engine.begin() as connection:
        for table_name in missing_from_legacy_schema:
            connection.execute(text(f"DROP TABLE IF EXISTS {table_name}"))

    assert set(inspect(engine).get_table_names()) == {
        "users",
        "students",
        "audit_logs",
        "alembic_version",
    }

    command.upgrade(config, "head")

    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES
