from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "req_unknown"))


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    request_id = _request_id(request)
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": request_id,
        },
        headers={"X-Request-ID": request_id},
    )


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return error_response(
        request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"type": item["type"], "location": list(item["loc"]), "message": item["msg"]}
        for item in exc.errors()
    ]
    return error_response(
        request,
        status_code=400,
        code="INVALID_REQUEST",
        message="请求参数无效",
        details={"errors": errors},
    )


async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if exc.status_code == 404:
        return error_response(
            request,
            status_code=404,
            code="RESOURCE_NOT_FOUND",
            message="请求的资源不存在",
        )
    return error_response(
        request,
        status_code=exc.status_code,
        code="INVALID_REQUEST",
        message="请求无效",
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return error_response(
        request,
        status_code=500,
        code="INTERNAL_ERROR",
        message="服务器内部错误",
    )
