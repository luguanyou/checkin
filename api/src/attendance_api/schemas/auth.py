from datetime import UTC, datetime

from pydantic import Field, field_serializer

from attendance_api.schemas.common import ApiModel, TimestampedApiModel


class LoginRequest(ApiModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordRequest(ApiModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class UserResponse(TimestampedApiModel):
    id: str
    username: str
    display_name: str
    role: str
    status: str
    must_change_password: bool
    last_login_at: datetime | None

    @field_serializer("last_login_at", when_used="json")
    def serialize_optional_timestamp(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class LoginResponse(ApiModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
