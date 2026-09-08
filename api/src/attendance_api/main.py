from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import APIRouter, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from attendance_api.admin_bootstrap import bootstrap_configured_admin
from attendance_api.db import engine
from attendance_api.errors import (
    ApiError,
    api_error_handler,
    http_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from attendance_api.middleware.request_id import add_request_id
from attendance_api.modules.attendance.router import classes_router as attendance_classes_router
from attendance_api.modules.attendance.router import records_router
from attendance_api.modules.attendance.router import router as attendance_router
from attendance_api.modules.auth.router import router as auth_router
from attendance_api.modules.courses.router import classes_router
from attendance_api.modules.courses.router import router as courses_router
from attendance_api.modules.exports.router import router as exports_router
from attendance_api.modules.imports.router import router as imports_router
from attendance_api.modules.rosters.router import enrollments_router
from attendance_api.modules.rosters.router import router as rosters_router
from attendance_api.modules.tts.router import router as tts_router
from attendance_api.modules.users.router import router as users_router
from attendance_api.schemas.common import ErrorResponse

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status_code: {"model": ErrorResponse, "description": "统一错误响应"}
    for status_code in (400, 401, 403, 404, 409, 413, 422, 429, 500)
}
OPENAPI_TAGS = [
    {"name": "health", "description": "服务存活与就绪状态"},
    {"name": "auth", "description": "认证和会话管理"},
    {"name": "admin-users", "description": "管理员教师账号管理"},
    {"name": "courses", "description": "课程管理"},
    {"name": "classes", "description": "班级管理"},
    {"name": "rosters", "description": "班级名单管理"},
    {"name": "roster-imports", "description": "名单导入"},
    {"name": "attendance", "description": "考勤场次与记录"},
    {"name": "exports", "description": "考勤导出"},
]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    bootstrap_configured_admin()
    yield


def _database_is_ready() -> bool:
    api_root = Path(__file__).resolve().parents[2]
    alembic_config = Config(str(api_root / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(api_root / "migrations"))
    expected_heads = set(ScriptDirectory.from_config(alembic_config).get_heads())

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            current_revision = MigrationContext.configure(connection).get_current_revision()
    except Exception:
        return False

    return {current_revision} == expected_heads


def create_app() -> FastAPI:
    app = FastAPI(
        title="智能课堂考勤 API",
        version="1.0.0",
        openapi_tags=OPENAPI_TAGS,
        responses=ERROR_RESPONSES,
        lifespan=lifespan,
    )
    app.middleware("http")(add_request_id)
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)
    health_router = APIRouter(prefix="/api/v1/health", tags=["health"])

    @health_router.get("/live", operation_id="getHealthLive")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @health_router.get("/ready", operation_id="getHealthReady")
    def ready() -> JSONResponse:
        is_ready = _database_is_ready()
        return JSONResponse(
            status_code=200 if is_ready else 503,
            content={"status": "ready" if is_ready else "not_ready"},
        )

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(courses_router)
    app.include_router(classes_router)
    app.include_router(rosters_router)
    app.include_router(enrollments_router)
    app.include_router(imports_router)
    app.include_router(attendance_classes_router)
    app.include_router(attendance_router)
    app.include_router(records_router)
    app.include_router(exports_router)
    app.include_router(tts_router)
    return app


app = create_app()
