from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from typing import TypedDict, cast

import jwt
from jwt import PyJWTError

from attendance_api.config import get_settings

REQUIRED_CLAIMS = {"sub", "sid", "role", "must_change_password", "iat", "exp"}


class InvalidAccessTokenError(ValueError):
    pass


class AccessClaims(TypedDict):
    sub: str
    sid: str
    role: str
    must_change_password: bool
    iat: int
    exp: int


def generate_refresh_token() -> str:
    return token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def create_access_token(
    *, user_id: str, session_id: str, role: str, must_change_password: bool
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: AccessClaims = {
        "sub": user_id,
        "sid": session_id,
        "role": role,
        "must_change_password": must_change_password,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.access_token_ttl_seconds)).timestamp()),
    }
    return jwt.encode(dict(payload), settings.jwt_secret.get_secret_value(), algorithm="HS256")


def decode_access_token(token: str) -> AccessClaims:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            options={"require": sorted(REQUIRED_CLAIMS)},
        )
    except PyJWTError as exc:
        raise InvalidAccessTokenError from exc

    if not REQUIRED_CLAIMS.issubset(payload):
        raise InvalidAccessTokenError
    if not isinstance(payload["sub"], str) or not isinstance(payload["sid"], str):
        raise InvalidAccessTokenError
    if payload["role"] not in {"ADMIN", "TEACHER"}:
        raise InvalidAccessTokenError
    if not isinstance(payload["must_change_password"], bool):
        raise InvalidAccessTokenError
    return cast(AccessClaims, payload)
