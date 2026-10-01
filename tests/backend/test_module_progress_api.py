"""Module progression API authorization and response tests."""

from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from skillpulse.api.dependencies.auth import get_current_user
from skillpulse.api.routes import module_progress as routes
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

BASE = (
    f"/api/v1/catalog/courses/{COURSE}"
    f"/cohorts/{COHORT}/my-modules"
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


def module_result(status="available"):
    return {
        "topic_id": TOPIC,
        "title": "Networking and VPC",
        "sequence_number": 1,
        "exam_domain": "Design Secure Architectures",
        "expected_hours": 6,
        "status": status,
        "started_at": (
            "2026-10-01T12:00:00Z"
            if status == "in_progress"
            else None
        ),
        "completed_at": None,
    }


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(routes.router, prefix="/api/v1")
    return application


@pytest.fixture
def client(app):
    app.dependency_overrides[get_current_user] = make_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_list_uses_authenticated_learner(client, monkeypatch):
    captured = {}

    def fake_list(**kwargs):
        captured.update(kwargs)
        return [module_result()]

    monkeypatch.setattr(
        routes.repository, "list_learner_modules", fake_list
    )

    response = client.get(BASE, headers=HEADERS)

    assert response.status_code == 200
    assert response.json()[0]["status"] == "available"
    assert captured == {
        "organization_id": ORG,
        "course_id": COURSE,
        "cohort_id": COHORT,
        "learner_id": LEARNER,
    }


def test_start_uses_authenticated_learner(client, monkeypatch):
    captured = {}

    def fake_start(**kwargs):
        captured.update(kwargs)
        return module_result("in_progress")

    monkeypatch.setattr(
        routes.repository, "start_learner_module", fake_start
    )

    response = client.post(
        f"{BASE}/{TOPIC}/start", headers=HEADERS
    )

    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"
    assert captured == {
        "organization_id": ORG,
        "course_id": COURSE,
        "cohort_id": COHORT,
        "learner_id": LEARNER,
        "topic_id": TOPIC,
    }


@pytest.mark.parametrize(
    ("error_type", "expected_status"),
    [
        (routes.repository.ModuleAccessDenied, 403),
        (routes.repository.ModuleNotFound, 404),
        (routes.repository.ModuleLocked, 409),
    ],
)
def test_start_maps_repository_errors(
    client, monkeypatch, error_type, expected_status
):
    def fake_start(**kwargs):
        raise error_type()

    monkeypatch.setattr(
        routes.repository, "start_learner_module", fake_start
    )

    response = client.post(
        f"{BASE}/{TOPIC}/start", headers=HEADERS
    )

    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "role", [MembershipRole.TUTOR, MembershipRole.ADMIN]
)
def test_non_student_cannot_start(app, client, monkeypatch, role):
    app.dependency_overrides[get_current_user] = lambda: make_user(role)

    def unexpected_call(**kwargs):
        pytest.fail("Repository must not run for a forbidden role.")

    monkeypatch.setattr(
        routes.repository, "start_learner_module", unexpected_call
    )

    response = client.post(
        f"{BASE}/{TOPIC}/start", headers=HEADERS
    )

    assert response.status_code == 403


def test_other_organisation_is_forbidden(client, monkeypatch):
    def unexpected_call(**kwargs):
        pytest.fail("Repository must not run for another organisation.")

    monkeypatch.setattr(
        routes.repository, "list_learner_modules", unexpected_call
    )

    response = client.get(
        BASE,
        headers={
            "X-Organization-ID":
                "10000000-0000-0000-0000-000000000099"
        },
    )

    assert response.status_code == 403


def test_missing_authentication_is_rejected(app):
    with TestClient(app) as anonymous_client:
        response = anonymous_client.get(BASE, headers=HEADERS)

    assert response.status_code == 401


def test_database_error_does_not_expose_details(client, monkeypatch):
    def fake_list(**kwargs):
        raise SQLAlchemyError("private database information")

    monkeypatch.setattr(
        routes.repository, "list_learner_modules", fake_list
    )

    response = client.get(BASE, headers=HEADERS)

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Module progression service is unavailable."
    )
    assert "private database information" not in response.text
