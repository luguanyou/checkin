from datetime import UTC, datetime
from typing import Literal

from pydantic import field_serializer

from attendance_api.schemas.common import ApiModel, TimestampedApiModel


class StudentResponse(ApiModel):
    id: str
    student_number: str
    name: str
    gender: str | None
    major: str | None


class RosterMemberResponse(TimestampedApiModel):
    enrollment_id: str
    enrollment_status: str
    student: StudentResponse


class RosterListResponse(ApiModel):
    items: list[RosterMemberResponse]
    page: int
    page_size: int
    total: int


class ImportSummary(ApiModel):
    total: int
    valid: int
    errors: int
    duplicates: int
    importable: int


class ImportRow(ApiModel):
    row_number: int
    student_number: str
    name: str
    gender: str | None
    class_name: str
    major: str | None
    status: str
    code: str | None
    fields: list[str]
    message: str | None


class ImportPreviewResponse(ApiModel):
    preview_id: str
    expires_at: datetime
    summary: ImportSummary
    rows: list[ImportRow]

    @field_serializer("expires_at", when_used="json")
    def serialize_expiry(self, value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class ConfirmImportRequest(ApiModel):
    preview_id: str
    duplicate_policy: Literal["skip", "replace"]


class ConfirmImportResponse(ApiModel):
    preview_id: str
    created_students: int
    created_enrollments: int
    restored_enrollments: int
    skipped: int
    failed: int


class UpdateEnrollmentStatusRequest(ApiModel):
    status: Literal["ACTIVE", "REMOVED"]
