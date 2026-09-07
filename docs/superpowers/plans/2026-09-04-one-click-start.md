# One-click Local Startup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Windows double-click launcher that prepares and starts the persistent development database, migrates it, starts the API and frontend, and opens the application.

**Architecture:** `api/compose.dev.yaml` owns only the persistent MySQL service. `scripts/start.ps1` is the orchestration boundary and exposes testable helpers while running its main workflow only when invoked directly. `start.bat` is a thin Explorer-friendly wrapper.

**Tech Stack:** Windows PowerShell 5.1+, Docker Compose, MySQL 8.4, uv, Alembic, FastAPI/Uvicorn, Node.js/npm, Vite.

---

## File map

- Create `api/compose.dev.yaml`: isolated persistent local MySQL service.
- Create `scripts/start.ps1`: prerequisite checks, first-run environment generation, setup, process launch, readiness polling, and browser opening.
- Create `start.bat`: double-click wrapper with failure pause behavior.
- Create `tests/start-compose.Tests.ps1`: Docker Compose contract test.
- Create `tests/start-environment.Tests.ps1`: generated `.env` behavior test.
- Create `tests/start-launcher.Tests.ps1`: syntax and launcher contract test.
- Create `.gitignore`: protect generated secrets and local environment files.
- Modify `README.md`: document one-click startup and generated credentials.

The workspace has no `.git` directory, so commit steps are intentionally omitted. Do not initialize a repository merely to satisfy the workflow.

### Task 1: Persistent development database

**Files:**
- Create: `tests/start-compose.Tests.ps1`
- Create: `api/compose.dev.yaml`
- Create: `.gitignore`

- [ ] **Step 1: Write the failing Compose contract test**

Create a dependency-free PowerShell test that loads `api/compose.dev.yaml` as text and asserts it contains MySQL 8.4, database `attendance`, host binding `127.0.0.1:33306:3306`, a health check, the named volume `attendance_mysql_data`, and a volume mount. Also assert `.gitignore` ignores `/api/.env` and `/.env.local`.

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tests/start-compose.Tests.ps1
```

Expected: exit code `1` because `api/compose.dev.yaml` does not exist.

- [ ] **Step 3: Add the minimal Compose configuration**

Create `api/compose.dev.yaml` with this contract:

```yaml
services:
  mysql:
    image: mysql:8.4
    environment:
      MYSQL_DATABASE: attendance
      MYSQL_USER: attendance
      MYSQL_PASSWORD: attendance
      MYSQL_ROOT_PASSWORD: local-development-only
      TZ: Asia/Shanghai
    ports:
      - "127.0.0.1:33306:3306"
    volumes:
      - attendance_mysql_data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-uroot", "-plocal-development-only"]
      interval: 2s
      timeout: 3s
      retries: 30

volumes:
  attendance_mysql_data:
```

Create `.gitignore` with `/api/.env` and `/.env.local`; preserve any ignore rules that appear before implementation.

- [ ] **Step 4: Verify GREEN and validate Compose**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tests/start-compose.Tests.ps1
docker compose -p attendance-dev -f api/compose.dev.yaml config --quiet
```

Expected: both commands exit `0`.

### Task 2: First-run API configuration

**Files:**
- Create: `tests/start-environment.Tests.ps1`
- Create: `scripts/start.ps1`

- [ ] **Step 1: Write the failing environment behavior test**

The test dot-sources `scripts/start.ps1`, calls `Initialize-ApiEnvironment` with a temporary path, and asserts:

- the first call reports `Created = $true`;
- the file contains the development database URL on port `33306`, `FRONTEND_ORIGIN=http://127.0.0.1:5173`, `REFRESH_COOKIE_SECURE=false`, username `admin`, and non-empty password/JWT fields;
- the password is 12 to 128 characters and the JWT secret is at least 32 characters;
- the second call reports `Created = $false` and leaves the exact file bytes unchanged.

The test deletes only its own unique directory under `[IO.Path]::GetTempPath()` in a `finally` block.

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tests/start-environment.Tests.ps1
```

Expected: exit code `1` because `scripts/start.ps1` is missing.

- [ ] **Step 3: Implement the environment helpers**

Add `New-RandomSecret` using `RandomNumberGenerator`, base64url encoding, and no padding. Add `Initialize-ApiEnvironment -Path <string>` that returns an object with `Created`, `Username`, and `Password`, writes UTF-8 without BOM only when the file is absent, creates the parent directory, and generates this complete configuration:

```dotenv
APP_ENV=development
DATABASE_URL=mysql+pymysql://attendance:attendance@127.0.0.1:33306/attendance
JWT_SECRET=<generated 32+ character value>
FRONTEND_ORIGIN=http://127.0.0.1:5173
ACCESS_TOKEN_TTL_SECONDS=900
REFRESH_TOKEN_TTL_SECONDS=604800
REFRESH_COOKIE_SECURE=false
ADMIN_USERNAME=admin
ADMIN_DISPLAY_NAME=Super Administrator
ADMIN_PASSWORD=<generated 12-128 character value>
```

Guard main execution with:

```powershell
if ($MyInvocation.InvocationName -ne '.') {
    exit (Start-DevelopmentStack)
}
```

During this task, define `Start-DevelopmentStack` to throw `Launcher implementation is not complete.` so direct invocation cannot silently succeed.

- [ ] **Step 4: Run the environment test and verify GREEN**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tests/start-environment.Tests.ps1
```

Expected: exit `0` and `start-environment.Tests.ps1: PASS`.

### Task 3: Complete startup orchestration and double-click entry

**Files:**
- Create: `tests/start-launcher.Tests.ps1`
- Modify: `scripts/start.ps1`
- Create: `start.bat`

- [ ] **Step 1: Write the failing launcher contract test**

Use `[System.Management.Automation.Language.Parser]::ParseFile` to assert `scripts/start.ps1` has no parse errors. Assert its source contains the exact Compose project `attendance-dev`, `uv sync --group dev`, `npm install`, `uv run alembic upgrade head`, Uvicorn on `127.0.0.1:8000`, Vite startup, `/api/v1/health/ready`, frontend URL `http://127.0.0.1:5173`, and `Start-Process`. Assert `start.bat` passes `-ExecutionPolicy Bypass`, invokes `scripts\start.ps1`, propagates a non-zero exit code, and pauses only on failure.

- [ ] **Step 2: Run the launcher test and verify RED**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tests/start-launcher.Tests.ps1
```

Expected: exit `1` because orchestration and `start.bat` are absent.

- [ ] **Step 3: Implement checked command execution and readiness polling**

In `scripts/start.ps1`, add:

- `Assert-Command -Name <string>` using `Get-Command -ErrorAction SilentlyContinue`;
- `Invoke-Native -FilePath <string> -Arguments <string[]> -WorkingDirectory <string>` that restores the original location in `finally` and throws on non-zero `$LASTEXITCODE`;
- `Wait-HttpEndpoint -Uri <string> -Name <string> -TimeoutSeconds <int>` that polls once per second with `Invoke-WebRequest -UseBasicParsing -TimeoutSec 3` and throws after the deadline.

Every thrown error must identify the command or endpoint that failed.

- [ ] **Step 4: Implement the main workflow**

`Start-DevelopmentStack` must resolve `$ProjectRoot` from `$PSScriptRoot`, then perform these checked actions in order:

```powershell
Assert-Command docker
Assert-Command uv
Assert-Command node
Assert-Command npm
Invoke-Native docker @('info') $ProjectRoot
Initialize-ApiEnvironment (Join-Path $ProjectRoot 'api\.env')
Invoke-Native docker @('compose', '-p', 'attendance-dev', '-f', 'compose.dev.yaml', 'up', '-d', '--wait') $ApiRoot
Invoke-Native uv @('sync', '--group', 'dev') $ApiRoot
Invoke-Native npm @('install') $ProjectRoot
Invoke-Native uv @('run', 'alembic', 'upgrade', 'head') $ApiRoot
```

Then start two new `powershell.exe` windows with `-NoExit` and explicit working directories. The API command is `uv run uvicorn attendance_api.main:app --host 127.0.0.1 --port 8000`; the frontend command is `npm run dev`. Poll API readiness and the frontend for up to 60 seconds, print both URLs, print generated credentials only when `Created` is true, and call `Start-Process 'http://127.0.0.1:5173'` unless `-SkipBrowser` was passed.

Wrap the workflow in `try/catch`; write the exception through `Write-Error` and return `1`, otherwise return `0`. Never stop existing processes or delete the volume.

- [ ] **Step 5: Add the batch wrapper**

Create `start.bat`:

```bat
@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1"
set "START_EXIT_CODE=%ERRORLEVEL%"
if not "%START_EXIT_CODE%"=="0" (
  echo.
  echo Startup failed. Review the error above.
  pause
)
exit /b %START_EXIT_CODE%
```

- [ ] **Step 6: Verify GREEN**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tests/start-launcher.Tests.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File tests/start-environment.Tests.ps1
```

Expected: both print `PASS` and exit `0`.

### Task 4: Documentation and end-to-end verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document one-click startup**

At the start of the local-development section, document that Windows users can double-click `start.bat`; Docker Desktop, uv, and Node.js are prerequisites; first-run setup creates `api/.env`; generated credentials are printed once and remain in that file; subsequent runs preserve existing settings and database data. Keep the existing manual commands as the troubleshooting/manual path.

- [ ] **Step 2: Run all static and behavioral launcher tests**

Run:

```powershell
Get-ChildItem tests/start-*.Tests.ps1 | ForEach-Object {
  & powershell -NoProfile -ExecutionPolicy Bypass -File $_.FullName
  if ($LASTEXITCODE -ne 0) { throw "Test failed: $($_.Name)" }
}
```

Expected: three `PASS` lines and exit `0`.

- [ ] **Step 3: Run the actual launcher without opening the browser**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start.ps1 -SkipBrowser
```

Expected: exit `0`, MySQL becomes healthy, migrations reach head, and both service URLs are reported. If a prerequisite is genuinely unavailable, report the exact failed check rather than claiming end-to-end success.

- [ ] **Step 4: Verify each live service and migration state**

Run:

```powershell
docker compose -p attendance-dev -f api/compose.dev.yaml ps
Push-Location api
uv run alembic current
Pop-Location
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ready
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5173
```

Expected: MySQL is `healthy`, Alembic shows `0001 (head)`, API returns `status: ready`, and the frontend returns HTTP `200`.

- [ ] **Step 5: Run repository regression checks**

Run:

```powershell
npm run typecheck
npm run test:unit
Push-Location api
uv run --env-file .env.test.example pytest
Pop-Location
```

Expected: all commands exit `0`. Do not stop services after verification because the requested outcome is a running development application.
