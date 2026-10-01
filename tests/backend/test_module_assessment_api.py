"""Module assessment API security and validation tests."""

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from skillpulse.api.dependencies.auth import get_current_user
from skillpulse.api.routes import module_assessments as routes
from skillpulse.db.identity import (
    AuthenticatedUser,
    MembershipRole,
    OrganizationMembership,
)

ORG = UUID("10000000-0000-0000-0000-000000000001")
COURSE = UUID("40000000-0000-0000-0000-000000000001")
COHORT = UUID("42000000-0000-0000-0000-000000000001")
LEARNER = UUID("20000000-0000-0000-0000-000000000003")
TOPIC = UUID("41000000-0000-0000-0000-000000000001")
QUESTION = UUID("62000000-0000-0000-0000-000000000001")

BASE = (
    f"/api/v1/catalog/courses/{COURSE}/cohorts/{COHORT}"
    f"/my-modules/{TOPIC}/check"
)
HEADERS = {"X-Organization-ID": str(ORG)}


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(routes.router, prefix="/api/v1")
    return application


@pytest.fixture
def client(app):
    user = AuthenticatedUser(
        user_id=LEARNER,
        email="learner@example.test",
        full_name="Test Learner",
        memberships=(
            OrganizationMembership(
                organization_id=ORG,
                organization_name="Test Organisation",
                organization_slug="test",
                role=MembershipRole.STUDENT,
            ),
        ),
    )
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def payload():
    return {
        "attempt_id": str(uuid4()),
        "version": "a" * 64,
        "answers": {str(QUESTION): ["Option B"]},
    }


def test_response_filters_answer_keys(client, monkeypatch):
    def fake_get(**kwargs):
        return {
            "assessment_id": uuid4(),
            "title": "Demo check",
            "version": "a" * 64,
            "pass_percentage": 100,
            "maximum_attempts": 3,
            "attempts_remaining": 3,
            "module_status": "in_progress",
            "questions": [{
                "id": QUESTION,
                "question_text": "Choose an option.",
                "options": ["Option A", "Option B"],
                "correct_answer_json": ["Option B"],
                "explanation": "Private answer explanation",
            }],
        }

    monkeypatch.setattr(routes.repository, "get_module_check", fake_get)
    response = client.get(BASE, headers=HEADERS)

    assert response.status_code == 200
    assert set(response.json()["questions"][0]) == {
        "id", "question_text", "options"
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("score", 100),
        ("passed", True),
        ("learner_id", str(uuid4())),
    ],
)
def test_client_cannot_supply_server_owned_fields(
    client, monkeypatch, field, value
):
    def unexpected_call(**kwargs):
        pytest.fail("Invalid request must not reach the repository.")

    monkeypatch.setattr(
        routes.repository, "submit_module_check", unexpected_call
    )
    body = payload()
    body[field] = value

    response = client.post(
        BASE + "/attempts", headers=HEADERS, json=body
    )
    assert response.status_code == 422


def test_submission_uses_authenticated_identity(client, monkeypatch):
    captured = {}

    def fake_submit(**kwargs):
        captured.update(kwargs)
        return {
            "attempt_id": kwargs["attempt_id"],
            "score": 1,
            "percentage": 100,
            "passed": True,
            "module_status": "completed",
        }

    monkeypatch.setattr(
        routes.repository, "submit_module_check", fake_submit
    )
    response = client.post(
        BASE + "/attempts", headers=HEADERS, json=payload()
    )

    assert response.status_code == 200
    assert captured["learner_id"] == LEARNER
    assert captured["organization_id"] == ORG
    assert captured["course_id"] == COURSE
    assert captured["cohort_id"] == COHORT
    assert captured["topic_id"] == TOPIC
    assert captured["answers"] == {str(QUESTION): ["Option B"]}


def test_anonymous_submission_is_rejected(app):
    with TestClient(app) as client:
        response = client.post(
            BASE + "/attempts", headers=HEADERS, json=payload()
        )
    assert response.status_code == 401


def test_other_organisation_is_rejected(client, monkeypatch):
    def unexpected_call(**kwargs):
        pytest.fail("Unauthorised request reached the repository.")

    monkeypatch.setattr(
        routes.repository, "submit_module_check", unexpected_call
    )
    response = client.post(
        BASE + "/attempts",
        headers={"X-Organization-ID": str(uuid4())},
        json=payload(),
    )
    assert response.status_code == 403


def test_attempt_limit_returns_conflict(client, monkeypatch):
    def fake_submit(**kwargs):
        raise routes.repository.CheckConflict("No attempts remain.")

    monkeypatch.setattr(
        routes.repository, "submit_module_check", fake_submit
    )
    response = client.post(
        BASE + "/attempts", headers=HEADERS, json=payload()
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "No attempts remain."
