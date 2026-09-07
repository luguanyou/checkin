# Attendance Backend API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first production-ready FastAPI and MySQL backend for account administration, authentication, courses, rosters, attendance, audit, and single-session exports.

**Architecture:** Add an isolated `api/` Python package beside the existing static prototype. The service is a FastAPI modular monolith with synchronous SQLAlchemy 2 repositories, explicit service-layer transactions, Alembic migrations, and a MySQL 8 database. OpenAPI is the frontend contract; teaching resources are scoped through the owning teacher on every query.

**Tech Stack:** Python 3.11+, uv, FastAPI, Pydantic Settings, SQLAlchemy 2, Alembic, PyMySQL, MySQL 8, Argon2id, PyJWT, pandas/openpyxl/xlrd, pytest, httpx, Ruff, mypy, Docker Compose.

**Canonical specifications:**

- `spec/spec-architecture-attendance-system.md`
- `spec/spec-schema-attendance-database.md`
- `spec/spec-design-attendance-api.md`

**Repository note:** The current workspace is not a Git repository. Commit checkpoints are intentionally omitted. Initialize version control separately before implementation if commits are required.

---

## File Structure

```text
api/
├── .env.example
├── Dockerfile
├── compose.test.yaml
├── pyproject.toml
├── uv.lock
├── alembic.ini
├── migrations/
│   ├── env.py
│   └── versions/0001_initial_schema.py
├── src/attendance_api/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── db.py
│   ├── errors.py
│   ├── cli.py
│   ├── middleware/request_id.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── users.py
│   │   ├── teaching.py
│   │   ├── imports.py
│   │   ├── attendance.py
│   │   └── audit.py
│   ├── schemas/
│   │   ├── common.py
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── courses.py
│   │   ├── rosters.py
│   │   └── attendance.py
│   ├── security/
│   │   ├── passwords.py
│   │   └── tokens.py
│   └── modules/
│       ├── auth/{router.py,service.py,dependencies.py}
│       ├── users/{router.py,service.py}
│       ├── courses/{router.py,service.py}
│       ├── rosters/{router.py,service.py}
│       ├── imports/{router.py,service.py,parser.py}
│       ├── attendance/{router.py,service.py}
│       ├── exports/{router.py,service.py}
│       └── audit/service.py
└── tests/
    ├── conftest.py
    ├── test_health.py
    ├── test_migrations.py
    ├── auth/test_auth_api.py
    ├── users/test_admin_users_api.py
    ├── courses/test_courses_api.py
    ├── rosters/test_roster_api.py
    ├── imports/test_import_api.py
    ├── attendance/test_sessions_api.py
    ├── attendance/test_records_api.py
    ├── exports/test_export_api.py
    └── contract/test_openapi.py
```

Each `modules/*/service.py` owns its transaction and business rules. Routers validate transport data and map service results. SQLAlchemy models define persistence only; they do not authorize requests or serialize API responses.

---

### Task 1: Scaffold the API and Health Endpoints

**Files:**
- Create: `api/pyproject.toml`
- Create: `api/.env.example`
- Create: `api/src/attendance_api/__init__.py`
- Create: `api/src/attendance_api/config.py`
- Create: `api/src/attendance_api/main.py`
- Create: `api/tests/test_health.py`

- [ ] **Step 1: Write the failing health tests**

```python
# api/tests/test_health.py
from fastapi.testclient import TestClient

from attendance_api.main import create_app


def test_live_does_not_require_auth() -> None:
    response = TestClient(create_app()).get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_uses_api_title_and_version() -> None:
    schema = TestClient(create_app()).get("/openapi.json").json()
    assert schema["info"]["title"] == "智能课堂考勤 API"
    assert schema["info"]["version"] == "1.0.0"
```

- [ ] **Step 2: Create the package manifest and install dependencies**

```toml
# api/pyproject.toml
[project]
name = "attendance-api"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115,<1",
  "uvicorn[standard]>=0.34,<1",
  "pydantic-settings>=2.7,<3",
  "sqlalchemy>=2.0,<3",
  "alembic>=1.14,<2",
  "pymysql>=1.1,<2",
  "argon2-cffi>=23,<26",
  "pyjwt[crypto]>=2.10,<3",
  "python-multipart>=0.0.20,<1",
  "pandas>=2.2,<4",
  "openpyxl>=3.1,<4",
  "xlrd>=2.0,<3",
]

[dependency-groups]
dev = [
  "httpx>=0.28,<1",
  "pytest>=8.3,<10",
  "pytest-cov>=6,<8",
  "ruff>=0.9,<1",
  "mypy>=1.14,<2",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/attendance_api"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q --strict-markers"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]

[tool.mypy]
python_version = "3.11"
strict = true
packages = ["attendance_api"]
```

Run: `cd api; uv sync --group dev`

Expected: dependencies install and `api/uv.lock` is created.

- [ ] **Step 3: Run the health test and verify it fails**

Run: `cd api; uv run pytest tests/test_health.py -q`

Expected: FAIL because `attendance_api.main` does not exist.

- [ ] **Step 4: Implement settings and the application factory**

```python
# api/src/attendance_api/config.py
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "mysql+pymysql://attendance:attendance@localhost:3306/attendance"
    jwt_secret: SecretStr = SecretStr("development-secret-change-before-deploy")
    jwt_algorithm: str = "HS256"
    frontend_origin: str = "https://localhost"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 604800

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

```python
# api/src/attendance_api/main.py
from fastapi import APIRouter, FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="智能课堂考勤 API", version="1.0.0")
    health = APIRouter(prefix="/api/v1/health", tags=["health"])

    @health.get("/live", operation_id="getHealthLive")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(health)
    return app


app = create_app()
```

`.env.example` must contain `DATABASE_URL`, a 32-byte-or-longer `JWT_SECRET`, `FRONTEND_ORIGIN`, and no real credential values.

- [ ] **Step 5: Verify the scaffold**

Run: `cd api; uv run pytest tests/test_health.py -q; uv run ruff check .; uv run mypy src`

Expected: 2 tests pass; Ruff and mypy exit 0.

---

### Task 2: Add MySQL Test Infrastructure and the Initial Migration

**Files:**
- Create: `api/compose.test.yaml`
- Create: `api/alembic.ini`
- Create: `api/migrations/env.py`
- Create: `api/migrations/versions/0001_initial_schema.py`
- Create: `api/src/attendance_api/db.py`
- Create: `api/src/attendance_api/models/base.py`
- Create: `api/src/attendance_api/models/users.py`
- Create: `api/src/attendance_api/models/teaching.py`
- Create: `api/src/attendance_api/models/imports.py`
- Create: `api/src/attendance_api/models/attendance.py`
- Create: `api/src/attendance_api/models/audit.py`
- Create: `api/src/attendance_api/models/__init__.py`
- Create: `api/tests/conftest.py`
- Create: `api/tests/test_migrations.py`

- [ ] **Step 1: Start a disposable MySQL 8 test database**

```yaml
# api/compose.test.yaml
services:
  mysql:
    image: mysql:8.4
    environment:
      MYSQL_DATABASE: attendance_test
      MYSQL_USER: attendance
      MYSQL_PASSWORD: attendance
      MYSQL_ROOT_PASSWORD: root-test-only
      TZ: UTC
    ports:
      - "33306:3306"
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-uroot", "-proot-test-only"]
      interval: 2s
      timeout: 3s
      retries: 30
```

Run: `cd api; docker compose -f compose.test.yaml up -d --wait`

Expected: the `mysql` service reports healthy on port 33306.

- [ ] **Step 2: Write failing schema assertions**

```python
# api/tests/test_migrations.py
from sqlalchemy import inspect


EXPECTED_TABLES = {
    "users", "login_sessions", "courses", "class_groups", "students",
    "enrollments", "import_previews", "attendance_sessions",
    "attendance_records", "audit_logs", "alembic_version",
}


def test_initial_migration_creates_all_tables(engine) -> None:
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES


def test_attendance_constraints_exist(engine) -> None:
    inspector = inspect(engine)
    unique_names = {
        item["name"] for item in inspector.get_unique_constraints("attendance_records")
    }
    assert "uq_attendance_records_session_student" in unique_names
    index_names = {item["name"] for item in inspector.get_indexes("attendance_records")}
    assert "ix_attendance_records_session_status" in index_names
```

- [ ] **Step 3: Run the migration tests and verify they fail**

Run: `$env:DATABASE_URL='mysql+pymysql://attendance:attendance@127.0.0.1:33306/attendance_test'; cd api; uv run pytest tests/test_migrations.py -q`

Expected: FAIL because the database and model infrastructure are not defined.

- [ ] **Step 4: Implement the database session boundary**

```python
# api/src/attendance_api/db.py
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from attendance_api.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True, pool_recycle=1800)
SessionFactory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionFactory() as session:
        yield session
```

Define a SQLAlchemy 2 `DeclarativeBase` with UUID string and UTC timestamp mixins. Create all ten models with field types, checks, foreign keys, unique constraints, and named indexes exactly as specified in `spec/spec-schema-attendance-database.md` sections 4.2 through 4.11. Use named `CheckConstraint` objects for persisted status values so migrations and tests see stable constraint names.

- [ ] **Step 5: Write the complete initial migration**

`0001_initial_schema.py` must create tables in this order:

```text
users
login_sessions
courses
class_groups
students
enrollments
import_previews
attendance_sessions
attendance_records
audit_logs
```

The downgrade must drop them in reverse order. Use named constraints from the schema specification so tests can assert them. Configure `migrations/env.py` with `Base.metadata` and the URL from `Settings`.

- [ ] **Step 6: Apply and verify the migration**

Run: `$env:DATABASE_URL='mysql+pymysql://attendance:attendance@127.0.0.1:33306/attendance_test'; cd api; uv run alembic upgrade head; uv run pytest tests/test_migrations.py -q`

Expected: migration succeeds and both tests pass.

---

### Task 3: Add Uniform Errors, Request IDs, and Database Readiness

**Files:**
- Create: `api/src/attendance_api/errors.py`
- Create: `api/src/attendance_api/middleware/request_id.py`
- Modify: `api/src/attendance_api/main.py`
- Modify: `api/tests/test_health.py`
- Create: `api/tests/test_errors.py`

- [ ] **Step 1: Write failing response-contract tests**

```python
def test_unknown_route_uses_uniform_error(client) -> None:
    response = client.get("/api/v1/not-found", headers={"X-Request-ID": "req_test"})
    assert response.status_code == 404
    assert response.headers["X-Request-ID"] == "req_test"
    assert response.json() == {
        "code": "RESOURCE_NOT_FOUND",
        "message": "请求的资源不存在",
        "details": {},
        "request_id": "req_test",
    }


def test_ready_checks_database(client) -> None:
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
```

- [ ] **Step 2: Run tests and verify failure**

Run: `cd api; uv run pytest tests/test_errors.py tests/test_health.py -q`

Expected: FAIL because request middleware, error handlers, and readiness are missing.

- [ ] **Step 3: Implement error and request contracts**

```python
# api/src/attendance_api/errors.py
from typing import Any


class ApiError(Exception):
    def __init__(
        self, status_code: int, code: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
```

Middleware must accept `X-Request-ID` only when it is 1 to 64 printable ASCII characters; otherwise generate `req_` plus a UUID hex value. Register handlers for `ApiError`, request validation, Starlette 404, and unhandled exceptions. All business errors must have `{code,message,details,request_id}` and the response header must match.

Readiness must execute `SELECT 1` and compare the current Alembic revision to the expected head. Database failure or revision mismatch returns `503 {"status":"not_ready"}` without internal details.

- [ ] **Step 4: Verify error behavior**

Run: `cd api; uv run pytest tests/test_errors.py tests/test_health.py -q`

Expected: all response-contract and health tests pass.

---

### Task 4: Implement Passwords, JWTs, Login Sessions, and Auth APIs

**Files:**
- Create: `api/src/attendance_api/security/passwords.py`
- Create: `api/src/attendance_api/security/tokens.py`
- Create: `api/src/attendance_api/schemas/common.py`
- Create: `api/src/attendance_api/schemas/auth.py`
- Create: `api/src/attendance_api/modules/auth/dependencies.py`
- Create: `api/src/attendance_api/modules/auth/service.py`
- Create: `api/src/attendance_api/modules/auth/router.py`
- Modify: `api/src/attendance_api/main.py`
- Create: `api/tests/auth/test_auth_api.py`

- [ ] **Step 1: Write failing authentication tests**

Start with the complete login contract test:

```python
def test_login_sets_secure_refresh_cookie_and_returns_access_token(client, teacher) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": teacher.username, "password": teacher.plaintext_password},
    )
    assert response.status_code == 200
    assert response.json()["expires_in"] == 900
    assert response.json()["user"]["id"] == teacher.id
    cookie = response.headers["set-cookie"]
    assert "refresh_token=" in cookie
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/api/v1/auth" in cookie
```

Add separate tests asserting: unknown user, bad password, and disabled user have the same `INVALID_CREDENTIALS` response; refresh rotates the database hash and rejects the old Cookie; wrong `Origin` returns `INVALID_ORIGIN`; `/auth/me` omits all sensitive fields; a temporary-password token receives `PASSWORD_CHANGE_REQUIRED` from `/courses`; password change clears the flag, rotates the current session, and revokes other sessions; two logout calls both return 204 and clear the Cookie.

- [ ] **Step 2: Run tests and verify failure**

Run: `cd api; uv run pytest tests/auth/test_auth_api.py -q`

Expected: FAIL because auth routes and security services are absent.

- [ ] **Step 3: Implement cryptographic helpers**

```python
# api/src/attendance_api/security/passwords.py
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, candidate: str) -> bool:
    try:
        return _hasher.verify(password_hash, candidate)
    except (VerifyMismatchError, InvalidHashError):
        return False
```

`tokens.py` must generate 32-byte refresh tokens with `secrets.token_urlsafe(32)`, persist only `sha256(token).hexdigest()`, and create HS256 access tokens containing `sub`, `sid`, `role`, `must_change_password`, `iat`, and `exp`. Reject JWTs with a missing claim, unexpected algorithm, invalid signature, or expired `exp`.

- [ ] **Step 4: Implement auth transactions and routes**

Implement the five routes and `operation_id` values from API specification section 4.7. Use the exact Cookie name, path, lifetime, and security flags. Login failure increments `failed_login_count` and updates `last_failed_login_at`; success resets the count and updates `last_login_at`. Refresh rotation, password change, and session revocation each run in explicit transactions.

Dependencies must expose `get_current_user`, `require_teacher`, `require_admin`, and `require_password_changed`. Each returns the authorized `User` or raises one stable `ApiError`; `get_current_user` also verifies the JWT session ID still refers to a non-revoked, non-expired login session.

- [ ] **Step 5: Verify auth and security quality**

Run: `cd api; uv run pytest tests/auth/test_auth_api.py -q; uv run ruff check src tests; uv run mypy src`

Expected: authentication tests pass; static checks exit 0.

---

### Task 5: Implement Administrator User Management and Bootstrap CLI

**Files:**
- Create: `api/src/attendance_api/schemas/users.py`
- Create: `api/src/attendance_api/modules/audit/service.py`
- Create: `api/src/attendance_api/modules/users/service.py`
- Create: `api/src/attendance_api/modules/users/router.py`
- Create: `api/src/attendance_api/cli.py`
- Modify: `api/src/attendance_api/main.py`
- Create: `api/tests/users/test_admin_users_api.py`

- [ ] **Step 1: Write failing admin tests**

```python
def test_admin_creates_teacher_without_echoing_password(admin_client) -> None:
    response = admin_client.post(
        "/api/v1/admin/users",
        json={
            "username": "Teacher01 ",
            "display_name": "王老师",
            "temporary_password": "temporary-password",
        },
    )
    assert response.status_code == 201
    assert response.json()["username"] == "teacher01"
    assert response.json()["role"] == "TEACHER"
    assert response.json()["must_change_password"] is True
    assert "password" not in str(response.json()).lower()
```

Add independent tests for teacher-role rejection; normalized duplicate username; disabling and password reset revoking every session; self-disable returning `SELF_ADMIN_ACTION_FORBIDDEN`; role/status/query pagination; and CLI creation storing an Argon2id hash rather than the supplied value.

- [ ] **Step 2: Run tests and verify failure**

Run: `cd api; uv run pytest tests/users/test_admin_users_api.py -q`

Expected: FAIL because admin routes and bootstrap command are absent.

- [ ] **Step 3: Implement admin services and audit writes**

Implement `listUsers`, `createTeacher`, `updateUserStatus`, and `resetUserPassword` exactly as API specification section 4.8. Normalize usernames before uniqueness checks and still rely on the database unique constraint for races. Password validation is 12 to 128 characters and rejects reuse on reset.

Audit service function `append_audit` accepts the active `Session` plus keyword-only actor ID, action, entity type and ID, before/after JSON, reason, IP address, request ID, and optional client mutation ID. It adds and flushes one `AuditLog` without committing, so the caller's business transaction controls atomicity.

Never place password values or hashes in audit JSON.

- [ ] **Step 4: Add the one-time administrator CLI**

Expose `uv run python -m attendance_api.cli create-admin --username admin --display-name 管理员`. Read the password twice with `getpass`, validate it, store only Argon2id output, and refuse an existing username. Do not accept a password command-line argument because process lists can expose it.

- [ ] **Step 5: Verify admin behavior**

Run: `cd api; uv run pytest tests/users/test_admin_users_api.py -q`

Expected: all admin and CLI tests pass.

---

### Task 6: Implement Courses and Class Groups

**Files:**
- Create: `api/src/attendance_api/schemas/courses.py`
- Create: `api/src/attendance_api/modules/courses/service.py`
- Create: `api/src/attendance_api/modules/courses/router.py`
- Modify: `api/src/attendance_api/main.py`
- Create: `api/tests/courses/test_courses_api.py`

- [ ] **Step 1: Write failing ownership and lifecycle tests**

```python
def test_teacher_creates_and_lists_only_own_courses(teacher_client, other_course) -> None:
    created = teacher_client.post(
        "/api/v1/courses",
        json={"name": "产品设计方法", "code": "PD204", "term": "2026 秋季学期"},
    )
    assert created.status_code == 201
    listed = teacher_client.get("/api/v1/courses").json()
    assert listed["total"] == 1
    assert listed["items"][0]["id"] == created.json()["id"]
    assert other_course.id not in {item["id"] for item in listed["items"]}
```

Add independent tests for embedded class summaries and active counts; duplicate `(code, term)`; foreign-course 404; class-name uniqueness within a course; archived-course create rejection; and one-way course/class archive transitions.

- [ ] **Step 2: Run tests and verify failure**

Run: `cd api; uv run pytest tests/courses/test_courses_api.py -q`

Expected: FAIL because course routes are absent.

- [ ] **Step 3: Implement scoped course queries and writes**

All course queries must include `Course.owner_teacher_id == current_user.id`. Class queries must join through `Course` and apply the same predicate. Implement `listCourses`, `createCourse`, `updateCourse`, `createClassGroup`, and `updateClassGroup` with exact response fields, validation limits, pagination, filters, and operation IDs from API specification section 4.9.

Course and class archive transitions are one-way in the first release. Translate named uniqueness violations to `DUPLICATE_RESOURCE`; do not parse localized database messages.

- [ ] **Step 4: Verify course behavior**

Run: `cd api; uv run pytest tests/courses/test_courses_api.py -q`

Expected: all course, class, ownership, and lifecycle tests pass.

---

### Task 7: Implement Roster Queries and Import Preview Parsing

**Files:**
- Create: `api/src/attendance_api/schemas/rosters.py`
- Create: `api/src/attendance_api/modules/rosters/service.py`
- Create: `api/src/attendance_api/modules/rosters/router.py`
- Create: `api/src/attendance_api/modules/imports/parser.py`
- Create: `api/src/attendance_api/modules/imports/service.py`
- Create: `api/src/attendance_api/modules/imports/router.py`
- Modify: `api/src/attendance_api/main.py`
- Create: `api/tests/rosters/test_roster_api.py`
- Create: `api/tests/imports/test_import_api.py`
- Create: `api/tests/fixtures/rosters/valid.csv`
- Create: `api/tests/fixtures/rosters/invalid.csv`

- [ ] **Step 1: Write failing roster and parser tests**

```python
def test_preview_marks_required_duplicate_identity_and_class_errors(
    teacher_client, class_group, roster_file
) -> None:
    response = teacher_client.post(
        f"/api/v1/classes/{class_group.id}/roster/import-preview",
        files={"file": ("invalid.csv", roster_file, "text/csv")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["summary"] == {
        "total": 4, "valid": 0, "errors": 2, "duplicates": 1, "importable": 0
    }
    assert {row["code"] for row in body["rows"]} >= {
        "MISSING_REQUIRED_FIELD", "CLASS_MISMATCH", "DUPLICATE_IN_FILE"
    }
```

Add independent tests for owned-class roster scope and search; XLSX, XLS, UTF-8 BOM, and GB18030 success; spoofed extensions and damaged workbooks; 10 MiB and 500-row boundaries; system identity conflicts; and temporary-file removal on success and exceptions.

- [ ] **Step 2: Run tests and verify failure**

Run: `cd api; uv run pytest tests/rosters/test_roster_api.py tests/imports/test_import_api.py -q`

Expected: FAIL because roster and import endpoints are absent.

- [ ] **Step 3: Implement deterministic file parsing**

Define immutable `ParsedRoster` with `rows: list[dict[str, str | int | None]]` and `validation: dict[str, object]`. Its public entry point is `parse_roster(path: Path, filename: str, target_class_name: str) -> ParsedRoster`.

Apply these rules in order: sanitize filename; enforce 10 MiB; verify file signature; parse `.xlsx` with openpyxl, `.xls` with xlrd, and CSV using `utf-8-sig`, then UTF-8, then GB18030; normalize headers to `student_number`, `name`, `gender`, `class_name`, `major`; trim cell text; discard fully blank rows; enforce 500 data rows; calculate row numbers from the source; validate required fields and maximum lengths; compare class name; detect duplicates in file; then compare existing students and enrollments.

Wrap all temporary-file processing in `try/finally` and unlink in `finally`. Persist only sanitized filename, normalized rows, validation JSON, owner, target class, and an expiry no later than one hour.

- [ ] **Step 4: Implement preview and roster responses**

Implement `getClassRoster` and `previewRosterImport` with the exact row-level codes and summaries in API specification section 4.9. A parsed file with row errors returns `201`; a structurally unreadable file returns the matching 4xx code.

- [ ] **Step 5: Verify roster preview behavior**

Run: `cd api; uv run pytest tests/rosters/test_roster_api.py tests/imports/test_import_api.py -q`

Expected: roster authorization and all supported/error file cases pass.

---

### Task 8: Implement Atomic Import Confirmation and Enrollment Updates

**Files:**
- Modify: `api/src/attendance_api/modules/imports/service.py`
- Modify: `api/src/attendance_api/modules/imports/router.py`
- Modify: `api/src/attendance_api/modules/rosters/service.py`
- Modify: `api/src/attendance_api/modules/rosters/router.py`
- Modify: `api/tests/imports/test_import_api.py`
- Modify: `api/tests/rosters/test_roster_api.py`

- [ ] **Step 1: Add failing confirmation tests**

```python
def test_confirm_identity_conflict_rolls_back_every_row(
    teacher_client, class_group, identity_conflict_preview, db_session
) -> None:
    from sqlalchemy import func, select

    from attendance_api.models.teaching import Enrollment, Student

    student_count_before = db_session.scalar(select(func.count()).select_from(Student))
    enrollment_count_before = db_session.scalar(select(func.count()).select_from(Enrollment))
    response = teacher_client.post(
        f"/api/v1/classes/{class_group.id}/roster/import-confirm",
        json={"preview_id": identity_conflict_preview.id, "duplicate_policy": "replace"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "STUDENT_IDENTITY_CONFLICT"
    assert db_session.scalar(select(func.count()).select_from(Student)) == student_count_before
    assert db_session.scalar(select(func.count()).select_from(Enrollment)) == enrollment_count_before
```

Add independent tests for atomic creation counts; `skip` leaving relationships unchanged; `replace` restoring removed relationships without changing identity; expired, foreign, and confirmed preview errors; and enrollment status changes leaving historical records unchanged.

- [ ] **Step 2: Run tests and verify failure**

Run: `cd api; uv run pytest tests/imports/test_import_api.py tests/rosters/test_roster_api.py -q`

Expected: new confirmation and enrollment tests fail.

- [ ] **Step 3: Implement confirmation with row locking**

Load the preview using a SQLAlchemy `select(ImportPreview)` statement filtered by preview ID, owner ID, class ID, `expires_at > now`, and `confirmed_at IS NULL`, then call `.with_for_update()`. Re-run identity-conflict checks inside the transaction. For each valid row, create or reuse the global student, then create, skip, or restore the enrollment according to `duplicate_policy`. Mark `confirmed_at`, append one `ROSTER_IMPORTED` audit record with counts, and commit once.

Catch uniqueness races by rolling back and translating to the stable conflict code; never continue after one row fails.

- [ ] **Step 4: Implement enrollment soft status changes**

Implement `updateEnrollmentStatus`. Scope through enrollment -> class -> course owner, accept only `ACTIVE` or `REMOVED`, append `ENROLLMENT_STATUS_CHANGED`, and leave attendance snapshots untouched.

- [ ] **Step 5: Verify import transactions**

Run: `cd api; uv run pytest tests/imports/test_import_api.py tests/rosters/test_roster_api.py -q`

Expected: confirmation counts, duplicate policies, rollback, expiry, and historical isolation pass.

---

### Task 9: Implement Attendance Session Creation, Listing, and Detail

**Files:**
- Create: `api/src/attendance_api/schemas/attendance.py`
- Create: `api/src/attendance_api/modules/attendance/service.py`
- Create: `api/src/attendance_api/modules/attendance/router.py`
- Modify: `api/src/attendance_api/main.py`
- Create: `api/tests/attendance/test_sessions_api.py`

- [ ] **Step 1: Write failing session tests**

```python
def test_create_session_snapshots_every_active_roster_member(
    teacher_client, class_group, active_enrollments
) -> None:
    response = teacher_client.post(
        f"/api/v1/classes/{class_group.id}/attendance-sessions",
        json={"session_date": "2026-09-03"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "DRAFT"
    assert len(body["records"]) == len(active_enrollments)
    assert {record["status"] for record in body["records"]} == {"pending"}
    assert body["summary"]["pending"] == len(active_enrollments)
```

Add independent tests for empty, archived, and foreign classes; a two-transaction same-date race; list filters; snapshots surviving roster removal and class rename; and summaries containing all five status counts.

- [ ] **Step 2: Run tests and verify failure**

Run: `cd api; uv run pytest tests/attendance/test_sessions_api.py -q`

Expected: FAIL because attendance routes are absent.

- [ ] **Step 3: Implement atomic session creation**

Validate that the owned course and class are active. Read active enrollments joined to students in `student_number, student_id` order. In one transaction insert the `DRAFT` session, one `pending` record per student with the three snapshot fields, and `ATTENDANCE_SESSION_CREATED` audit. Empty roster returns `ROSTER_EMPTY`; named unique violation returns `DUPLICATE_RESOURCE` without orphan records.

- [ ] **Step 4: Implement list and detail serializers**

Implement `listAttendanceSessions`, including `date_from <= date_to`, owner scoping, stable pagination, and no `records` in list items. Implement `getAttendanceSession` with all records and summary counts. API dates are based on Asia/Shanghai while stored timestamps remain UTC.

- [ ] **Step 5: Verify attendance reads and creation**

Run: `cd api; uv run pytest tests/attendance/test_sessions_api.py -q`

Expected: all creation, uniqueness, snapshot, list, detail, and summary tests pass.

---

### Task 10: Implement Idempotent Record Updates and Session Completion

**Files:**
- Modify: `api/src/attendance_api/modules/attendance/service.py`
- Modify: `api/src/attendance_api/modules/attendance/router.py`
- Create: `api/tests/attendance/test_records_api.py`

- [ ] **Step 1: Write failing concurrency and completion tests**

```python
def test_stale_version_returns_current_record_without_update(
    teacher_client, attendance_record
) -> None:
    response = teacher_client.patch(
        f"/api/v1/attendance-records/{attendance_record.id}",
        json={
            "status": "late",
            "expected_version": attendance_record.version - 1,
            "client_mutation_id": "e9329885-359a-49b9-8846-6fad26c6501b",
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "ATTENDANCE_RECORD_CONFLICT"
    assert response.json()["details"]["current_record"]["version"] == attendance_record.version
```

Add independent tests for draft updates incrementing version and writing audit; completed-record reason and before/after audit; same-mutation replay; mutation reuse on another record; pending completion rejection; and idempotent completion preserving its first timestamp.

- [ ] **Step 2: Run tests and verify failure**

Run: `cd api; uv run pytest tests/attendance/test_records_api.py -q`

Expected: FAIL because update and completion behavior is missing.

- [ ] **Step 3: Implement record update ordering**

Inside one transaction:

1. Query `audit_logs` by `client_mutation_id`.
2. If it belongs to this record and action, reconstruct and return the first result from `after_value`.
3. If it belongs to anything else, return `INVALID_REQUEST`.
4. Scope the record through session -> class -> course owner.
5. Validate status and conditional reason.
6. Update with `WHERE id=:id AND version=:expected_version` and increment version.
7. On zero rows, return `ATTENDANCE_RECORD_CONFLICT` with current record.
8. Insert audit `before_value` and a complete response snapshot in `after_value` using the unique mutation ID.
9. Commit and return the new record.

Preserve the first non-null `marked_at`; always update `last_modified_at` and `last_modified_by`.

- [ ] **Step 4: Implement completion under a row lock**

Load the owned session with a SQLAlchemy statement ending in `.with_for_update()`. If already completed, return it without changing `completed_at`. Count pending records in the locked transaction; return `ATTENDANCE_INCOMPLETE` with `pending_count` when nonzero. Otherwise set status and completion time, append audit, and commit.

- [ ] **Step 5: Verify concurrency and state rules**

Run: `cd api; uv run pytest tests/attendance/test_records_api.py -q`

Expected: version, mutation, audit, reason, pending, and idempotent completion tests pass.

---

### Task 11: Implement Streaming CSV and XLSX Exports

**Files:**
- Create: `api/src/attendance_api/modules/exports/service.py`
- Create: `api/src/attendance_api/modules/exports/router.py`
- Modify: `api/src/attendance_api/main.py`
- Create: `api/tests/exports/test_export_api.py`

- [ ] **Step 1: Write failing export tests**

```python
def test_csv_has_bom_fixed_columns_snapshot_values_and_safe_formulas(
    teacher_client, completed_session_with_formula_value
) -> None:
    from attendance_api.modules.exports.service import EXPORT_COLUMNS

    response = teacher_client.get(
        f"/api/v1/attendance-sessions/{completed_session_with_formula_value.id}/export",
        params={"format": "csv"},
    )
    assert response.status_code == 200
    assert response.content.startswith(b"\xef\xbb\xbf")
    text = response.content.decode("utf-8-sig")
    assert text.splitlines()[0].split(",") == EXPORT_COLUMNS
    assert "'=HYPERLINK" in text
```

Add independent tests opening XLSX and asserting student numbers are string cells; sanitized UTF-8 filename headers; draft, unknown-format, and foreign-session errors; and no persistent file under the configured temporary directory after response completion.

- [ ] **Step 2: Run tests and verify failure**

Run: `cd api; uv run pytest tests/exports/test_export_api.py -q`

Expected: FAIL because export route is absent.

- [ ] **Step 3: Implement export generation**

Use this fixed column order:

```python
EXPORT_COLUMNS = [
    "课程", "课程代码", "班级", "日期", "姓名", "学号", "考勤状态",
    "点名时间", "最后修改时间", "最后修改人",
]
```

Generate CSV into `io.StringIO`, prefix UTF-8 BOM in the byte stream, quote with the standard `csv` module, and prefix spreadsheet-formula text beginning with `=`, `+`, `-`, or `@` with a single quote. Generate XLSX into `io.BytesIO` with openpyxl and set student-number/text cells to string type. Use snapshot identity values.

Sanitize Windows and POSIX forbidden filename characters to `_`, collapse repeated underscores, cap the base to 180 characters, then emit RFC 5987 `filename*` in `Content-Disposition`. Return a `StreamingResponse`; do not write a persistent export file.

- [ ] **Step 4: Verify exports**

Run: `cd api; uv run pytest tests/exports/test_export_api.py -q`

Expected: CSV and XLSX content, response headers, authorization, state checks, and no-file behavior pass.

---

### Task 12: Lock the OpenAPI Contract and Production Service Boundary

**Files:**
- Create: `api/tests/contract/test_openapi.py`
- Create: `api/Dockerfile`
- Modify: `api/src/attendance_api/main.py`
- Modify: `api/.env.example`
- Create: `api/README.md`

- [ ] **Step 1: Write failing OpenAPI coverage tests**

```python
EXPECTED_OPERATION_IDS = {
    "getHealthLive", "getHealthReady", "login", "refreshAccessToken", "logout",
    "getCurrentUser", "changePassword", "listUsers", "createTeacher",
    "updateUserStatus", "resetUserPassword", "listCourses", "createCourse",
    "updateCourse", "createClassGroup", "updateClassGroup", "getClassRoster",
    "previewRosterImport", "confirmRosterImport", "updateEnrollmentStatus",
    "listAttendanceSessions", "createAttendanceSession", "getAttendanceSession",
    "updateAttendanceRecord", "completeAttendanceSession", "exportAttendanceSession",
}


def test_openapi_contains_all_stable_operation_ids(client) -> None:
    schema = client.get("/openapi.json").json()
    actual = {
        operation["operationId"]
        for path in schema["paths"].values()
        for method, operation in path.items()
        if method in {"get", "post", "patch", "put", "delete"}
    }
    assert actual == EXPECTED_OPERATION_IDS
```

Also assert security schemes, error schemas, request models with forbidden extra fields, upload media type, and binary export responses.

- [ ] **Step 2: Run contract tests and verify failure**

Run: `cd api; uv run pytest tests/contract/test_openapi.py -q`

Expected: FAIL until all routes expose exact operation IDs and response models.

- [ ] **Step 3: Complete app registration and OpenAPI metadata**

Register routers in this order: health, auth, admin users, courses, rosters, imports, attendance, exports. Add Bearer security, reusable error schemas, tags, and explicit success/error response models to every route. Configure Pydantic request models with `extra="forbid"` and response models with `from_attributes=True` where ORM conversion is used.

- [ ] **Step 4: Add the production container**

```dockerfile
# api/Dockerfile
FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src
RUN groupadd --gid 10001 attendance \
    && useradd --uid 10001 --gid attendance --no-create-home attendance \
    && chown -R attendance:attendance /app
USER attendance
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "attendance_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
```

The fixed UID/GID runs the container without root privileges. Do not run migrations in `CMD`; deployment executes `uv run alembic upgrade head` as an explicit release step.

- [ ] **Step 5: Document local operation**

`api/README.md` must provide exact commands for dependency installation, MySQL startup, migration, admin bootstrap, API startup, test execution, OpenAPI URL, and test-database shutdown. It must state that `.env` is untracked and production secrets must not use example values.

- [ ] **Step 6: Run the full verification gate**

Run:

```powershell
cd api
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest --cov=attendance_api --cov-report=term-missing --cov-fail-under=85
uv run alembic downgrade base
uv run alembic upgrade head
docker build -t attendance-api:local .
```

Expected: every command exits 0; backend coverage is at least 85%; a clean database can downgrade and upgrade; the image builds.

- [ ] **Step 7: Verify the live service contract**

Run: `cd api; uv run uvicorn attendance_api.main:app --host 127.0.0.1 --port 8000`

In another terminal run:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/live
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ready
Invoke-WebRequest http://127.0.0.1:8000/openapi.json -OutFile openapi.json
```

Expected: both health endpoints report healthy, and generated OpenAPI contains all 26 operation IDs.

---

## Final Specification Coverage

| Requirement area | Implemented by |
| --- | --- |
| MySQL schema, constraints, indexes, migrations | Task 2 |
| Uniform errors, request IDs, readiness | Task 3 |
| JWT, refresh rotation, first password change | Task 4 |
| Administrator teacher management | Task 5 |
| Course/class ownership and archive lifecycle | Task 6 |
| Roster query and import preview | Task 7 |
| Atomic import confirmation and enrollment status | Task 8 |
| Attendance snapshots, history list and details | Task 9 |
| Optimistic locking, mutation idempotency, audit, completion | Task 10 |
| Streaming CSV/XLSX and formula-injection defense | Task 11 |
| OpenAPI, static quality gates and container image | Task 12 |

Production Nginx, HTTPS certificates, root `compose.yaml`, database backups, and React migration are separate deployment/frontend workstreams. The backend container and API contract produced here are their prerequisites; excluding those workstreams keeps this plan independently executable and testable.
