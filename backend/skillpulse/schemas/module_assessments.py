"""Module assessment API schemas."""

from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModuleQuestionResponse(BaseModel):
    id: UUID
    question_text: str
    options: list[str]


class ModuleCheckResponse(BaseModel):
    assessment_id: UUID
    title: str
    version: str
    pass_percentage: Decimal
    maximum_attempts: int
    attempts_remaining: int
    module_status: Literal["in_progress", "completed"]
    questions: list[ModuleQuestionResponse]


SingleAnswer = Annotated[list[str], Field(min_length=1, max_length=1)]


class ModuleCheckSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_id: UUID
    version: str = Field(pattern=r"^[a-f0-9]{64}$")
    answers: dict[UUID, SingleAnswer] = Field(
        min_length=1,
        max_length=100,
    )


class ModuleCheckResult(BaseModel):
    attempt_id: UUID
    score: Decimal
    percentage: Decimal
    passed: bool
    module_status: Literal["in_progress", "completed"]
