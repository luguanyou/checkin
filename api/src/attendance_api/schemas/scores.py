from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from attendance_api.schemas.common import ApiModel

ScoreCategory = Literal["HOMEWORK", "CLASSROOM", "LAB", "OTHER"]
CATEGORIES: tuple[ScoreCategory, ...] = ("HOMEWORK", "CLASSROOM", "LAB", "OTHER")
ScoreDecimal = Annotated[Decimal, Field(max_digits=20, decimal_places=4, allow_inf_nan=False)]
FactorDecimal = Annotated[ScoreDecimal, Field(ge=0)]


class ScoreSettings(ApiModel):
    base_score: ScoreDecimal | None
    factors: dict[ScoreCategory, FactorDecimal | None]

    @field_validator("factors")
    @classmethod
    def require_categories(
        cls, value: dict[ScoreCategory, Decimal | None]
    ) -> dict[ScoreCategory, Decimal | None]:
        if set(value) != set(CATEGORIES):
            raise ValueError("all four categories are required")
        return value


class SetScoreSettingsRequest(ScoreSettings):
    expected_version: int = Field(ge=0)


class CreateScoreItemRequest(ApiModel):
    expected_version: int = Field(ge=0)
    category: ScoreCategory
    name: str = Field(min_length=1, max_length=120)
    occurred_on: date
    description: str = Field(default="", max_length=500)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value


class UpdateScoreItemRequest(ApiModel):
    expected_version: int = Field(ge=0)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    occurred_on: date | None = None
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("name cannot be blank")
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        fields = self.model_fields_set - {"expected_version"}
        if not fields or any(getattr(self, name) is None for name in fields):
            raise ValueError("at least one non-null change is required")
        return self


class ScoreRecordInput(ApiModel):
    enrollment_id: str = Field(min_length=1, max_length=36)
    points: ScoreDecimal | None
    note: str = Field(default="", max_length=500)


class SetScoreRecordsRequest(ApiModel):
    expected_version: int = Field(ge=0)
    records: list[ScoreRecordInput] = Field(min_length=1, max_length=5000)

    @field_validator("records")
    @classmethod
    def no_duplicates(cls, value: list[ScoreRecordInput]) -> list[ScoreRecordInput]:
        if len({row.enrollment_id for row in value}) != len(value):
            raise ValueError("duplicate enrollment in batch")
        return value


class ScoreItem(ApiModel):
    id: str
    category: ScoreCategory
    name: str
    occurred_on: date
    description: str


class ScoreStudent(ApiModel):
    enrollment_id: str
    student_id: str
    student_number: str
    student_name: str
    enrollment_status: Literal["ACTIVE", "REMOVED"]


class ScoreRecord(ApiModel):
    id: str
    item_id: str
    enrollment_id: str
    points: ScoreDecimal | None
    note: str
    updated_at: str


class ScoreCategorySummary(ApiModel):
    category: ScoreCategory
    points: str
    contribution: str | None
    pending: int


class ScoreSummary(ApiModel):
    enrollment_id: str
    categories: list[ScoreCategorySummary]
    raw_score: str | None
    final_score: str | None
    status: Literal["READY", "RULES_PENDING", "RECORDS_PENDING"]


class ScoreScope(ApiModel):
    id: str
    name: str
    status: Literal["ACTIVE", "ARCHIVED"]


class ScoreBook(ApiModel):
    class_group: ScoreScope
    course: ScoreScope
    version: int
    readonly: bool
    rules_ready: bool
    settings: ScoreSettings
    items: list[ScoreItem]
    students: list[ScoreStudent]
    records: list[ScoreRecord]
    summaries: list[ScoreSummary]


class ScoreHistory(ApiModel):
    id: str
    action: str
    actor_name: str
    created_at: str
    before_value: dict[str, object] | None
    after_value: dict[str, object] | None


class ScoreHistoryResponse(ApiModel):
    items: list[ScoreHistory]
