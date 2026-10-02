"""Final project submission and review schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
)

ReviewStatus = Literal[
    "submitted",
    "under_review",
    "changes_requested",
    "approved",
    "rejected",
]


class FinalProjectSubmissionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submission_id: UUID
    submission_url: HttpUrl
    note: str = Field(min_length=10, max_length=5000)

    @field_validator("submission_url")
    @classmethod
    def require_https(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("Use an HTTPS project link.")
        if value.username is not None or value.password is not None:
            raise ValueError("Project links must not contain credentials.")
        return value

    @field_validator("note", mode="before")
    @classmethod
    def trim_note(cls, value):
        return value.strip() if isinstance(value, str) else value


class FinalProjectSubmissionResponse(BaseModel):
    submission_id: UUID
    submission_number: int
    submission_url: str
    note: str
    review_status: ReviewStatus
    score: Decimal | None
    tutor_feedback: str | None
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    submitted_at: datetime


class FinalProjectResponse(BaseModel):
    lab_task_id: UUID
    title: str
    instructions: str
    evidence_requirements: dict[str, object] | list[object]
    maximum_score: Decimal
    modules_completed: int
    modules_total: int
    can_submit: bool
    submission_block_reason: str | None
    latest_submission: FinalProjectSubmissionResponse | None


class FinalProjectReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_status: Literal[
        "under_review",
        "changes_requested",
        "approved",
        "rejected",
    ]
    score: Decimal | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    tutor_feedback: str = Field(min_length=10, max_length=5000)

    @field_validator("tutor_feedback", mode="before")
    @classmethod
    def trim_feedback(cls, value):
        return value.strip() if isinstance(value, str) else value
