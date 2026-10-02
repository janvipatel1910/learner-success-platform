"""Tutor review API authorization and validation tests."""

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from skillpulse.api.dependencies.auth import get_current_user
from skillpulse.api.routes import final_project_reviews as routes
from skillpulse.db.identity import (
    AuthenticatedUser,
    MembershipRole,
    OrganizationMembership,
)

ORG = UUID("10000000-0000-0000-0000-000000000001")
COURSE = UUID("40000000-0000-0000-0000-000000000001")
COHORT = UUID("42000000-0000-0000-0000-000000000001")
TUTOR = UUID("20000000-0000-0000-0000-000000000002")
LEARNER = UUID("20000000-0000-0000-0000-000000000003")
SUBMISSION = UUID("66000000-0000-0000-0000-000000000099")

BASE = (
    f"/api/v1/catalog/courses/{COURSE}/cohorts/{COHORT}"
    "/final-project/submissions"
)
REVIEW = f"{BASE}/{SUBMISSION}/review"
HEADERS = {"X-Organization-ID": str(ORG)}


def make_user(role=MembershipRole.TUTOR):
    return AuthenticatedUser(
        user_id=TUTOR,
        email="tutor@example.test",
        full_name="Test Tutor",
        memberships=(
            OrganizationMembership(
                organization_id=ORG,
                organization_name="Test Organisation",
                organization_slug="test",
                role=role,
            ),
        ),
    )


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(routes.router, prefix="/api/v1")
    return application


@pytest.fixture
def client(app):
    app.dependency_overrides[get_current_user] = lambda: make_user()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def payload():
    return {
        "expected_review_status": "submitted",
        "review_status": "approved",
        "score": 85,
        "tutor_feedback": "Reviewed the architecture and recovery evidence.",
    }


def test_review_uses_authenticated_tutor(client, monkeypatch):
    captured = {}

    def fake_review(**kwargs):
        captured.update(kwargs)
        return {
            "submission_id": SUBMISSION,
            "submission_number": 1,
            "submission_url": "https://example.com/project",
            "note": "Architecture and recovery plan.",
            "review_status": "approved",
            "score": 85,
            "tutor_feedback": kwargs["tutor_feedback"],
            "reviewed_by": kwargs["tutor_id"],
            "reviewed_at": "2026-10-01T12:00:00Z",
            "submitted_at": "2026-10-01T11:00:00Z",
            "learner_id": LEARNER,
            "learner_name": "Test Learner",
            "project_title": "Demo Project",
            "maximum_score": 100,
        }

    monkeypatch.setattr(
        routes.repository, "review_project_submission", fake_review
    )
    response = client.put(REVIEW, headers=HEADERS, json=payload())

    assert response.status_code == 200
    assert response.json()["reviewed_by"] == str(TUTOR)
    assert captured["tutor_id"] == TUTOR
    assert captured["organization_id"] == ORG
    assert captured["course_id"] == COURSE
    assert captured["cohort_id"] == COHORT
    assert captured["submission_id"] == SUBMISSION


@pytest.mark.parametrize(
    "role", [MembershipRole.STUDENT, MembershipRole.ADMIN]
)
def test_non_tutor_cannot_review(app, client, monkeypatch, role):
    app.dependency_overrides[get_current_user] = lambda: make_user(role)

    def unexpected_call(**kwargs):
        pytest.fail("A non-tutor reached the review repository.")

    monkeypatch.setattr(
        routes.repository, "review_project_submission", unexpected_call
    )
    response = client.put(REVIEW, headers=HEADERS, json=payload())
    assert response.status_code == 403


@pytest.mark.parametrize(
    ("error_type", "expected_status"),
    [
        (routes.repository.TutorAccessDenied, 403),
        (routes.repository.SubmissionNotFound, 404),
        (routes.repository.ReviewConflict, 409),
        (routes.repository.InvalidReview, 422),
    ],
)
def test_repository_errors_are_controlled(
    client, monkeypatch, error_type, expected_status
):
    def fake_review(**kwargs):
        raise error_type("Review unavailable.")

    monkeypatch.setattr(
        routes.repository, "review_project_submission", fake_review
    )
    response = client.put(REVIEW, headers=HEADERS, json=payload())
    assert response.status_code == expected_status


def test_cannot_choose_another_reviewer(client, monkeypatch):
    def unexpected_call(**kwargs):
        pytest.fail("Forged reviewer reached the repository.")

    monkeypatch.setattr(
        routes.repository, "review_project_submission", unexpected_call
    )
    body = payload()
    body["reviewed_by"] = str(uuid4())

    response = client.put(REVIEW, headers=HEADERS, json=body)
    assert response.status_code == 422


def test_other_organisation_is_forbidden(client, monkeypatch):
    def unexpected_call(**kwargs):
        pytest.fail("Another organisation reached the repository.")

    monkeypatch.setattr(
        routes.repository, "review_project_submission", unexpected_call
    )
    response = client.put(
        REVIEW,
        headers={"X-Organization-ID": str(uuid4())},
        json=payload(),
    )
    assert response.status_code == 403


def test_anonymous_review_is_rejected(app):
    with TestClient(app) as anonymous:
        response = anonymous.put(
            REVIEW, headers=HEADERS, json=payload()
        )
    assert response.status_code == 401


def test_student_cannot_list_submissions(app, client, monkeypatch):
    app.dependency_overrides[get_current_user] = (
        lambda: make_user(MembershipRole.STUDENT)
    )

    def unexpected_call(**kwargs):
        pytest.fail("Student reached the tutor submission list.")

    monkeypatch.setattr(
        routes.repository, "list_project_submissions", unexpected_call
    )
    response = client.get(BASE, headers=HEADERS)
    assert response.status_code == 403
