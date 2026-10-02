"""Database checks for learner final project submissions."""

import os
from contextlib import contextmanager
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from skillpulse.db import final_projects as repository
from skillpulse.db.connection import get_engine
from skillpulse.db.module_progress import ModuleAccessDenied

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "true",
    reason="Set RUN_DATABASE_TESTS=true to run database checks.",
)

CONTEXT = {
    "organization_id": UUID("10000000-0000-0000-0000-000000000001"),
    "course_id": UUID("40000000-0000-0000-0000-000000000001"),
    "cohort_id": UUID("42000000-0000-0000-0000-000000000001"),
    "learner_id": UUID("20000000-0000-0000-0000-000000000003"),
}
VPC = UUID("41000000-0000-0000-0000-000000000001")
TUTOR = UUID("20000000-0000-0000-0000-000000000002")
URL = "https://example.com/demo-project"
NOTE = "Architecture diagram, recovery plan and validation checklist."


@pytest.fixture
def database(monkeypatch):
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            # Isolate this cohort's project history temporarily.
            submission_ids = connection.execute(
                text("""
                    DELETE FROM final_project_submissions
                    WHERE cohort_id = :cohort_id
                      AND learner_id = :learner_id
                    RETURNING submission_id
                """),
                CONTEXT,
            ).scalars().all()

            for submission_id in submission_ids:
                connection.execute(
                    text("DELETE FROM lab_submissions WHERE id = :id"),
                    {"id": submission_id},
                )

            # Fixture only: establish completed module prerequisites.
            connection.execute(
                text("""
                    INSERT INTO module_progress (
                        cohort_id, learner_id, topic_id,
                        status, started_at, completed_at
                    )
                    SELECT
                        :cohort_id, :learner_id, id,
                        'completed', NOW(), NOW()
                    FROM topics
                    WHERE course_id = :course_id
                    ON CONFLICT (cohort_id, learner_id, topic_id)
                    DO UPDATE SET
                        status = 'completed',
                        completed_at = GREATEST(
                            module_progress.started_at, NOW()
                        )
                """),
                CONTEXT,
            )

            class TransactionEngine:
                @contextmanager
                def begin(self):
                    yield connection

            monkeypatch.setattr(
                repository, "get_engine", lambda: TransactionEngine()
            )

            yield connection
        finally:
            transaction.rollback()


def submit(submission_id=None, note=NOTE):
    return repository.submit_learner_final_project(
        **CONTEXT,
        submission_id=submission_id or uuid4(),
        submission_url=URL,
        note=note,
    )


def set_review(connection, submission_id, review_status):
    connection.execute(
        text("""
            UPDATE lab_submissions
            SET review_status = :review_status,
                reviewed_by = :tutor,
                reviewed_at = NOW(),
                tutor_feedback = 'Test review feedback for this project.'
            WHERE id = :submission_id
        """),
        {
            "review_status": review_status,
            "tutor": TUTOR,
            "submission_id": submission_id,
        },
    )


def test_completed_modules_allow_submission(database):
    project = repository.get_learner_final_project(**CONTEXT)

    assert project["modules_total"] > 0
    assert project["modules_completed"] == project["modules_total"]
    assert project["can_submit"] is True

    saved = submit()
    assert saved["review_status"] == "submitted"
    assert saved["score"] is None
    assert saved["reviewed_by"] is None

    refreshed = repository.get_learner_final_project(**CONTEXT)
    assert refreshed["can_submit"] is False
    assert refreshed["latest_submission"]["submission_id"] == (
        saved["submission_id"]
    )


def test_incomplete_module_blocks_submission(database):
    database.execute(
        text("""
            UPDATE module_progress
            SET status = 'in_progress', completed_at = NULL
            WHERE cohort_id = :cohort_id
              AND learner_id = :learner_id
              AND topic_id = :topic_id
        """),
        {**CONTEXT, "topic_id": VPC},
    )

    assert repository.get_learner_final_project(
        **CONTEXT
    )["can_submit"] is False

    with pytest.raises(
        repository.FinalProjectConflict, match="Complete all modules"
    ):
        submit()


def test_retry_returns_same_submission(database):
    submission_id = uuid4()
    first = submit(submission_id)
    retry = submit(submission_id)

    assert retry == first

    count = database.execute(
        text("""
            SELECT COUNT(*) FROM final_project_submissions
            WHERE cohort_id = :cohort_id
              AND learner_id = :learner_id
        """),
        CONTEXT,
    ).scalar_one()
    assert count == 1


def test_same_identifier_with_different_content_is_rejected(database):
    submission_id = uuid4()
    submit(submission_id)

    with pytest.raises(
        repository.FinalProjectConflict, match="different content"
    ):
        submit(submission_id, note="Changed content with the same identifier.")


@pytest.mark.parametrize("review_status", ["submitted", "under_review"])
def test_pending_review_blocks_new_submission(database, review_status):
    saved = submit()
    set_review(database, saved["submission_id"], review_status)

    with pytest.raises(
        repository.FinalProjectConflict, match="awaiting tutor review"
    ):
        submit()


@pytest.mark.parametrize(
    "review_status", ["changes_requested", "rejected"]
)
def test_review_feedback_allows_resubmission(database, review_status):
    first = submit()
    set_review(database, first["submission_id"], review_status)

    second = submit()
    assert second["submission_number"] == first["submission_number"] + 1
    assert second["review_status"] == "submitted"
    assert second["reviewed_by"] is None


def test_approved_project_blocks_new_submission(database):
    saved = submit()
    set_review(database, saved["submission_id"], "approved")

    with pytest.raises(
        repository.FinalProjectConflict, match="already approved"
    ):
        submit()


def test_other_organisation_cannot_read_or_submit(database):
    other_context = {**CONTEXT, "organization_id": uuid4()}

    with pytest.raises(ModuleAccessDenied):
        repository.get_learner_final_project(**other_context)

    with pytest.raises(ModuleAccessDenied):
        repository.submit_learner_final_project(
            **other_context,
            submission_id=uuid4(),
            submission_url=URL,
            note=NOTE,
        )
