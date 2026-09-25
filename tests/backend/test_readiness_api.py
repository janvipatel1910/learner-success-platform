"""Readiness API scoring and authorization tests."""

from unittest.mock import Mock
from uuid import UUID

import pytest

from skillpulse.api.dependencies.auth import get_current_user
from skillpulse.api.routes import readiness as routes
from skillpulse.db.identity import (
    AuthenticatedUser,
    MembershipRole,
    OrganizationMembership,
)
from skillpulse.schemas.enrollment import CohortRole
from skillpulse.core.config import get_settings

ORG = UUID("10000000-0000-0000-0000-000000000001")
OTHER_ORG = UUID("10000000-0000-0000-0000-000000000099")
COURSE = UUID("40000000-0000-0000-0000-000000000001")
COHORT = UUID("42000000-0000-0000-0000-000000000001")
LEARNER = UUID("20000000-0000-0000-0000-000000000003")
STAFF = UUID("20000000-0000-0000-0000-000000000002")
MODEL = UUID("80000000-0000-0000-0000-000000000001")

BASE = (
    f"{get_settings().api_prefix}/catalog"
    f"/courses/{COURSE}/cohorts/{COHORT}"
)
MY_URL = f"{BASE}/readiness/me"
STAFF_URL = f"{BASE}/learners/{LEARNER}/readiness"
HEADERS = {"X-Organization-ID": str(ORG)}


@pytest.fixture
def login(client):
    """Override identity only; keep route authorization active."""
    previous = client.app.dependency_overrides.copy()

    def authenticate(role, organization_id=ORG):
        user = AuthenticatedUser(
            user_id=LEARNER if role == MembershipRole.STUDENT else STAFF,
            email="test@example.com",
            full_name="Test User",
            memberships=(
                OrganizationMembership(
                    organization_id=organization_id,
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


@pytest.fixture
def repositories(monkeypatch):
    inputs = Mock(return_value={
        "readiness_model_id": MODEL,
        "component_weights_json": {
            "quiz": 0.20,
            "mock": 0.30,
            "lab": 0.20,
            "attendance": 0.15,
            "blockers": 0.15,
        },
        "readiness_threshold": 75,
        "minimum_mock_score": 70,
        "minimum_lab_completion": 80,
        "quiz_component": 80,
        "mock_component": 90,
        "lab_component": 100,
        "attendance_component": 80,
        "blocker_component": 70,
    })
    membership = Mock(return_value=True)

    monkeypatch.setattr(
        routes.readiness_repository, "get_readiness_inputs", inputs
    )
    monkeypatch.setattr(
        routes.membership_repository,
        "has_active_cohort_role",
        membership,
    )
    return inputs, membership


@pytest.mark.parametrize("url", [MY_URL, STAFF_URL])
def test_authentication_required(client, repositories, url):
    inputs, membership = repositories

    response = client.get(url, headers=HEADERS)

    assert response.status_code == 401
    inputs.assert_not_called()
    membership.assert_not_called()


def test_student_reads_own_readiness(client, login, repositories):
    login(MembershipRole.STUDENT)
    inputs, membership = repositories

    response = client.get(MY_URL, headers=HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["learner_id"] == str(LEARNER)
    assert body["readiness_model_id"] == str(MODEL)
    assert body["overall_score"] == 85.5
    assert body["readiness_level"] == "ready"
    assert body["explanation_json"]["components"]["mock"] == 90
    inputs.assert_called_once_with(ORG, COURSE, COHORT, LEARNER)
    membership.assert_called_once_with(
        ORG, COURSE, COHORT, LEARNER, CohortRole.LEARNER
    )


def test_student_cannot_use_staff_endpoint(client, login, repositories):
    login(MembershipRole.STUDENT)
    inputs, membership = repositories

    response = client.get(STAFF_URL, headers=HEADERS)

    assert response.status_code == 403
    inputs.assert_not_called()
    membership.assert_not_called()


def test_student_requires_active_membership(client, login, repositories):
    login(MembershipRole.STUDENT)
    inputs, membership = repositories
    membership.return_value = False

    response = client.get(MY_URL, headers=HEADERS)

    assert response.status_code == 403
    inputs.assert_not_called()


def test_assigned_tutor_can_read(client, login, repositories):
    login(MembershipRole.TUTOR)
    inputs, membership = repositories

    response = client.get(STAFF_URL, headers=HEADERS)

    assert response.status_code == 200
    inputs.assert_called_once_with(ORG, COURSE, COHORT, LEARNER)
    membership.assert_called_once_with(
        ORG, COURSE, COHORT, STAFF, CohortRole.TUTOR
    )


def test_unassigned_tutor_is_rejected(client, login, repositories):
    login(MembershipRole.TUTOR)
    inputs, membership = repositories
    membership.return_value = False

    response = client.get(STAFF_URL, headers=HEADERS)

    assert response.status_code == 403
    inputs.assert_not_called()


def test_admin_does_not_need_cohort_assignment(client, login, repositories):
    login(MembershipRole.ADMIN)
    inputs, membership = repositories
    membership.return_value = False

    response = client.get(STAFF_URL, headers=HEADERS)

    assert response.status_code == 200
    membership.assert_not_called()
    inputs.assert_called_once_with(ORG, COURSE, COHORT, LEARNER)


def test_other_organization_admin_is_rejected(client, login, repositories):
    login(MembershipRole.ADMIN, organization_id=OTHER_ORG)
    inputs, membership = repositories

    response = client.get(STAFF_URL, headers=HEADERS)

    assert response.status_code == 403
    inputs.assert_not_called()
    membership.assert_not_called()


def test_missing_readiness_returns_404(client, login, repositories):
    login(MembershipRole.ADMIN)
    inputs, _ = repositories
    inputs.return_value = None

    response = client.get(STAFF_URL, headers=HEADERS)

    assert response.status_code == 404
@pytest.fixture
def snapshot_writer(monkeypatch):
    writer = Mock(return_value={
        "id": UUID("90000000-0000-0000-0000-000000000001"),
        "learner_id": LEARNER,
        "cohort_id": COHORT,
        "readiness_model_id": MODEL,
        "overall_score": 85.5,
        "readiness_level": "ready",
    })
    monkeypatch.setattr(
        routes.readiness_repository,
        "create_readiness_snapshot",
        writer,
    )
    return writer


@pytest.mark.parametrize(
    ("role", "assigned", "expected_status"),
    [
        (MembershipRole.ADMIN, False, 201),
        (MembershipRole.TUTOR, True, 201),
        (MembershipRole.TUTOR, False, 403),
        (MembershipRole.STUDENT, True, 403),
    ],
)
def test_snapshot_permissions(
    client,
    login,
    repositories,
    snapshot_writer,
    role,
    assigned,
    expected_status,
):
    login(role)
    _, membership = repositories
    membership.return_value = assigned

    response = client.post(
        f"{STAFF_URL}/snapshots",
        headers=HEADERS,
    )

    assert response.status_code == expected_status

    if expected_status == 201:
        snapshot_writer.assert_called_once_with(
            ORG, COURSE, COHORT, LEARNER
        )
        assert response.json()["learner_id"] == str(LEARNER)
        assert response.json()["overall_score"] == 85.5
    else:
        snapshot_writer.assert_not_called()


def test_snapshot_requires_authentication(client, snapshot_writer):
    response = client.post(
        f"{STAFF_URL}/snapshots",
        headers=HEADERS,
    )

    assert response.status_code == 401
    snapshot_writer.assert_not_called()


def test_snapshot_rejects_other_organization(
    client, login, snapshot_writer
):
    login(MembershipRole.ADMIN, organization_id=OTHER_ORG)

    response = client.post(
        f"{STAFF_URL}/snapshots",
        headers=HEADERS,
    )

    assert response.status_code == 403
    snapshot_writer.assert_not_called()


def test_snapshot_missing_inputs_returns_404(
    client, login, snapshot_writer
):
    login(MembershipRole.ADMIN)
    snapshot_writer.return_value = None

    response = client.post(
        f"{STAFF_URL}/snapshots",
        headers=HEADERS,
    )

    assert response.status_code == 404


def test_snapshot_database_error_returns_503(
    client, login, snapshot_writer
):
    from sqlalchemy.exc import SQLAlchemyError

    login(MembershipRole.ADMIN)
    snapshot_writer.side_effect = SQLAlchemyError("Test failure")

    response = client.post(
        f"{STAFF_URL}/snapshots",
        headers=HEADERS,
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Readiness service is unavailable."
    )
@pytest.fixture
def history_reader(monkeypatch):
    reader = Mock(return_value=[])
    monkeypatch.setattr(
        routes.readiness_repository,
        "list_readiness_snapshots",
        reader,
    )
    return reader


@pytest.mark.parametrize(
    ("role", "own_history", "assigned", "expected_status"),
    [
        (MembershipRole.STUDENT, True, True, 200),
        (MembershipRole.STUDENT, True, False, 403),
        (MembershipRole.STUDENT, False, True, 403),
        (MembershipRole.TUTOR, False, True, 200),
        (MembershipRole.TUTOR, False, False, 403),
        (MembershipRole.ADMIN, False, False, 200),
    ],
)
def test_history_permissions(
    client,
    login,
    repositories,
    history_reader,
    role,
    own_history,
    assigned,
    expected_status,
):
    login(role)
    _, membership = repositories
    membership.return_value = assigned
    url = MY_URL if own_history else STAFF_URL

    response = client.get(
        f"{url}/snapshots",
        headers=HEADERS,
        params={"limit": 5, "offset": 2},
    )

    assert response.status_code == expected_status

    if expected_status == 200:
        assert response.json() == []
        history_reader.assert_called_once_with(
            ORG, COURSE, COHORT, LEARNER, limit=5, offset=2
        )
    else:
        history_reader.assert_not_called()


@pytest.mark.parametrize("url", [MY_URL, STAFF_URL])
def test_history_requires_authentication(client, history_reader, url):
    response = client.get(
        f"{url}/snapshots",
        headers=HEADERS,
    )

    assert response.status_code == 401
    history_reader.assert_not_called()


def test_history_rejects_other_organization(client, login, history_reader):
    login(MembershipRole.ADMIN, organization_id=OTHER_ORG)

    response = client.get(
        f"{STAFF_URL}/snapshots",
        headers=HEADERS,
    )

    assert response.status_code == 403
    history_reader.assert_not_called()


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
    ],
)
def test_history_rejects_invalid_pagination(
    client, login, history_reader, params
):
    login(MembershipRole.ADMIN)

    response = client.get(
        f"{STAFF_URL}/snapshots",
        headers=HEADERS,
        params=params,
    )

    assert response.status_code == 422
    history_reader.assert_not_called()


def test_history_returns_saved_records(client, login, history_reader):
    login(MembershipRole.ADMIN)
    history_reader.return_value = [
        {
            "id": MODEL,
            "learner_id": LEARNER,
            "overall_score": 85.5,
            "readiness_level": "ready",
        }
    ]

    response = client.get(
        f"{STAFF_URL}/snapshots",
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(MODEL),
            "learner_id": str(LEARNER),
            "overall_score": 85.5,
            "readiness_level": "ready",
        }
    ]
    history_reader.assert_called_once_with(
        ORG, COURSE, COHORT, LEARNER, limit=20, offset=0
    )


def test_history_database_error_returns_503(
    client, login, history_reader
):
    from sqlalchemy.exc import SQLAlchemyError

    login(MembershipRole.ADMIN)
    history_reader.side_effect = SQLAlchemyError("Test failure")

    response = client.get(
        f"{STAFF_URL}/snapshots",
        headers=HEADERS,
    )

    assert response.status_code == 503
