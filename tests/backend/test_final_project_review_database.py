"""Database tests for assigned tutor final project reviews."""

import os
from contextlib import contextmanager
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from skillpulse.db import final_project_reviews as reviews
from skillpulse.db.connection import get_engine

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "true",
    reason="Set RUN_DATABASE_TESTS=true to run database checks.",
)

ORG = UUID("10000000-0000-0000-0000-000000000001")
COURSE = UUID("40000000-0000-0000-0000-000000000001")
COHORT = UUID("42000000-0000-0000-0000-000000000001")
TUTOR = UUID("20000000-0000-0000-0000-000000000002")
LEARNER = UUID("20000000-0000-0000-0000-000000000003")

CONTEXT = {
    "organization_id": ORG,
    "course_id": COURSE,
    "cohort_id": COHORT,
    "tutor_id": TUTOR,
}


@pytest.fixture
def database(monkeypatch):
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            task_id = connection.execute(
                text("""
                    SELECT lab_task_id
                    FROM course_final_projects
                    WHERE course_id = :course_id
                """),
                {"course_id": COURSE},
            ).scalar_one()

            submission_id = uuid4()

            connection.execute(
                text("""
                    INSERT INTO lab_submissions (
                        id, lab_task_id, learner_id, submission_number,
                        submission_url, evidence_json, review_status
                    )
                    VALUES (
                        :submission_id, :task_id, :learner_id, 1,
                        'https://example.com/project',
                        '{"note":"Architecture and recovery plan."}'::jsonb,
                        'submitted'
                    )
                """),
                {
                    "submission_id": submission_id,
                    "task_id": task_id,
                    "learner_id": LEARNER,
                },
            )

            connection.execute(
                text("""
                    INSERT INTO final_project_submissions (
                        submission_id, course_id, cohort_id,
                        lab_task_id, learner_id
                    )
                    VALUES (
                        :submission_id, :course_id, :cohort_id,
                        :task_id, :learner_id
                    )
                """),
                {
                    "submission_id": submission_id,
                    "course_id": COURSE,
                    "cohort_id": COHORT,
                    "task_id": task_id,
                    "learner_id": LEARNER,
                },
            )

            class TransactionEngine:
                @contextmanager
                def begin(self):
                    yield connection

            monkeypatch.setattr(
                reviews, "get_engine", lambda: TransactionEngine()
            )

            yield connection, submission_id

        finally:
            transaction.rollback()


def test_assigned_tutor_can_list_submission(database):
    _, submission_id = database

    items, total = reviews.list_project_submissions(
        **CONTEXT,
        limit=20,
        offset=0,
    )

    assert total >= 1
    assert any(
        item["submission_id"] == submission_id for item in items
    )


def test_assigned_tutor_can_approve_submission(database):
    connection, submission_id = database

    result = reviews.review_project_submission(
        **CONTEXT,
        submission_id=submission_id,
        expected_review_status="submitted",
        review_status="approved",
        score=Decimal("85"),
        tutor_feedback="Good architecture and clear recovery evidence.",
    )

    assert result["review_status"] == "approved"
    assert result["score"] == Decimal("85.00")
    assert result["reviewed_by"] == TUTOR

    saved = connection.execute(
        text("""
            SELECT review_status::text, score, reviewed_by
            FROM lab_submissions
            WHERE id = :submission_id
        """),
        {"submission_id": submission_id},
    ).mappings().one()

    assert saved["review_status"] == "approved"
    assert saved["score"] == Decimal("85.00")
    assert saved["reviewed_by"] == TUTOR


def test_approved_submission_cannot_be_reviewed_again(database):
    _, submission_id = database

    reviews.review_project_submission(
        **CONTEXT,
        submission_id=submission_id,
        expected_review_status="submitted",
        review_status="approved",
        score=Decimal("85"),
        tutor_feedback="Good architecture and clear recovery evidence.",
    )

    with pytest.raises(
        reviews.ReviewConflict,
        match="final review",
    ):
        reviews.review_project_submission(
            **CONTEXT,
            submission_id=submission_id,
            expected_review_status="approved",
            review_status="rejected",
            score=None,
            tutor_feedback="This should not overwrite approval.",
        )


def test_wrong_tutor_is_rejected(database):
    _, submission_id = database

    with pytest.raises(reviews.TutorAccessDenied):
        reviews.review_project_submission(
            **{**CONTEXT, "tutor_id": LEARNER},
            submission_id=submission_id,
            expected_review_status="submitted",
            review_status="approved",
            score=Decimal("85"),
            tutor_feedback="This reviewer is not assigned as tutor.",
        )


def test_approved_review_requires_score(database):
    _, submission_id = database

    with pytest.raises(
        reviews.InvalidReview,
        match="requires a score",
    ):
        reviews.review_project_submission(
            **CONTEXT,
            submission_id=submission_id,
            expected_review_status="submitted",
            review_status="approved",
            score=None,
            tutor_feedback="Approval without a score is invalid.",
        )


def test_short_feedback_is_rejected(database):
    _, submission_id = database

    with pytest.raises(
        reviews.InvalidReview,
        match="Feedback",
    ):
        reviews.review_project_submission(
            **CONTEXT,
            submission_id=submission_id,
            expected_review_status="submitted",
            review_status="rejected",
            score=None,
            tutor_feedback="Too short",
        )
