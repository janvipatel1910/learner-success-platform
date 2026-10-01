"""Database checks for sequential module progression."""

import os
from contextlib import contextmanager
from uuid import UUID

import pytest
from sqlalchemy import text

from skillpulse.db import module_progress as repository
from skillpulse.db.connection import get_engine

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "true",
    reason="Set RUN_DATABASE_TESTS=true to run database checks.",
)

ORG = UUID("10000000-0000-0000-0000-000000000001")
COURSE = UUID("40000000-0000-0000-0000-000000000001")
COHORT = UUID("42000000-0000-0000-0000-000000000001")
LEARNER = UUID("20000000-0000-0000-0000-000000000003")

CONTEXT = {
    "organization_id": ORG,
    "course_id": COURSE,
    "cohort_id": COHORT,
    "learner_id": LEARNER,
}


@pytest.fixture
def database(monkeypatch):
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            # Isolate this learner's progress inside a rolled-back transaction.
            connection.execute(
                text(
                    """
                    DELETE FROM module_progress
                    WHERE cohort_id = :cohort_id
                      AND learner_id = :learner_id
                    """
                ),
                CONTEXT,
            )

            class TransactionEngine:
                @contextmanager
                def begin(self):
                    yield connection

            monkeypatch.setattr(
                repository,
                "get_engine",
                lambda: TransactionEngine(),
            )

            modules = repository.list_learner_modules(**CONTEXT)
            assert len(modules) >= 2, (
                "The demo course needs at least two topics."
            )
            yield connection, modules
        finally:
            transaction.rollback()


def test_first_available_and_later_modules_locked(database):
    _, modules = database

    assert modules[0]["status"] == "available"
    assert all(
        module["status"] == "locked" for module in modules[1:]
    )


def test_locked_module_cannot_be_started(database):
    connection, modules = database

    with pytest.raises(repository.ModuleLocked):
        repository.start_learner_module(
            **CONTEXT, topic_id=modules[1]["topic_id"]
        )

    count = connection.execute(
        text(
            """
            SELECT COUNT(*) FROM module_progress
            WHERE cohort_id = :cohort_id
              AND learner_id = :learner_id
            """
        ),
        CONTEXT,
    ).scalar_one()

    assert count == 0


def test_start_is_idempotent(database):
    connection, modules = database
    topic_id = modules[0]["topic_id"]

    first = repository.start_learner_module(
        **CONTEXT, topic_id=topic_id
    )
    second = repository.start_learner_module(
        **CONTEXT, topic_id=topic_id
    )

    assert first["status"] == "in_progress"
    assert first["started_at"] is not None
    assert second == first

    count = connection.execute(
        text(
            """
            SELECT COUNT(*) FROM module_progress
            WHERE cohort_id = :cohort_id
              AND learner_id = :learner_id
              AND topic_id = :topic_id
            """
        ),
        {**CONTEXT, "topic_id": topic_id},
    ).scalar_one()

    assert count == 1
    assert repository.list_learner_modules(
        **CONTEXT
    )[1]["status"] == "locked"


def test_completed_predecessor_unlocks_next_module(database):
    connection, modules = database
    first_topic = modules[0]["topic_id"]

    repository.start_learner_module(
        **CONTEXT, topic_id=first_topic
    )

    # Test fixture only: simulate a verified completion.
    # The production completion workflow is not implemented yet.
    connection.execute(
        text(
            """
            UPDATE module_progress
            SET status = 'completed',
                completed_at = NOW()
            WHERE cohort_id = :cohort_id
              AND learner_id = :learner_id
              AND topic_id = :topic_id
            """
        ),
        {**CONTEXT, "topic_id": first_topic},
    )

    updated = repository.list_learner_modules(**CONTEXT)
    assert updated[0]["status"] == "completed"
    assert updated[1]["status"] == "available"

    next_module = repository.start_learner_module(
        **CONTEXT, topic_id=modules[1]["topic_id"]
    )
    assert next_module["status"] == "in_progress"

    completed = repository.start_learner_module(
        **CONTEXT, topic_id=first_topic
    )
    assert completed["status"] == "completed"
    assert completed["completed_at"] is not None


def test_wrong_organisation_cannot_read_or_start(database):
    _, modules = database
    other_context = {
        **CONTEXT,
        "organization_id": UUID(
            "10000000-0000-0000-0000-000000000099"
        ),
    }

    with pytest.raises(repository.ModuleAccessDenied):
        repository.list_learner_modules(**other_context)

    with pytest.raises(repository.ModuleAccessDenied):
        repository.start_learner_module(
            **other_context, topic_id=modules[0]["topic_id"]
        )


def test_unknown_topic_cannot_be_started(database):
    with pytest.raises(repository.ModuleNotFound):
        repository.start_learner_module(
            **CONTEXT,
            topic_id=UUID(
                "41000000-0000-0000-0000-000000000099"
            ),
        )
