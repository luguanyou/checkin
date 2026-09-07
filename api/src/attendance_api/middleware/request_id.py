from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response


def _is_valid_request_id(value: str | None) -> bool:
    return bool(
        value
        and len(value) <= 64
        and value.isascii()
        and all(character.isprintable() for character in value)
    )


async def add_request_id(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    supplied_request_id = request.headers.get("X-Request-ID")
    if _is_valid_request_id(supplied_request_id):
        assert supplied_request_id is not None
        request_id = supplied_request_id
    else:
        request_id = f"req_{uuid4().hex}"
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
