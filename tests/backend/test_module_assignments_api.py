"""Module assignment API tests (no database)."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from skillpulse.api.dependencies.auth import get_current_user
from skillpulse.api.routes import module_assignments as routes
from skillpulse.db.identity import (
    AuthenticatedUser,
    MembershipRole,
    OrganizationMembership,
)

ORG = UUID("10000000-0000-0000-0000-000000000001")
COURSE = UUID("40000000-0000-0000-0000-000000000001")
COHORT = UUID("42000000-0000-0000-0000-000000000001")
USER = UUID("20000000-0000-0000-0000-000000000003")
ASSIGNMENT = UUID("66000000-0000-0000-0000-000000000001")

COHORT_PATH = f"/api/v1/catalog/courses/{COURSE}/cohorts/{COHORT}"
HEADERS = {"X-Organization-ID": str(ORG)}
ANSWER = "My design uses public and private subnets in two Availability Zones."


def make_user(role):
    return AuthenticatedUser(
        user_id=USER,
        email="person@example.test",
        full_name="Test Person",
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
    yield application
    application.dependency_overrides.clear()


def client_as(app, role):
    app.dependency_overrides[get_current_user] = lambda: make_user(role)
    return TestClient(app)


def saved_submission(**overrides):
    return {
        "submission_id": uuid4(),
        "submission_number": 1,
        "answer_text": ANSWER,
        "link_url": None,
        "review_status": "submitted",
        "tutor_feedback": None,
        "reviewed_at": None,
        "submitted_at": datetime.now(UTC),
        **overrides,
    }


def test_learner_submission_uses_their_own_account(app, monkeypatch):
    captured = {}

    def fake_submit(**kwargs):
        captured.update(kwargs)
        return saved_submission(link_url=kwargs["link_url"])

    monkeypatch.setattr(routes.repository, "submit_assignment", fake_submit)
    client = client_as(app, MembershipRole.STUDENT)

    response = client.post(
        f"{COHORT_PATH}/my-assignments/{ASSIGNMENT}/submissions",
        headers=HEADERS,
        json={
            "submission_id": str(uuid4()),
            "answer_text": f"  {ANSWER}  ",
            "link_url": "https://github.com/example/design",
        },
    )

    assert response.status_code == 200
    assert captured["learner_id"] == USER
    assert captured["assignment_id"] == ASSIGNMENT
    assert captured["answer_text"] == ANSWER
    assert captured["link_url"] == "https://github.com/example/design"


def test_empty_link_is_saved_as_no_link(app, monkeypatch):
    captured = {}

    def fake_submit(**kwargs):
        captured.update(kwargs)
        return saved_submission()

    monkeypatch.setattr(routes.repository, "submit_assignment", fake_submit)
    client = client_as(app, MembershipRole.STUDENT)

    response = client.post(
        f"{COHORT_PATH}/my-assignments/{ASSIGNMENT}/submissions",
        headers=HEADERS,
        json={"submission_id": str(uuid4()), "answer_text": ANSWER, "link_url": ""},
    )

    assert response.status_code == 200
    assert captured["link_url"] is None


@pytest.mark.parametrize(
    "body",
    [
        {"answer_text": "Too short."},
        {"answer_text": ANSWER, "link_url": "http://example.com/plain"},
        {"answer_text": ANSWER, "link_url": "https://user:pass@example.com/x"},
        {"answer_text": ANSWER, "score": 90},
    ],
)
def test_invalid_answers_are_rejected(app, body):
    client = client_as(app, MembershipRole.STUDENT)

    response = client.post(
        f"{COHORT_PATH}/my-assignments/{ASSIGNMENT}/submissions",
        headers=HEADERS,
        json={"submission_id": str(uuid4()), **body},
    )

    assert response.status_code == 422


def test_tutor_cannot_submit_as_learner(app):
    client = client_as(app, MembershipRole.TUTOR)

    response = client.post(
        f"{COHORT_PATH}/my-assignments/{ASSIGNMENT}/submissions",
        headers=HEADERS,
        json={"submission_id": str(uuid4()), "answer_text": ANSWER},
    )

    assert response.status_code == 403


def test_learner_cannot_review(app):
    client = client_as(app, MembershipRole.STUDENT)

    response = client.put(
        f"{COHORT_PATH}/assignment-submissions/{uuid4()}/review",
        headers=HEADERS,
        json={"review_status": "approved", "tutor_feedback": "Great work here."},
    )

    assert response.status_code == 403


def test_review_only_allows_approve_or_changes(app):
    client = client_as(app, MembershipRole.TUTOR)

    response = client.put(
        f"{COHORT_PATH}/assignment-submissions/{uuid4()}/review",
        headers=HEADERS,
        json={"review_status": "rejected", "tutor_feedback": "Not accepted here."},
    )

    assert response.status_code == 422


def test_conflict_becomes_409(app, monkeypatch):
    def fake_submit(**kwargs):
        raise routes.repository.AssignmentConflict(
            "Your answer is waiting for tutor review."
        )

    monkeypatch.setattr(routes.repository, "submit_assignment", fake_submit)
    client = client_as(app, MembershipRole.STUDENT)

    response = client.post(
        f"{COHORT_PATH}/my-assignments/{ASSIGNMENT}/submissions",
        headers=HEADERS,
        json={"submission_id": str(uuid4()), "answer_text": ANSWER},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Your answer is waiting for tutor review."


def test_database_failure_becomes_503(app, monkeypatch):
    def fake_list(**kwargs):
        raise OperationalError("SELECT 1", {}, Exception("down"))

    monkeypatch.setattr(
        routes.repository, "list_learner_assignments", fake_list
    )
    client = client_as(app, MembershipRole.STUDENT)

    response = client.get(f"{COHORT_PATH}/my-assignments", headers=HEADERS)

    assert response.status_code == 503
    assert response.json()["detail"] == "Assignment service is unavailable."


def test_tutor_list_passes_status_filter(app, monkeypatch):
    captured = {}

    def fake_list(**kwargs):
        captured.update(kwargs)
        return [], 0

    monkeypatch.setattr(
        routes.repository, "list_assignment_submissions", fake_list
    )
    client = client_as(app, MembershipRole.TUTOR)

    response = client.get(
        f"{COHORT_PATH}/assignment-submissions?review_status=submitted",
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}
    assert captured["tutor_id"] == USER
    assert captured["review_status"] == "submitted"
