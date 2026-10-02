"""Final project submission API tests."""

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from skillpulse.api.dependencies.auth import get_current_user
from skillpulse.api.routes import final_projects as routes
from skillpulse.db.identity import (
    AuthenticatedUser,
    MembershipRole,
    OrganizationMembership,
)

ORG = UUID("10000000-0000-0000-0000-000000000001")
COURSE = UUID("40000000-0000-0000-0000-000000000001")
COHORT = UUID("42000000-0000-0000-0000-000000000001")
LEARNER = UUID("20000000-0000-0000-0000-000000000003")

BASE = (
    f"/api/v1/catalog/courses/{COURSE}/cohorts/{COHORT}"
    "/my-final-project"
)
HEADERS = {"X-Organization-ID": str(ORG)}


def make_user(role=MembershipRole.STUDENT):
    return AuthenticatedUser(
        user_id=LEARNER,
        email="learner@example.test",
        full_name="Test Learner",
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
        "submission_id": str(uuid4()),
        "submission_url": "https://example.com/project",
        "note": "My architecture diagram and recovery plan are included.",
    }


def test_submission_uses_authenticated_learner(client, monkeypatch):
    captured = {}

    def fake_submit(**kwargs):
        captured.update(kwargs)
        return {
            "submission_id": kwargs["submission_id"],
            "submission_number": 1,
            "submission_url": kwargs["submission_url"],
            "note": kwargs["note"],
            "review_status": "submitted",
            "score": None,
            "tutor_feedback": None,
            "reviewed_by": None,
            "reviewed_at": None,
            "submitted_at": "2026-10-01T12:00:00Z",
        }

    monkeypatch.setattr(
        routes.repository, "submit_learner_final_project", fake_submit
    )

    response = client.post(
        BASE + "/submissions", headers=HEADERS, json=payload()
    )

    assert response.status_code == 200
    assert response.json()["review_status"] == "submitted"
    assert captured["learner_id"] == LEARNER
    assert captured["organization_id"] == ORG
    assert captured["course_id"] == COURSE
    assert captured["cohort_id"] == COHORT


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("score", 100),
        ("review_status", "approved"),
        ("learner_id", str(uuid4())),
        ("submission_url", "http://example.com/project"),
        ("submission_url", "https://user:password@example.com/project"),
        ("note", "          "),
    ],
)
def test_invalid_or_server_owned_fields_are_rejected(
    client, monkeypatch, field, value
):
    def unexpected_call(**kwargs):
        pytest.fail("Invalid input must not reach the repository.")

    monkeypatch.setattr(
        routes.repository,
        "submit_learner_final_project",
        unexpected_call,
    )
    body = payload()
    body[field] = value

    response = client.post(
        BASE + "/submissions", headers=HEADERS, json=body
    )
    assert response.status_code == 422


def test_anonymous_submission_is_rejected(app):
    with TestClient(app) as anonymous:
        response = anonymous.post(
            BASE + "/submissions", headers=HEADERS, json=payload()
        )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "role", [MembershipRole.TUTOR, MembershipRole.ADMIN]
)
def test_non_student_cannot_submit(app, client, monkeypatch, role):
    app.dependency_overrides[get_current_user] = lambda: make_user(role)

    def unexpected_call(**kwargs):
        pytest.fail("Forbidden role reached the repository.")

    monkeypatch.setattr(
        routes.repository,
        "submit_learner_final_project",
        unexpected_call,
    )

    response = client.post(
        BASE + "/submissions", headers=HEADERS, json=payload()
    )
    assert response.status_code == 403


def test_other_organisation_is_forbidden(client, monkeypatch):
    def unexpected_call(**kwargs):
        pytest.fail("Another organisation reached the repository.")

    monkeypatch.setattr(
        routes.repository,
        "submit_learner_final_project",
        unexpected_call,
    )

    response = client.post(
        BASE + "/submissions",
        headers={"X-Organization-ID": str(uuid4())},
        json=payload(),
    )
    assert response.status_code == 403


def test_pending_review_returns_conflict(client, monkeypatch):
    def fake_submit(**kwargs):
        raise routes.repository.FinalProjectConflict(
            "Your project is awaiting tutor review."
        )

    monkeypatch.setattr(
        routes.repository, "submit_learner_final_project", fake_submit
    )

    response = client.post(
        BASE + "/submissions", headers=HEADERS, json=payload()
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Your project is awaiting tutor review."
    )
