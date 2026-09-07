# Environment-Configured Administrator Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically create or synchronize the configured administrator from API environment variables and route authenticated administrators to a simple frontend page.

**Architecture:** Add optional administrator settings and a focused bootstrap module that runs once during FastAPI lifespan startup. Keep authentication policy separate from password-creation policy, then use role-aware frontend routes so administrators never load teacher-only resources.

**Tech Stack:** Python 3.11+, FastAPI lifespan, Pydantic Settings, SQLAlchemy 2, Argon2id, pytest, React 19, React Router, TypeScript, Vitest, Testing Library.

---

## File Map

- Create `api/src/attendance_api/admin_bootstrap.py`: validate configured credentials, create or synchronize the administrator transactionally, and revoke sessions when the configured password changes.
- Create `api/tests/auth/test_admin_bootstrap.py`: cover disabled configuration, creation, idempotency, credential synchronization, conflicts, and validation.
- Modify `api/src/attendance_api/config.py`: expose optional administrator settings without placing a usable password in source control.
- Modify `api/src/attendance_api/main.py`: invoke bootstrap during application lifespan before serving requests.
- Modify `api/tests/test_health.py`: prove the lifespan invokes bootstrap.
- Modify `api/src/attendance_api/schemas/auth.py`: accept any non-empty login password up to the storage limit.
- Modify `api/tests/auth/test_auth_api.py`: prove a legacy short password reaches credential verification and succeeds.
- Create `src/features/admin/AdminPage.tsx`: render account identity and logout only, with no business API query.
- Modify `src/app/router.tsx`: add role-aware home destinations and route guards.
- Modify `src/features/auth/LoginPage.tsx`: remove new-password policy validation from login.
- Modify `src/app/App.test.tsx`: cover short-password submission, administrator routing, no teacher calls, and logout.
- Modify `src/styles/global.css`: add responsive dimensions for the simple administrator page.
- Modify `api/.env.example`, `api/.env.test.example`, `api/README.md`, and `README.md`: document automatic bootstrap and password reset behavior.

### Task 1: Administrator Settings and Transactional Synchronization

**Files:**
- Create: `api/tests/auth/test_admin_bootstrap.py`
- Create: `api/src/attendance_api/admin_bootstrap.py`
- Modify: `api/src/attendance_api/config.py`

- [ ] **Step 1: Write failing tests for disabled configuration and initial creation**

Create tests using the existing transactional `db_session` fixture:

```python
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from attendance_api.admin_bootstrap import sync_configured_admin
from attendance_api.config import Settings
from attendance_api.models import User
from attendance_api.security.passwords import verify_password

ADMIN_PASSWORD = "configured-admin-password"


def settings(password: str | None = ADMIN_PASSWORD) -> Settings:
    return Settings(
        _env_file=None,
        admin_username=" RootAdmin ",
        admin_display_name=" 超级管理员 ",
        admin_password=SecretStr(password) if password is not None else None,
    )


def test_admin_bootstrap_is_disabled_without_password(db_session: Session) -> None:
    result = sync_configured_admin(db_session, settings(None))

    assert result == "disabled"
    assert db_session.scalar(select(User)) is None


def test_admin_bootstrap_creates_active_admin_with_hash(db_session: Session) -> None:
    result = sync_configured_admin(db_session, settings())

    admin = db_session.scalar(select(User).where(User.username == "rootadmin"))
    assert result == "created"
    assert admin is not None
    assert admin.display_name == "超级管理员"
    assert admin.role == "ADMIN"
    assert admin.status == "ACTIVE"
    assert admin.must_change_password is False
    assert admin.password_hash != ADMIN_PASSWORD
    assert verify_password(admin.password_hash, ADMIN_PASSWORD)
```

- [ ] **Step 2: Run the new tests and verify RED**

Run: `cd api; uv run --env-file .env.test.example pytest tests/auth/test_admin_bootstrap.py -q`

Expected: collection fails with `ModuleNotFoundError: No module named 'attendance_api.admin_bootstrap'`.

- [ ] **Step 3: Add settings and the minimal creation implementation**

Extend `Settings`:

```python
admin_username: str = "admin"
admin_display_name: str = "超级管理员"
admin_password: SecretStr | None = None
```

Create `admin_bootstrap.py` with `AdminBootstrapResult = Literal["disabled", "created", "updated", "unchanged"]`. In `sync_configured_admin(db, settings)`, return `"disabled"` for a missing or empty secret, normalize username/display name, enforce nonblank values and `password_meets_policy`, create an `ACTIVE` `ADMIN` with `must_change_password=False`, commit, and return `"created"`.

- [ ] **Step 4: Run the new tests and verify GREEN**

Run: `cd api; uv run --env-file .env.test.example pytest tests/auth/test_admin_bootstrap.py -q`

Expected: both tests pass.

- [ ] **Step 5: Add failing tests for idempotency, updates, and conflicts**

Add tests that:

```python
def test_admin_bootstrap_is_idempotent_when_configuration_matches(db_session: Session) -> None:
    sync_configured_admin(db_session, settings())
    admin = db_session.scalar(select(User).where(User.username == "rootadmin"))
    assert admin is not None
    original_hash = admin.password_hash

    result = sync_configured_admin(db_session, settings())

    db_session.refresh(admin)
    assert result == "unchanged"
    assert admin.password_hash == original_hash


def test_admin_bootstrap_updates_password_and_revokes_sessions(db_session: Session) -> None:
    sync_configured_admin(db_session, settings("old-admin-password"))
    admin = db_session.scalar(select(User).where(User.username == "rootadmin"))
    assert admin is not None
    session = LoginSession(
        user_id=admin.id,
        refresh_token_hash="a" * 64,
        expires_at=utc_now() + timedelta(days=1),
        last_used_at=utc_now(),
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    db_session.add(session)
    db_session.commit()

    updated = settings("new-admin-password")
    updated.admin_display_name = "新管理员"
    result = sync_configured_admin(db_session, updated)

    db_session.refresh(admin)
    db_session.refresh(session)
    assert result == "updated"
    assert admin.display_name == "新管理员"
    assert verify_password(admin.password_hash, "new-admin-password")
    assert session.revoked_at is not None
```

Also add distinct tests proving an existing configured admin is re-enabled with `must_change_password=False`, a `TEACHER` using the configured username raises `AdminBootstrapError`, and blank username, blank display name, or a password outside 12–128 characters raises `AdminBootstrapError` without modifying rows.

- [ ] **Step 6: Run the extended tests and verify RED**

Run: `cd api; uv run --env-file .env.test.example pytest tests/auth/test_admin_bootstrap.py -q`

Expected: update/idempotency/conflict tests fail because existing users are not handled.

- [ ] **Step 7: Implement existing-account synchronization**

Lock the configured row with `select(User).where(User.username == normalized_username).with_for_update()`. Reject a non-admin role. Synchronize display name, `ACTIVE`, and `must_change_password=False`; compare the configured password with `verify_password`. Only on mismatch, replace the hash and execute:

```python
db.execute(
    update(LoginSession)
    .where(LoginSession.user_id == user.id, LoginSession.revoked_at.is_(None))
    .values(revoked_at=utc_now())
)
```

Commit once and return `"updated"` when any field changed, otherwise `"unchanged"`. Raise `AdminBootstrapError` before mutation for invalid settings or role conflict.

- [ ] **Step 8: Run bootstrap tests and verify GREEN**

Run: `cd api; uv run --env-file .env.test.example pytest tests/auth/test_admin_bootstrap.py -q`

Expected: all bootstrap tests pass.

- [ ] **Step 9: Commit checkpoint**

Current workspace has no `.git` directory, so no commit command can be run. Preserve the completed Task 1 changes without manufacturing Git metadata.

### Task 2: Run Bootstrap During FastAPI Lifespan

**Files:**
- Modify: `api/src/attendance_api/admin_bootstrap.py`
- Modify: `api/src/attendance_api/main.py`
- Modify: `api/tests/test_health.py`

- [ ] **Step 1: Write a failing lifespan test**

Add:

```python
def test_startup_runs_admin_bootstrap(monkeypatch: pytest.MonkeyPatch) -> None:
    bootstrap = Mock()
    monkeypatch.setattr("attendance_api.main.bootstrap_configured_admin", bootstrap)

    with TestClient(create_app()):
        pass

    bootstrap.assert_called_once_with()
```

- [ ] **Step 2: Run the test and verify RED**

Run: `cd api; uv run --env-file .env.test.example pytest tests/test_health.py::test_startup_runs_admin_bootstrap -q`

Expected: FAIL because `attendance_api.main.bootstrap_configured_admin` does not exist.

- [ ] **Step 3: Add the production bootstrap wrapper and lifespan**

In `admin_bootstrap.py`, add `bootstrap_configured_admin()` that reads `get_settings()`, opens `SessionFactory`, calls `sync_configured_admin`, and logs only the non-secret username plus result.

In `main.py`, add:

```python
@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    bootstrap_configured_admin()
    yield
```

Pass `lifespan=lifespan` to `FastAPI(...)`. Let configuration, migration, and database errors propagate so the server never advertises readiness with incomplete initialization.

- [ ] **Step 4: Run startup and bootstrap tests and verify GREEN**

Run: `cd api; uv run --env-file .env.test.example pytest tests/test_health.py tests/auth/test_admin_bootstrap.py -q`

Expected: all selected tests pass and logs contain no configured password.

- [ ] **Step 5: Commit checkpoint**

Skip because this workspace has no Git repository.

### Task 3: Separate Login Validation From New-Password Policy

**Files:**
- Modify: `api/src/attendance_api/schemas/auth.py`
- Modify: `api/tests/auth/test_auth_api.py`
- Modify: `src/features/auth/LoginPage.tsx`
- Modify: `src/app/App.test.tsx`

- [ ] **Step 1: Write a failing API test for a valid legacy short password**

Create a user with `PasswordHasher().hash("short-pass")`, then post the same password to `/api/v1/auth/login` and assert status `200`. This must fail with `INVALID_REQUEST` before the implementation change.

- [ ] **Step 2: Run the API test and verify RED**

Run: `cd api; uv run --env-file .env.test.example pytest tests/auth/test_auth_api.py::test_login_accepts_valid_legacy_short_password -q`

Expected: FAIL with status `400`, proving request validation blocks credential verification.

- [ ] **Step 3: Relax only the login request constraint**

Change `LoginRequest.password` from `Field(min_length=12, max_length=128)` to `Field(min_length=1, max_length=128)`. Do not change `ChangePasswordRequest` or `password_meets_policy`.

- [ ] **Step 4: Run the API test and verify GREEN**

Run: `cd api; uv run --env-file .env.test.example pytest tests/auth/test_auth_api.py::test_login_accepts_valid_legacy_short_password -q`

Expected: PASS.

- [ ] **Step 5: Write a failing frontend test for submitting a short password**

After session restoration returns 401, enter `admin` and `short-pass`, submit, and assert `fetch` receives a second call whose body is `{"username":"admin","password":"short-pass"}`. Return a 401 login response so routing is not part of this test.

- [ ] **Step 6: Run the frontend test and verify RED**

Run: `npm run test:unit -- --run src/app/App.test.tsx`

Expected: FAIL because the page displays the 12-character validation error and never sends the login request.

- [ ] **Step 7: Remove the login-page length check**

Keep `if (!password) next.password = '请输入密码';` and delete only the `password.length < 12` branch.

- [ ] **Step 8: Run focused backend and frontend tests and verify GREEN**

Run: `cd api; uv run --env-file .env.test.example pytest tests/auth/test_auth_api.py -q`

Run: `npm run test:unit -- --run src/app/App.test.tsx`

Expected: all selected tests pass.

- [ ] **Step 9: Commit checkpoint**

Skip because this workspace has no Git repository.

### Task 4: Role-Aware Routes and Simple Administrator Page

**Files:**
- Create: `src/features/admin/AdminPage.tsx`
- Modify: `src/app/router.tsx`
- Modify: `src/app/App.test.tsx`
- Modify: `src/styles/global.css`

- [ ] **Step 1: Write failing administrator route tests**

Add a `loginResponse(role)` test helper with complete `User` fields. Cover these behaviors:

```typescript
it('routes an administrator to the administrator page without teacher requests', async () => {
  // refresh fails, login succeeds with role ADMIN
  // enter credentials and submit
  expect(await screen.findByRole('heading', { name: '超级管理员' })).toBeInTheDocument();
  expect(screen.getByText('admin')).toBeInTheDocument();
  expect(fetcher).toHaveBeenCalledTimes(2);
});

it('redirects a restored administrator away from the teacher dashboard', async () => {
  window.history.pushState({}, '', '/');
  // refresh succeeds with role ADMIN
  render(<App />);
  expect(await screen.findByRole('heading', { name: '超级管理员' })).toBeInTheDocument();
  expect(fetcher).toHaveBeenCalledTimes(1);
});
```

Also test that a restored teacher visiting `/admin` reaches the teacher dashboard, and clicking the administrator page logout button posts `/auth/logout` and returns to the login heading.

- [ ] **Step 2: Run route tests and verify RED**

Run: `npm run test:unit -- --run src/app/App.test.tsx`

Expected: FAIL because `/admin`, role-aware redirects, and `AdminPage` are absent; the current administrator path triggers teacher API calls.

- [ ] **Step 3: Create the simple administrator page**

Implement `AdminPage` using `useAuth()` and Lucide `ShieldCheck`/`LogOut`. Render a stable full-page region containing the brand, heading `超级管理员`, current `display_name`, current `username`, an `管理员` status label, and an icon-plus-text logout button. Do not call `useApi`, `useQuery`, or any teacher resource.

- [ ] **Step 4: Implement role destinations and guards**

In `router.tsx`, define:

```typescript
function homeFor(role: UserRole | undefined) {
  return role === 'ADMIN' ? '/admin' : '/';
}
```

Update `PublicOnly` and `PasswordRoute` to redirect with `homeFor(user?.role)`. Add a `RoleRoute` that redirects an authenticated wrong-role user to their own home. Nest current teacher routes under `RoleRoute role="TEACHER"`, and add `/admin` under `RoleRoute role="ADMIN"`. Preserve the `must_change_password` gate before role routing.

- [ ] **Step 5: Add bounded responsive administrator styles**

Add `.admin-page`, `.admin-topbar`, `.admin-content`, `.admin-identity`, and `.admin-details` rules using existing semantic colors, 5–6px radii, fixed icon/button dimensions, and a mobile breakpoint. Keep sections unframed except the single account-details panel.

- [ ] **Step 6: Run route tests and verify GREEN**

Run: `npm run test:unit -- --run src/app/App.test.tsx`

Expected: all authentication and administrator routing tests pass with no unexpected fetches.

- [ ] **Step 7: Run all frontend unit tests**

Run: `npm run typecheck`

Run: `npm run test:unit`

Expected: TypeScript and every Vitest file pass without warnings.

- [ ] **Step 8: Commit checkpoint**

Skip because this workspace has no Git repository.

### Task 5: Environment Documentation and Full Verification

**Files:**
- Modify: `api/.env.example`
- Modify: `api/.env.test.example`
- Modify: `api/README.md`
- Modify: `README.md`

- [ ] **Step 1: Document configuration without committing a password**

Add commented entries to both example environment files:

```dotenv
# ADMIN_USERNAME=admin
# ADMIN_DISPLAY_NAME=超级管理员
# ADMIN_PASSWORD=replace-with-12-to-128-characters
```

Explain in both READMEs that setting these in the real `api/.env` creates the account on startup; changing `ADMIN_PASSWORD` and restarting resets it and revokes prior sessions; removing/blanking the value disables synchronization; and `.env` must never be committed.

- [ ] **Step 2: Run backend quality gates**

Run: `cd api; uv run --env-file .env.test.example pytest`

Run: `cd api; uv run ruff check .`

Run: `cd api; uv run ruff format --check .`

Run: `cd api; uv run mypy src`

Expected: all tests and static checks pass.

- [ ] **Step 3: Run frontend quality gates**

Run: `npm run typecheck`

Run: `npm run test:unit`

Run: `npm run build`

Expected: all commands exit zero and `dist/` builds successfully.

- [ ] **Step 4: Verify real startup synchronization against the test database**

Set a temporary `ADMIN_PASSWORD` only for the process, start the API, request `/api/v1/health/ready`, then log in through the frontend with the configured account. Verify the browser reaches `/admin`, renders the account identity, issues no course/attendance requests, and logout returns to `/login`. Do not print the password in output or store it in tracked files.

- [ ] **Step 5: Final diff review**

Confirm no password or token appears in source, examples, logs, test snapshots, or built frontend assets. Confirm existing teacher login, first-password-change, dashboard, and business routes remain unchanged.

- [ ] **Step 6: Commit checkpoint**

Skip because this workspace has no Git repository. Report the changed files and verification output directly to the user.
