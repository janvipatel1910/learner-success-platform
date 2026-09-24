"""PostgreSQL integration tests for blocker and intervention operations."""

import os
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from scripts.seed_synthetic_data import load_synthetic_data
from sqlalchemy import text

from skillpulse.db import blocker_interventions as repository
from skillpulse.db.connection import get_engine
from skillpulse.schemas.blocker_interventions import (
    BlockerCreate,
    BlockerSeverity,
    BlockerStatus,
    BlockerUpdate,
    InterventionCompletion,
    InterventionCreate,
    InterventionOutcome,
)

pytestmark = pytest.mark.integration

requires_database = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "true",
    reason="Set RUN_DATABASE_TESTS=true to run PostgreSQL integration tests",
)

requires_seed_tests = pytest.mark.skipif(
    os.getenv("RUN_SEED_TESTS") != "true",
    reason="Set RUN_SEED_TESTS=true to run synthetic seed tests",
)

ORGANIZATION_ID = UUID("10000000-0000-0000-0000-000000000001")
OTHER_ORGANIZATION_ID = UUID(
    "10000000-0000-0000-0000-000000000099"
)
COURSE_ID = UUID("40000000-0000-0000-0000-000000000001")
COHORT_ID = UUID("42000000-0000-0000-0000-000000000001")
TOPIC_ID = UUID("41000000-0000-0000-0000-000000000001")
TUTOR_USER_ID = UUID("20000000-0000-0000-0000-000000000002")
LEARNER_USER_ID = UUID(
    "20000000-0000-0000-0000-000000000004"
)
SEEDED_BLOCKER_ID = UUID(
    "70000000-0000-0000-0000-000000000001"
)


def delete_temporary_blocker(blocker_id: UUID | None) -> None:
    """Delete a test blocker after removing linked interventions."""

    if blocker_id is None:
        return

    with get_engine().begin() as connection:
        connection.execute(
            text(
                """
                DELETE FROM tutor_interventions
                WHERE blocker_id = :blocker_id
                """
            ),
            {"blocker_id": blocker_id},
        )
        connection.execute(
            text(
                """
                DELETE FROM blockers
                WHERE id = :blocker_id
                """
            ),
            {"blocker_id": blocker_id},
        )


@requires_database
@requires_seed_tests
def test_seeded_blockers_are_scoped_with_history() -> None:
    """Read seeded blockers without cross-organisation leakage."""

    load_synthetic_data()

    blockers, total = repository.list_my_blockers(
        ORGANIZATION_ID,
        LEARNER_USER_ID,
        status_filter=BlockerStatus.ASSIGNED,
        severity_filter=BlockerSeverity.HIGH,
        limit=20,
        offset=0,
    )

    assert total >= 1
    seeded = next(
        blocker
        for blocker in blockers
        if blocker.id == SEEDED_BLOCKER_ID
    )
    assert seeded.learner_id == LEARNER_USER_ID
    assert seeded.status is BlockerStatus.ASSIGNED
    assert seeded.severity is BlockerSeverity.HIGH
    assert seeded.assigned_tutor_id == TUTOR_USER_ID

    detail = repository.get_my_blocker(
        ORGANIZATION_ID,
        LEARNER_USER_ID,
        SEEDED_BLOCKER_ID,
    )

    assert detail is not None
    assert detail.events
    assert detail.interventions
    assert detail.interventions[0].outcome is InterventionOutcome.PENDING

    assert (
        repository.get_my_blocker(
            OTHER_ORGANIZATION_ID,
            LEARNER_USER_ID,
            SEEDED_BLOCKER_ID,
        )
        is None
    )

    staff_blockers, staff_total = repository.list_cohort_blockers(
        ORGANIZATION_ID,
        COURSE_ID,
        COHORT_ID,
        status_filter=None,
        severity_filter=None,
        limit=20,
        offset=0,
    )

    assert staff_total >= 2
    assert SEEDED_BLOCKER_ID in {
        blocker.id for blocker in staff_blockers
    }


@requires_database
@requires_seed_tests
def test_blocker_and_intervention_lifecycle_is_atomic() -> None:
    """Create, assign, support, complete and resolve one blocker."""

    load_synthetic_data()
    blocker_id: UUID | None = None

    try:
        created = repository.create_my_blocker(
            ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            LEARNER_USER_ID,
            BlockerCreate(
                topic_id=TOPIC_ID,
                title=f"SC-010 temporary blocker {uuid4()}",
                description="Temporary integration-test blocker.",
                category="integration_test",
                severity=BlockerSeverity.MEDIUM,
            ),
        )

        assert created is not None
        blocker_id = created.id
        assert created.status is BlockerStatus.OPEN
        assert len(created.events) == 1
        assert created.events[0].event_type == "created"

        assigned = repository.update_cohort_blocker(
            ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            blocker_id,
            TUTOR_USER_ID,
            BlockerUpdate(
                assigned_tutor_id=TUTOR_USER_ID,
                status=BlockerStatus.ASSIGNED,
                comment="Tutor accepted the blocker.",
            ),
        )

        assert assigned is not None
        assert assigned.status is BlockerStatus.ASSIGNED
        assert assigned.assigned_tutor_id == TUTOR_USER_ID

        intervention = repository.create_blocker_intervention(
            ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            blocker_id,
            TUTOR_USER_ID,
            InterventionCreate(
                intervention_type="targeted_practice",
                action_taken="Provided a focused routing exercise.",
                baseline_metric="topic_score",
                baseline_value=Decimal("40.00"),
            ),
        )

        assert intervention is not None
        assert intervention.outcome is InterventionOutcome.PENDING
        assert intervention.blocker_id == blocker_id

        completed = repository.complete_blocker_intervention(
            ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            blocker_id,
            intervention.id,
            TUTOR_USER_ID,
            InterventionCompletion(
                outcome="improved",
                follow_up_value=Decimal("85.00"),
            ),
        )

        assert completed is not None
        assert completed.outcome is InterventionOutcome.IMPROVED
        assert completed.follow_up_value == Decimal("85.00")
        assert completed.completed_at is not None

        assert (
            repository.complete_blocker_intervention(
                ORGANIZATION_ID,
                COURSE_ID,
                COHORT_ID,
                blocker_id,
                intervention.id,
                TUTOR_USER_ID,
                InterventionCompletion(
                    outcome="no_change",
                    follow_up_value=Decimal("85.00"),
                ),
            )
            is None
        )

        resolved = repository.update_cohort_blocker(
            ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            blocker_id,
            TUTOR_USER_ID,
            BlockerUpdate(
                status=BlockerStatus.RESOLVED,
                resolution_summary=(
                    "Learner completed the routing exercise successfully."
                ),
                comment="Blocker resolved after measured improvement.",
            ),
        )

        assert resolved is not None
        assert resolved.status is BlockerStatus.RESOLVED
        assert resolved.resolved_at is not None
        assert resolved.resolution_summary is not None
        assert len(resolved.events) == 5
        assert len(resolved.interventions) == 1

    finally:
        delete_temporary_blocker(blocker_id)


@requires_database
@requires_seed_tests
def test_blocker_creation_enforces_scope_and_topic() -> None:
    """Reject invalid organisations and topics during insertion."""

    load_synthetic_data()

    wrong_organization = repository.create_my_blocker(
        OTHER_ORGANIZATION_ID,
        COURSE_ID,
        COHORT_ID,
        LEARNER_USER_ID,
        BlockerCreate(
            topic_id=TOPIC_ID,
            title="Wrong organisation",
            description="This record must not be created.",
            category="scope_test",
        ),
    )
    assert wrong_organization is None

    wrong_topic = repository.create_my_blocker(
        ORGANIZATION_ID,
        COURSE_ID,
        COHORT_ID,
        LEARNER_USER_ID,
        BlockerCreate(
            topic_id=uuid4(),
            title="Wrong topic",
            description="This record must not be created.",
            category="scope_test",
        ),
    )
    assert wrong_topic is None


@requires_database
@requires_seed_tests
def test_blocker_assignment_requires_eligible_tutor() -> None:
    """Reject assignment to a user without active tutor eligibility."""

    load_synthetic_data()
    blocker_id: UUID | None = None

    try:
        created = repository.create_my_blocker(
            ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            LEARNER_USER_ID,
            BlockerCreate(
                topic_id=TOPIC_ID,
                title=f"SC-010 tutor eligibility {uuid4()}",
                description="Temporary tutor-eligibility test.",
                category="integration_test",
            ),
        )

        assert created is not None
        blocker_id = created.id

        updated = repository.update_cohort_blocker(
            ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            blocker_id,
            TUTOR_USER_ID,
            BlockerUpdate(
                assigned_tutor_id=uuid4(),
                status=BlockerStatus.ASSIGNED,
            ),
        )

        assert updated is None

        unchanged = repository.get_cohort_blocker(
            ORGANIZATION_ID,
            COURSE_ID,
            COHORT_ID,
            blocker_id,
        )

        assert unchanged is not None
        assert unchanged.status is BlockerStatus.OPEN
        assert unchanged.assigned_tutor_id is None
        assert len(unchanged.events) == 1

    finally:
        delete_temporary_blocker(blocker_id)
