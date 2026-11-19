"""Module assignment submission and review schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

AssignmentReviewStatus = Literal["submitted", "changes_requested", "approved"]


class AssignmentSubmissionCreate(BaseModel):
    """A learner's written answer, with an optional HTTPS link."""

    model_config = ConfigDict(extra="forbid")

    submission_id: UUID
    answer_text: str = Field(min_length=50, max_length=5000)
    link_url: HttpUrl | None = None

    @field_validator("answer_text", mode="before")
    @classmethod
    def trim_answer(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("link_url", mode="before")
    @classmethod
    def empty_link_is_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value.strip() if isinstance(value, str) else value

    @field_validator("link_url")
    @classmethod
    def require_https(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value is None:
            return value
        if value.scheme != "https":
            raise ValueError("Use an HTTPS link.")
        if value.username is not None or value.password is not None:
            raise ValueError("Links must not contain credentials.")
        return value


class AssignmentSubmissionResponse(BaseModel):
    submission_id: UUID
    submission_number: int
    answer_text: str
    link_url: str | None
    review_status: AssignmentReviewStatus
    tutor_feedback: str | None
    reviewed_at: datetime | None
    submitted_at: datetime


class LearnerAssignmentResponse(BaseModel):
    assignment_id: UUID
    topic_id: UUID
    module_title: str
    title: str
    instructions: str
    can_submit: bool
    submission_block_reason: str | None
    latest_submission: AssignmentSubmissionResponse | None


class TutorAssignmentSubmissionResponse(AssignmentSubmissionResponse):
    assignment_id: UUID
    learner_id: UUID
    learner_name: str
    assignment_title: str
    module_title: str
    is_latest: bool


class AssignmentReview(BaseModel):
    """A tutor's decision on one answer. Feedback is always required."""

    model_config = ConfigDict(extra="forbid")

    review_status: Literal["approved", "changes_requested"]
    tutor_feedback: str = Field(min_length=10, max_length=5000)

    @field_validator("tutor_feedback", mode="before")
    @classmethod
    def trim_feedback(cls, value):
        return value.strip() if isinstance(value, str) else value
