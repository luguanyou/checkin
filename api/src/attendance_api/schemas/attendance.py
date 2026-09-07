from datetime import UTC, date, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_serializer, field_validator

from attendance_api.schemas.common import ApiModel, TimestampedApiModel


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class CreateAttendanceSessionRequest(ApiModel):
    session_date: date


class ResourceSummary(ApiModel):
    id: str
    name: str


class CourseSummary(ResourceSummary):
    code: str


class ModifierSummary(ApiModel):
    id: str
    display_name: str


class AttendanceSummary(ApiModel):
    total: int
    pending: int
    present: int
    absent: int
    leave: int
    late: int
    exceptions: int


class AttendanceRecordResponse(ApiModel):
    id: str
    student_id: str
    student_number: str
    student_name: str
    class_name: str
    status: str
    marked_at: datetime | None
    last_modified_at: datetime | None
    last_modified_by: ModifierSummary
    version: int

    @field_serializer("marked_at", "last_modified_at", when_used="json")
    def serialize_optional_timestamp(self, value: datetime | None) -> datetime | None:
        return _as_utc(value)


class AttendanceSessionBase(TimestampedApiModel):
    id: str
    course: CourseSummary
    class_group: ResourceSummary
    session_date: date
    status: str
    started_at: datetime
    completed_at: datetime | None
    summary: AttendanceSummary

    @field_serializer("started_at", "completed_at", when_used="json")
    def serialize_session_timestamp(self, value: datetime | None) -> datetime | None:
        return _as_utc(value)


class AttendanceSessionResponse(AttendanceSessionBase):
    records: list[AttendanceRecordResponse]


class AttendanceSessionListResponse(ApiModel):
    items: list[AttendanceSessionBase]
    page: int
    page_size: int
    total: int


class UpdateAttendanceRecordRequest(ApiModel):
    status: Literal["present", "absent", "leave", "late"]
    expected_version: int = Field(ge=1)
    client_mutation_id: UUID
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None
