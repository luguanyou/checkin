from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from attendance_api.schemas.common import ApiModel, TimestampedApiModel


def _trim_required(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("value cannot be blank")
    return normalized


class CreateCourseRequest(ApiModel):
    name: str = Field(max_length=120)
    code: str = Field(max_length=50)
    term: str = Field(max_length=50)

    @field_validator("name", "code", "term")
    @classmethod
    def trim_fields(cls, value: str) -> str:
        return _trim_required(value)


class UpdateCourseRequest(ApiModel):
    name: str | None = Field(default=None, max_length=120)
    code: str | None = Field(default=None, max_length=50)
    term: str | None = Field(default=None, max_length=50)
    status: Literal["ACTIVE", "ARCHIVED"] | None = None

    @field_validator("name", "code", "term")
    @classmethod
    def trim_fields(cls, value: str | None) -> str | None:
        return _trim_required(value) if value is not None else None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        return self


class CreateClassGroupRequest(ApiModel):
    name: str = Field(max_length=120)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        return _trim_required(value)


class UpdateClassGroupRequest(ApiModel):
    name: str | None = Field(default=None, max_length=120)
    status: Literal["ACTIVE", "ARCHIVED"] | None = None

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str | None) -> str | None:
        return _trim_required(value) if value is not None else None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        return self


class ClassGroupResponse(ApiModel):
    id: str
    name: str
    status: str
    active_student_count: int


class CourseResponse(TimestampedApiModel):
    id: str
    name: str
    code: str
    term: str
    status: str
    classes: list[ClassGroupResponse]


class CourseListResponse(ApiModel):
    items: list[CourseResponse]
    page: int
    page_size: int
    total: int
