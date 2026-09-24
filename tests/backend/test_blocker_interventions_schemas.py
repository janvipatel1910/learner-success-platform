"""Tests for learner-blocker and tutor-intervention API schemas."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from skillpulse.schemas.blocker_interventions import (
    BlockerCreate,
    BlockerDetailResponse,
    BlockerSeverity,
    BlockerStatus,
    BlockerUpdate,
    CompletedInterventionOutcome,
    InterventionCompletion,
    InterventionCreate,
    InterventionOutcome,
)

_BLOCKER_ID = "70000000-0000-0000-0000-000000000001"
_EVENT_ID = "71000000-0000-0000-0000-000000000001"
_INTERVENTION_ID = "72000000-0000-0000-0000-000000000001"
_LEARNER_ID = "20000000-0000-0000-0000-000000000004"
_TUTOR_ID = "20000000-0000-0000-0000-000000000002"
_COHORT_ID = "42000000-0000-0000-0000-000000000001"
_COURSE_ID = "40000000-0000-0000-0000-000000000001"
_TOPIC_ID = "41000000-0000-0000-0000-000000000001"


def test_blocker_create_accepts_and_strips_valid_payload() -> None:
    blocker = BlockerCreate.model_validate(
        {
            "topic_id": _TOPIC_ID,
            "title": "  Private subnet routing confusion  ",
            "description": "  I cannot explain the NAT route path.  ",
            "category": "  concept  ",
            "severity": "high",
        }
    )

    assert blocker.topic_id == UUID(_TOPIC_ID)
    assert blocker.title == "Private subnet routing confusion"
    assert blocker.description == "I cannot explain the NAT route path."
    assert blocker.category == "concept"
    assert blocker.severity is BlockerSeverity.HIGH


def test_blocker_create_defaults_to_medium_severity() -> None:
    blocker = BlockerCreate.model_validate(
        {
            "title": "Need practice",
            "description": "I need another guided exercise.",
            "category": "practice",
        }
    )

    assert blocker.topic_id is None
    assert blocker.severity is BlockerSeverity.MEDIUM


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", ""),
        ("title", "x" * 201),
        ("description", " "),
        ("description", "x" * 5001),
        ("category", ""),
        ("category", "x" * 81),
    ],
)
def test_blocker_create_rejects_invalid_text(
    field: str,
    value: str,
) -> None:
    payload = {
        "title": "Routing issue",
        "description": "I need help with routing.",
        "category": "concept",
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        BlockerCreate.model_validate(payload)


def test_blocker_create_rejects_unknown_severity() -> None:
    with pytest.raises(ValidationError):
        BlockerCreate.model_validate(
            {
                "title": "Routing issue",
                "description": "I need help with routing.",
                "category": "concept",
                "severity": "urgent",
            }
        )


def test_blocker_create_rejects_client_supplied_identity() -> None:
    with pytest.raises(
        ValidationError,
        match="Extra inputs are not permitted",
    ):
        BlockerCreate.model_validate(
            {
                "title": "Routing issue",
                "description": "I need help with routing.",
                "category": "concept",
                "learner_id": _LEARNER_ID,
            }
        )


def test_blocker_update_accepts_valid_management_fields() -> None:
    update = BlockerUpdate.model_validate(
        {
            "assigned_tutor_id": _TUTOR_ID,
            "severity": "critical",
            "status": "assigned",
            "comment": "  Tutor assigned for urgent support.  ",
        }
    )

    assert update.assigned_tutor_id == UUID(_TUTOR_ID)
    assert update.severity is BlockerSeverity.CRITICAL
    assert update.status is BlockerStatus.ASSIGNED
    assert update.comment == "Tutor assigned for urgent support."


def test_blocker_update_rejects_empty_payload() -> None:
    with pytest.raises(
        ValidationError,
        match="At least one blocker update field is required",
    ):
        BlockerUpdate.model_validate({})


@pytest.mark.parametrize("field", ["severity", "status"])
def test_blocker_update_rejects_null_enums(field: str) -> None:
    with pytest.raises(
        ValidationError,
        match=f"{field} cannot be null",
    ):
        BlockerUpdate.model_validate({field: None})


def test_blocker_update_rejects_null_only_comment() -> None:
    with pytest.raises(
        ValidationError,
        match="comment cannot be null",
    ):
        BlockerUpdate.model_validate({"comment": None})


def test_intervention_create_accepts_complete_baseline() -> None:
    intervention = InterventionCreate.model_validate(
        {
            "intervention_type": "  targeted_practice  ",
            "action_taken": "  Provided a route-table exercise.  ",
            "baseline_metric": "  topic_score  ",
            "baseline_value": "60.00",
        }
    )

    assert intervention.intervention_type == "targeted_practice"
    assert intervention.action_taken == "Provided a route-table exercise."
    assert intervention.baseline_metric == "topic_score"
    assert intervention.baseline_value == Decimal("60.00")


@pytest.mark.parametrize(
    "payload",
    [
        {
            "intervention_type": "targeted_practice",
            "action_taken": "Provided a route-table exercise.",
            "baseline_metric": "topic_score",
        },
        {
            "intervention_type": "targeted_practice",
            "action_taken": "Provided a route-table exercise.",
            "baseline_value": 60,
        },
    ],
)
def test_intervention_create_rejects_incomplete_baseline(
    payload: dict[str, object],
) -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "baseline_metric and baseline_value "
            "must be supplied together"
        ),
    ):
        InterventionCreate.model_validate(payload)


def test_intervention_create_rejects_client_supplied_tutor() -> None:
    with pytest.raises(
        ValidationError,
        match="Extra inputs are not permitted",
    ):
        InterventionCreate.model_validate(
            {
                "intervention_type": "targeted_practice",
                "action_taken": "Provided a route-table exercise.",
                "tutor_id": _TUTOR_ID,
            }
        )


@pytest.mark.parametrize(
    "outcome",
    [
        "improved",
        "no_change",
        "declined",
    ],
)
def test_intervention_completion_accepts_final_outcomes(
    outcome: str,
) -> None:
    completion = InterventionCompletion.model_validate(
        {
            "outcome": outcome,
            "follow_up_value": "85.00",
        }
    )

    assert completion.outcome is CompletedInterventionOutcome(outcome)
    assert completion.follow_up_value == Decimal("85.00")


def test_intervention_completion_rejects_pending_outcome() -> None:
    with pytest.raises(ValidationError):
        InterventionCompletion.model_validate(
            {
                "outcome": "pending",
            }
        )


def test_blocker_detail_validates_nested_database_records() -> None:
    timestamp = datetime(2026, 8, 21, 10, 0, tzinfo=UTC)

    blocker = BlockerDetailResponse.model_validate(
        {
            "id": _BLOCKER_ID,
            "learner_id": _LEARNER_ID,
            "learner_email": "learner@example.com",
            "learner_full_name": "Synthetic Learner",
            "cohort_id": _COHORT_ID,
            "cohort_name": "AWS August Cohort",
            "course_id": _COURSE_ID,
            "course_title": "AWS Solutions Architecture",
            "topic_id": _TOPIC_ID,
            "topic_title": "VPC Networking",
            "title": "Private subnet routing confusion",
            "description": "Learner cannot explain the NAT route path.",
            "category": "concept",
            "severity": "high",
            "status": "assigned",
            "assigned_tutor_id": _TUTOR_ID,
            "assigned_tutor_email": "tutor@example.com",
            "assigned_tutor_full_name": "Synthetic Tutor",
            "opened_at": timestamp,
            "resolved_at": None,
            "resolution_summary": None,
            "created_at": timestamp,
            "updated_at": timestamp,
            "events": [
                {
                    "id": _EVENT_ID,
                    "blocker_id": _BLOCKER_ID,
                    "actor_id": _TUTOR_ID,
                    "actor_email": "tutor@example.com",
                    "actor_full_name": "Synthetic Tutor",
                    "event_type": "assigned",
                    "old_status": "open",
                    "new_status": "assigned",
                    "comment": "Tutor assigned.",
                    "created_at": timestamp,
                }
            ],
            "interventions": [
                {
                    "id": _INTERVENTION_ID,
                    "learner_id": _LEARNER_ID,
                    "cohort_id": _COHORT_ID,
                    "topic_id": _TOPIC_ID,
                    "topic_title": "VPC Networking",
                    "blocker_id": _BLOCKER_ID,
                    "intervention_type": "one_to_one_support",
                    "action_taken": "Scheduled a route-table walkthrough.",
                    "baseline_metric": "topic_score",
                    "baseline_value": "0.00",
                    "follow_up_value": None,
                    "outcome": "pending",
                    "tutor_id": _TUTOR_ID,
                    "tutor_email": "tutor@example.com",
                    "tutor_full_name": "Synthetic Tutor",
                    "started_at": timestamp,
                    "completed_at": None,
                    "created_at": timestamp,
                    "updated_at": timestamp,
                }
            ],
        }
    )

    assert blocker.id == UUID(_BLOCKER_ID)
    assert blocker.severity is BlockerSeverity.HIGH
    assert blocker.status is BlockerStatus.ASSIGNED
    assert blocker.events[0].new_status is BlockerStatus.ASSIGNED
    assert (
        blocker.interventions[0].outcome
        is InterventionOutcome.PENDING
    )
