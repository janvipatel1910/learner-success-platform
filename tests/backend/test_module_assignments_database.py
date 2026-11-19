"""Database checks for module assignments, tutor review and the certificate."""

import os
from contextlib import contextmanager
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from skillpulse.db import certificate_eligibility
from skillpulse.db import module_assignments as repository
from skillpulse.db.connection import get_engine

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_TESTS") != "true",
        reason="Set RUN_DATABASE_TESTS=true to run database checks.",
    ),
    pytest.mark.usefixtures("demo_course_content"),
]

SCOPE = {
    "organization_id": UUID("10000000-0000-0000-0000-000000000001"),
    "course_id": UUID("40000000-0000-0000-0000-000000000001"),
    "cohort_id": UUID("42000000-0000-0000-0000-000000000001"),
}
LEARNER = UUID("20000000-0000-0000-0000-000000000003")
OTHER_LEARNER = UUID("20000000-0000-0000-0000-000000000004")
TUTOR = UUID("20000000-0000-0000-0000-000000000002")
VPC_ASSIGNMENT = UUID("66000000-0000-0000-0000-000000000001")
S3_ASSIGNMENT = UUID("66000000-0000-0000-0000-000000000002")

ANSWER = (
    "I would use two public and two private subnets across two Availability "
    "Zones, with a NAT gateway in each public subnet."
)


@pytest.fixture
def database(monkeypatch):
    """Run each test in a transaction that is rolled back afterwards."""
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            count = connection.execute(
                text("""
                    SELECT COUNT(*) FROM module_assignments
                    WHERE course_id = :course_id AND status = 'published'
                """),
                SCOPE,
            ).scalar_one()
            assert count == 2, "Demo assignments must be seeded."

            class TransactionEngine:
                @contextmanager
                def begin(self):
                    yield connection

            for module in (repository, certificate_eligibility):
                monkeypatch.setattr(
                    module, "get_engine", lambda: TransactionEngine()
                )
            yield connection
        finally:
            transaction.rollback()


def submit(assignment_id=VPC_ASSIGNMENT, *, learner=LEARNER,
           submission_id=None, answer=ANSWER, link=None):
    return repository.submit_assignment(
        **SCOPE,
        learner_id=learner,
        assignment_id=assignment_id,
        submission_id=submission_id or uuid4(),
        answer_text=answer,
        link_url=link,
    )


def review(submission_id, status="approved",
           feedback="Clear design, well explained."):
    return repository.review_assignment_submission(
        **SCOPE,
        tutor_id=TUTOR,
        submission_id=submission_id,
        review_status=status,
        tutor_feedback=feedback,
    )


def my_assignments(learner=LEARNER):
    return {
        item["assignment_id"]: item
        for item in repository.list_learner_assignments(
            **SCOPE, learner_id=learner
        )
    }


def test_learner_sees_one_assignment_per_module(database):
    items = repository.list_learner_assignments(**SCOPE, learner_id=LEARNER)

    assert [item["module_title"] for item in items] == [
        "Networking and VPC",
        "Storage and S3",
    ]
    assert all(item["can_submit"] for item in items)
    assert all(item["latest_submission"] is None for item in items)


def test_submitted_answer_waits_for_review(database):
    saved = submit(link="https://github.com/example/vpc-design")

    assert saved["review_status"] == "submitted"
    assert saved["submission_number"] == 1
    item = my_assignments()[VPC_ASSIGNMENT]
    assert item["can_submit"] is False
    assert item["submission_block_reason"] == (
        "Your answer is waiting for tutor review."
    )
    assert item["latest_submission"]["link_url"] == (
        "https://github.com/example/vpc-design"
    )

    with pytest.raises(repository.AssignmentConflict):
        submit()


def test_same_submission_id_is_safe_to_retry(database):
    submission_id = uuid4()
    first = submit(submission_id=submission_id)
    again = submit(submission_id=submission_id)

    assert again["submission_id"] == first["submission_id"]

    with pytest.raises(repository.AssignmentConflict):
        submit(submission_id=submission_id, answer=ANSWER + " Changed.")


def test_changes_requested_allows_a_new_answer(database):
    first = submit()
    reviewed = review(
        first["submission_id"],
        status="changes_requested",
        feedback="Please add the database security group rule.",
    )
    assert reviewed["review_status"] == "changes_requested"
    assert reviewed["reviewed_by"] == TUTOR

    item = my_assignments()[VPC_ASSIGNMENT]
    assert item["can_submit"] is True
    assert item["latest_submission"]["tutor_feedback"] == (
        "Please add the database security group rule."
    )

    second = submit(answer=ANSWER + " The database allows 5432 from the web tier.")
    assert second["submission_number"] == 2

    # The older answer can no longer be reviewed.
    with pytest.raises(repository.AssignmentConflict):
        review(first["submission_id"])


def test_approved_answer_cannot_be_resubmitted_or_reviewed_again(database):
    saved = submit()
    review(saved["submission_id"])

    item = my_assignments()[VPC_ASSIGNMENT]
    assert item["latest_submission"]["review_status"] == "approved"
    assert item["submission_block_reason"] == "This assignment is already approved."

    with pytest.raises(repository.AssignmentConflict):
        submit()
    with pytest.raises(repository.AssignmentConflict):
        review(saved["submission_id"], status="changes_requested")


def test_tutor_sees_waiting_answers_first(database):
    reviewed = submit()
    review(reviewed["submission_id"], status="changes_requested",
           feedback="Add more detail please.")
    waiting = submit(S3_ASSIGNMENT, learner=OTHER_LEARNER)

    items, total = repository.list_assignment_submissions(
        **SCOPE, tutor_id=TUTOR
    )
    assert total == 2
    assert items[0]["submission_id"] == waiting["submission_id"]
    assert items[0]["learner_name"]

    only_waiting, waiting_total = repository.list_assignment_submissions(
        **SCOPE, tutor_id=TUTOR, review_status="submitted"
    )
    assert waiting_total == 1
    assert only_waiting[0]["submission_id"] == waiting["submission_id"]


def test_learner_cannot_review(database):
    saved = submit()

    with pytest.raises(repository.TutorAccessDenied):
        repository.review_assignment_submission(
            **SCOPE,
            tutor_id=OTHER_LEARNER,
            submission_id=saved["submission_id"],
            review_status="approved",
            tutor_feedback="Looks good to me.",
        )


def test_unknown_assignment_is_not_found(database):
    with pytest.raises(repository.AssignmentNotFound):
        submit(uuid4())


def test_learners_only_see_their_own_answers(database):
    submit()

    other = my_assignments(OTHER_LEARNER)[VPC_ASSIGNMENT]
    assert other["latest_submission"] is None
    assert other["can_submit"] is True


def test_certificate_needs_every_assignment_approved(database):
    def assignment_met():
        return certificate_eligibility.evaluate_certificate_eligibility(
            **SCOPE, learner_id=LEARNER
        )["assignment_met"]

    assert assignment_met() is False

    vpc = submit()
    review(vpc["submission_id"])
    assert assignment_met() is False

    s3 = submit(S3_ASSIGNMENT)
    review(s3["submission_id"])
    assert assignment_met() is True
