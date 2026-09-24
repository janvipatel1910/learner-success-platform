"""Validated API schemas for learner blockers and tutor interventions."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BlockerSeverity(StrEnum):
    """Supported blocker severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BlockerStatus(StrEnum):
    """Supported blocker workflow states."""

    OPEN = "open"
    ASSIGNED = "assigned"
    WAITING_STUDENT = "waiting_student"
    RESOLVED = "resolved"
    CLOSED = "closed"


class InterventionOutcome(StrEnum):
    """Supported tutor-intervention outcomes."""

    PENDING = "pending"
    IMPROVED = "improved"
    NO_CHANGE = "no_change"
    DECLINED = "declined"


class CompletedInterventionOutcome(StrEnum):
    """Outcomes allowed when completing an intervention."""

    IMPROVED = "improved"
    NO_CHANGE = "no_change"
    DECLINED = "declined"


class BlockerCreate(BaseModel):
    """Create a blocker for the authenticated learner."""

    topic_id: UUID | None = None
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    category: str = Field(min_length=1, max_length=80)
    severity: BlockerSeverity = BlockerSeverity.MEDIUM

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class BlockerUpdate(BaseModel):
    """Update a blocker and append an auditable blocker event."""

    assigned_tutor_id: UUID | None = None
    severity: BlockerSeverity | None = None
    status: BlockerStatus | None = None
    resolution_summary: str | None = Field(
        default=None,
        min_length=1,
        max_length=5000,
    )
    comment: str | None = Field(
        default=None,
        min_length=1,
        max_length=2000,
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    @model_validator(mode="after")
    def validate_update(self) -> "BlockerUpdate":
        """Reject empty updates and explicit null enum values."""

        fields = self.model_fields_set
        if not fields:
            raise ValueError("At least one blocker update field is required.")

        if "severity" in fields and self.severity is None:
            raise ValueError("severity cannot be null.")

        if "status" in fields and self.status is None:
            raise ValueError("status cannot be null.")

        if fields == {"comment"} and self.comment is None:
            raise ValueError("comment cannot be null.")

        return self


class InterventionCreate(BaseModel):
    """Create a tutor intervention linked to a blocker."""

    intervention_type: str = Field(min_length=1, max_length=80)
    action_taken: str = Field(min_length=1, max_length=5000)
    baseline_metric: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    baseline_value: Decimal | None = Field(
        default=None,
        max_digits=10,
        decimal_places=2,
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    @model_validator(mode="after")
    def validate_baseline(self) -> "InterventionCreate":
        """Require baseline metric and value to be supplied together."""

        has_metric = self.baseline_metric is not None
        has_value = self.baseline_value is not None
        if has_metric != has_value:
            raise ValueError(
                "baseline_metric and baseline_value must be supplied together."
            )

        return self


class InterventionCompletion(BaseModel):
    """Complete a pending tutor intervention."""

    outcome: CompletedInterventionOutcome
    follow_up_value: Decimal | None = Field(
        default=None,
        max_digits=10,
        decimal_places=2,
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class BlockerResponse(BaseModel):
    """A learner blocker returned by the API."""

    id: UUID
    learner_id: UUID
    learner_email: str
    learner_full_name: str
    cohort_id: UUID
    cohort_name: str
    course_id: UUID
    course_title: str
    topic_id: UUID | None
    topic_title: str | None
    title: str
    description: str
    category: str
    severity: BlockerSeverity
    status: BlockerStatus
    assigned_tutor_id: UUID | None
    assigned_tutor_email: str | None
    assigned_tutor_full_name: str | None
    opened_at: datetime
    resolved_at: datetime | None
    resolution_summary: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BlockerEventResponse(BaseModel):
    """One auditable event in a blocker's history."""

    id: UUID
    blocker_id: UUID
    actor_id: UUID
    actor_email: str
    actor_full_name: str
    event_type: str
    old_status: BlockerStatus | None
    new_status: BlockerStatus | None
    comment: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TutorInterventionResponse(BaseModel):
    """A tutor intervention returned by the API."""

    id: UUID
    learner_id: UUID
    cohort_id: UUID
    topic_id: UUID | None
    topic_title: str | None
    blocker_id: UUID | None
    intervention_type: str
    action_taken: str
    baseline_metric: str | None
    baseline_value: Decimal | None
    follow_up_value: Decimal | None
    outcome: InterventionOutcome
    tutor_id: UUID
    tutor_email: str
    tutor_full_name: str
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BlockerDetailResponse(BlockerResponse):
    """A blocker with its event timeline and tutor interventions."""

    events: list[BlockerEventResponse] = Field(default_factory=list)
    interventions: list[TutorInterventionResponse] = Field(
        default_factory=list
    )
