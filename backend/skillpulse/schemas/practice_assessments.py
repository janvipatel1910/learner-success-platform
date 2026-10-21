"""Practice quiz and mock exam API schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

AssessmentType = Literal["quiz", "mock_exam"]
QuestionType = Literal["single_choice", "multiple_choice"]


class PracticeAssessmentSummary(BaseModel):
    id: UUID
    title: str
    assessment_type: AssessmentType
    question_count: int
    time_limit_minutes: int | None
    pass_percentage: Decimal
    maximum_attempts: int
    attempts_used: int
    attempts_remaining: int
    best_percentage: Decimal | None
    in_progress_attempt_id: UUID | None


class PracticeQuestion(BaseModel):
    id: UUID
    topic_title: str
    question_text: str
    question_type: QuestionType
    select_count: int
    options: list[str]


class PracticeAttempt(BaseModel):
    attempt_id: UUID
    assessment_id: UUID
    title: str
    assessment_type: AssessmentType
    pass_percentage: Decimal
    started_at: datetime
    deadline: datetime | None
    questions: list[PracticeQuestion]


Selection = Annotated[list[str], Field(max_length=10)]


class PracticeSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Unanswered questions may be omitted; they score zero.
    answers: dict[UUID, Selection] = Field(default_factory=dict, max_length=200)


class TopicBreakdown(BaseModel):
    topic_title: str
    correct: int
    total: int


class ReviewedQuestion(BaseModel):
    id: UUID
    topic_title: str
    question_text: str
    question_type: QuestionType
    options: list[str]
    selected: list[str]
    correct_answer: list[str]
    is_correct: bool
    explanation: str


class PracticeResult(BaseModel):
    attempt_id: UUID
    assessment_id: UUID
    title: str
    score: Decimal
    percentage: Decimal
    passed: bool
    submitted_at: datetime
    topics: list[TopicBreakdown]
    questions: list[ReviewedQuestion]
