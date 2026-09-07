from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy.orm import Session

from attendance_api.config import get_settings
from attendance_api.db import get_db
from attendance_api.models import User
from attendance_api.modules.auth.dependencies import get_current_user
from attendance_api.modules.auth.service import AuthResult
from attendance_api.modules.auth.service import change_password as change_password_service
from attendance_api.modules.auth.service import login as login_service
from attendance_api.modules.auth.service import logout as logout_service
from attendance_api.modules.auth.service import refresh as refresh_service
from attendance_api.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    UserResponse,
)
from attendance_api.security.tokens import InvalidAccessTokenError, decode_access_token

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
COOKIE_PATH = "/api/v1/auth"


def _client_ip(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key="refresh_token",
        value=token,
        max_age=settings.refresh_token_ttl_seconds,
        path=COOKIE_PATH,
        secure=settings.refresh_cookie_secure,
        httponly=True,
        samesite="strict",
    )


def _login_response(result: AuthResult) -> LoginResponse:
    return LoginResponse(
        access_token=result.access_token,
        expires_in=get_settings().access_token_ttl_seconds,
        user=UserResponse.model_validate(result.user),
    )


@router.post("/login", response_model=LoginResponse, operation_id="login")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> LoginResponse:
    result = login_service(
        db,
        username=payload.username,
        password=payload.password,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("User-Agent", ""),
    )
    _set_refresh_cookie(response, result.refresh_token)
    return _login_response(result)


@router.post("/refresh", response_model=LoginResponse, operation_id="refreshAccessToken")
def refresh(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> LoginResponse:
    if not refresh_token:
        from attendance_api.errors import ApiError

        raise ApiError(401, "AUTHENTICATION_REQUIRED", "请先登录")
    result = refresh_service(db, refresh_token=refresh_token, origin=request.headers.get("Origin"))
    _set_refresh_cookie(response, result.refresh_token)
    return _login_response(result)


@router.post("/logout", status_code=204, operation_id="logout")
def logout(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> Response:
    session_id: str | None = None
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        try:
            session_id = decode_access_token(authorization[7:])["sid"]
        except InvalidAccessTokenError:
            pass
    logout_service(db, refresh_token=refresh_token, session_id=session_id)
    response = Response(status_code=204)
    response.delete_cookie(
        "refresh_token",
        path=COOKIE_PATH,
        secure=get_settings().refresh_cookie_secure,
        httponly=True,
        samesite="strict",
    )
    return response


@router.get("/me", response_model=UserResponse, operation_id="getCurrentUser")
def me(user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse.model_validate(user)


@router.post("/change-password", response_model=LoginResponse, operation_id="changePassword")
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> LoginResponse:
    result = change_password_service(
        db,
        user=user,
        session_id=str(request.state.auth_session_id),
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    _set_refresh_cookie(response, result.refresh_token)
    return _login_response(result)
