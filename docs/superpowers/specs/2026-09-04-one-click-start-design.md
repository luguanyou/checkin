# One-click local startup design

## Goal

Provide a Windows entry point that starts the complete local development stack with one double-click: a persistent MySQL container, database migrations, the FastAPI API, and the Vite frontend.

## Entry points and files

- `start.bat` is the double-click entry point. It invokes PowerShell with an execution-policy override scoped to the process and keeps the window open when startup fails.
- `scripts/start.ps1` owns prerequisite checks, first-run configuration, Docker orchestration, migrations, process startup, readiness checks, and opening the browser.
- `api/compose.dev.yaml` defines a development-only MySQL 8.4 service on host port `33306` with a named volume and a health check. It uses an explicit Compose project name so it does not collide with the test database.
- `.gitignore` excludes generated environment files and local runtime artifacts, including `api/.env`.

## Startup flow

1. Resolve all paths relative to the script location so launching from Explorer or another working directory behaves identically.
2. Check that `docker`, `uv`, `node`, and `npm` are available, and that Docker Desktop is responding.
3. If `api/.env` does not exist, create it from development-safe values: the development database URL, local frontend origin, insecure local refresh cookie, a cryptographically random JWT secret, and a random initial administrator password. Existing configuration is never overwritten.
4. Start the development MySQL service and wait for its Compose health check.
5. Run `uv sync`, `npm install`, and `uv run alembic upgrade head`. Dependency tools may no-op when dependencies are already current.
6. Start the API and frontend in separate PowerShell windows.
7. Poll the API health endpoint and frontend URL. Open the frontend in the default browser only after both respond.
8. Print service URLs and, only when generated on this run, the initial administrator credentials.

## Failure behavior

Each prerequisite or setup command is checked before continuing. On failure, the launcher prints the failing stage, preserves already-created configuration and database data, and exits non-zero. It does not automatically tear down services because doing so could hide logs or interrupt a database container that was already running.

If the expected ports are occupied, Docker or the application process reports the conflict and readiness checks fail with a concise diagnostic. The script does not terminate unrelated processes.

## Security boundaries

Generated credentials are for local development only. The API binds to `127.0.0.1`; MySQL is exposed only to the local host through port `33306`. Secrets remain in ignored `api/.env`. The script never replaces a user-managed `.env`.

## Verification

Automated PowerShell checks will validate the launcher's static contract and first-run configuration logic without starting long-lived terminals. End-to-end verification will then run the actual launcher, confirm MySQL health, confirm the migration reaches `head`, and request the API and frontend URLs. Any processes started for verification will be stopped without deleting the development database volume.
