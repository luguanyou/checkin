from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ErrorResponse(ApiModel):
    code: str
    message: str
    details: dict[str, Any]
    request_id: str


class TimestampedApiModel(ApiModel):
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at", when_used="json")
    def serialize_timestamp(self, value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
