"""Practice assessment API authorization and error mapping."""

from unittest.mock import Mock
from uuid import UUID

import pytest

from skillpulse.api.dependencies.auth import get_current_user
from skillpulse.api.routes import practice_assessments as routes
from skillpulse.core.config import get_settings
from skillpulse.db.identity import (
    AuthenticatedUser,
    MembershipRole,
    OrganizationMembership,
)

ORG = UUID("10000000-0000-0000-0000-000000000001")
COURSE = UUID("40000000-0000-0000-0000-000000000001")
COHORT = UUID("42000000-0000-0000-0000-000000000001")
LEARNER = UUID("20000000-0000-0000-0000-000000000003")
ASSESSMENT = UUID("63000000-0000-0000-0000-000000000001")
ATTEMPT = UUID("64000000-0000-0000-0000-000000000001")
QUESTION = UUID("62000000-0000-0000-0000-000000000101")

BASE = (
    f"{get_settings().api_prefix}/catalog/courses/{COURSE}"
    f"/cohorts/{COHORT}/practice-assessments"
)
HEADERS = {"X-Organization-ID": str(ORG)}


@pytest.fixture
def login(client):
    previous = client.app.dependency_overrides.copy()

    def authenticate(role):
        user = AuthenticatedUser(
            user_id=LEARNER,
            email="learner@example.com",
            full_name="Test Learner",
            memberships=(
                OrganizationMembership(
                    organization_id=ORG,
                    organization_name="Test Organisation",
                    organization_slug="test-org",
                    role=role,
                ),
            ),
        )
        client.app.dependency_overrides[get_current_user] = lambda: user

    yield authenticate

    client.app.dependency_overrides.clear()
    client.app.dependency_overrides.update(previous)


SUMMARY = {
    "id": ASSESSMENT,
    "title": "VPC Practice Quiz",
    "assessment_type": "quiz",
    "question_count": 8,
    "time_limit_minutes": None,
    "pass_percentage": 70,
    "maximum_attempts": 5,
    "attempts_used": 1,
    "attempts_remaining": 4,
    "best_percentage": 62.5,
    "in_progress_attempt_id": None,
}

ATTEMPT_PAYLOAD = {
    "attempt_id": ATTEMPT,
    "assessment_id": ASSESSMENT,
    "title": "VPC Practice Quiz",
    "assessment_type": "quiz",
    "pass_percentage": 70,
    "started_at": "2026-10-21T10:00:00Z",
    "deadline": None,
    "questions": [{
        "id": QUESTION,
        "topic_title": "Networking and VPC",
        "question_text": "Which two?",
        "question_type": "multiple_choice",
        "select_count": 2,
        "options": ["A", "B", "C"],
    }],
}


def test_learner_lists_practice_assessments(client, login, monkeypatch):
    login(MembershipRole.STUDENT)
    listing = Mock(return_value=[SUMMARY])
    monkeypatch.setattr(routes.repository, "list_practice_assessments", listing)

    response = client.get(BASE, headers=HEADERS)

    assert response.status_code == 200
    assert response.json()[0]["attempts_remaining"] == 4
    listing.assert_called_once_with(
        organization_id=ORG,
        course_id=COURSE,
        cohort_id=COHORT,
        learner_id=LEARNER,
    )


def test_started_attempt_never_exposes_answer_keys(client, login, monkeypatch):
    login(MembershipRole.STUDENT)
    monkeypatch.setattr(
        routes.repository, "start_attempt", Mock(return_value=ATTEMPT_PAYLOAD)
    )

    response = client.post(f"{BASE}/{ASSESSMENT}/attempts", headers=HEADERS)

    assert response.status_code == 200
    question = response.json()["questions"][0]
    assert question["select_count"] == 2
    assert "correct_answer" not in question
    assert "explanation" not in question


@pytest.mark.parametrize(
    "role", [MembershipRole.TUTOR, MembershipRole.ADMIN]
)
def test_only_students_can_take_practice_assessments(client, login, role):
    login(role)

    response = client.get(BASE, headers=HEADERS)

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (routes.repository.PracticeAccessDenied(), 403),
        (routes.repository.PracticeNotFound(), 404),
        (routes.repository.PracticeConflict("No attempts remain."), 409),
        (routes.InvalidAnswers("Select only valid options."), 422),
        (routes.InvalidAssessment("bad"), 503),
    ],
)
def test_submit_maps_errors(client, login, monkeypatch, error, status):
    login(MembershipRole.STUDENT)
    monkeypatch.setattr(
        routes.repository, "submit_attempt", Mock(side_effect=error)
    )

    response = client.post(
        f"{BASE}/{ASSESSMENT}/attempts/{ATTEMPT}/submit",
        headers=HEADERS,
        json={"answers": {str(QUESTION): ["A"]}},
    )

    assert response.status_code == status


def test_submission_rejects_unknown_fields(client, login):
    login(MembershipRole.STUDENT)

    response = client.post(
        f"{BASE}/{ASSESSMENT}/attempts/{ATTEMPT}/submit",
        headers=HEADERS,
        json={"answers": {}, "score": 100},
    )

    assert response.status_code == 422


def test_submit_passes_answers_as_strings(client, login, monkeypatch):
    login(MembershipRole.STUDENT)
    submit = Mock(return_value={
        "attempt_id": ATTEMPT,
        "assessment_id": ASSESSMENT,
        "title": "VPC Practice Quiz",
        "score": 1,
        "percentage": 100,
        "passed": True,
        "submitted_at": "2026-10-21T10:05:00Z",
        "topics": [{"topic_title": "Networking and VPC", "correct": 1, "total": 1}],
        "questions": [{
            "id": QUESTION,
            "topic_title": "Networking and VPC",
            "question_text": "Which two?",
            "question_type": "multiple_choice",
            "options": ["A", "B", "C"],
            "selected": ["A", "B"],
            "correct_answer": ["A", "B"],
            "is_correct": True,
            "explanation": "Because.",
        }],
    })
    monkeypatch.setattr(routes.repository, "submit_attempt", submit)

    response = client.post(
        f"{BASE}/{ASSESSMENT}/attempts/{ATTEMPT}/submit",
        headers=HEADERS,
        json={"answers": {str(QUESTION): ["A", "B"]}},
    )

    assert response.status_code == 200
    assert response.json()["topics"][0]["correct"] == 1
    assert submit.call_args.kwargs["answers"] == {str(QUESTION): ["A", "B"]}
