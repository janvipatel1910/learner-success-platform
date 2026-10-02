"""Tutor final project review schemas."""

from decimal import Decimal
from typing import Literal
from uuid import UUID

from skillpulse.schemas.final_projects import (
    FinalProjectReview,
    FinalProjectSubmissionResponse,
)


class TutorProjectSubmissionResponse(FinalProjectSubmissionResponse):
    learner_id: UUID
    learner_name: str
    project_title: str
    maximum_score: Decimal


class TutorProjectReview(FinalProjectReview):
    expected_review_status: Literal["submitted", "under_review"]
