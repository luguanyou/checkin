from typing import Literal

from pydantic import Field, field_validator

from attendance_api.schemas.auth import UserResponse
from attendance_api.schemas.common import ApiModel


class CreateTeacherRequest(ApiModel):
    username: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=100)
    temporary_password: str

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("username cannot be blank")
        return normalized

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("display_name cannot be blank")
        return normalized


class UpdateUserStatusRequest(ApiModel):
    status: Literal["ACTIVE", "DISABLED"]


class ResetUserPasswordRequest(ApiModel):
    temporary_password: str


class UserListResponse(ApiModel):
    items: list[UserResponse]
    page: int
    page_size: int
    total: int
