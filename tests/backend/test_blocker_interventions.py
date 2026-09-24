"""Tests for learner blocker and tutor intervention API routes."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from skillpulse.api.dependencies.auth import get_current_user
from skillpulse.api.routes import blocker_interventions as routes
from skillpulse.db.identity import (
    AuthenticatedUser,
    MembershipRole,
    OrganizationMembership,
)
from skillpulse.schemas.blocker_interventions import (
    BlockerDetailResponse,
    BlockerResponse,
    BlockerSeverity,
    BlockerStatus,
    InterventionOutcome,
    TutorInterventionResponse,
)

ORGANIZATION_ID = UUID("10000000-0000-0000-0000-000000000001")
OTHER_ORGANIZATION_ID = UUID(
    "10000000-0000-0000-0000-000000000099"
)
AUTHENTICATED_USER_ID = UUID(
    "20000000-0000-0000-0000-000000000002"
)
OTHER_TUTOR_ID = UUID("20000000-0000-0000-0000-000000000099")
COURSE_ID = UUID("40000000-0000-0000-0000-000000000001")
COHORT_ID = UUID("42000000-0000-0000-0000-000000000001")
TOPIC_ID = UUID("41000000-0000-0000-0000-000000000001")
BLOCKER_ID = UUID("70000000-0000-0000-0000-000000000001")
INTERVENTION_ID = UUID(
    "72000000-0000-0000-0000-000000000001"
)

MY_BLOCKERS_PATH = "/api/v1/catalog/my-blockers"
CREATE_MY_BLOCKER_PATH = (
    f"/api/v1/catalog/courses/{COURSE_ID}"
    f"/cohorts/{COHORT_ID}/my-blockers"
)
COHORT_BLOCKERS_PATH = (
    f"/api/v1/catalog/courses/{COURSE_ID}"
    f"/cohorts/{COHORT_ID}/blockers"
)
BLOCKER_PATH = f"{COHORT_BLOCKERS_PATH}/{BLOCKER_ID}"
INTERVENTIONS_PATH = f"{BLOCKER_PATH}/interventions"
INTERVENTION_PATH = f"{INTERVENTIONS_PATH}/{INTERVENTION_ID}"

_TIMESTAMP = datetime(2026, 8, 21, 10, 0, tzinfo=UTC)

BLOCKER_ITEM = BlockerResponse(
    id=BLOCKER_ID,
    learner_id=AUTHENTICATED_USER_ID,
    learner_email="learner@skillpulse.example",
    learner_full_name="Synthetic Learner",
    cohort_id=COHORT_ID,
    cohort_name="AWS Cohort One",
    course_id=COURSE_ID,
    course_title="AWS Cloud Engineering",
    topic_id=TOPIC_ID,
    topic_title="VPC Foundations",
    title="Private subnet routing confusion",
    description="Learner cannot explain the NAT gateway route path.",
    category="concept",
    severity=BlockerSeverity.HIGH,
    status=BlockerStatus.ASSIGNED,
    assigned_tutor_id=AUTHENTICATED_USER_ID,
    assigned_tutor_email="tutor@skillpulse.example",
    assigned_tutor_full_name="Synthetic Tutor",
    opened_at=_TIMESTAMP,
    resolved_at=None,
    resolution_summary=None,
    created_at=_TIMESTAMP,
    updated_at=_TIMESTAMP,
)

BLOCKER_DETAIL = BlockerDetailResponse(
    **BLOCKER_ITEM.model_dump(),
    events=[],
    interventions=[],
)

PENDING_INTERVENTION = TutorInterventionResponse(
    id=INTERVENTION_ID,
    learner_id=AUTHENTICATED_USER_ID,
    cohort_id=COHORT_ID,
    topic_id=TOPIC_ID,
    topic_title="VPC Foundations",
    blocker_id=BLOCKER_ID,
    intervention_type="one_to_one_support",
    action_taken="Scheduled a VPC route-table walkthrough.",
    baseline_metric="topic_score",
    baseline_value=Decimal("40.00"),
    follow_up_value=None,
    outcome=InterventionOutcome.PENDING,
    tutor_id=AUTHENTICATED_USER_ID,
    tutor_email="tutor@skillpulse.example",
    tutor_full_name="Synthetic Tutor",
    started_at=_TIMESTAMP,
    completed_at=None,
    created_at=_TIMESTAMP,
    updated_at=_TIMESTAMP,
)

COMPLETED_INTERVENTION = PENDING_INTERVENTION.model_copy(
    update={
        "follow_up_value": Decimal("85.00"),
        "outcome": InterventionOutcome.IMPROVED,
        "completed_at": _TIMESTAMP,
    }
)


def build_user(role: MembershipRole) -> AuthenticatedUser:
    """Create a user with one active organisation role."""

    return AuthenticatedUser(
        user_id=AUTHENTICATED_USER_ID,
        email="current.user@skillpulse.example",
        full_name="Current User",
        memberships=(
            OrganizationMembership(
                organization_id=ORGANIZATION_ID,
                organization_name="SkillPulse Demo Academy",
                organization_slug="skillpulse-demo-academy",
                role=role,
            ),
        ),
    )


def create_test_application(role: MembershipRole) -> FastAPI:
    """Create an isolated application with SC-010 routes."""

    application = FastAPI()
    application.include_router(
        routes.router,
        prefix="/api/v1",
    )

    def override_current_user() -> AuthenticatedUser:
        return build_user(role)

    application.dependency_overrides[get_current_user] = (
        override_current_user
    )
    return application


def organization_headers(
    organization_id: UUID = ORGANIZATION_ID,
) -> dict[str, str]:
    """Return the required organisation header."""

    return {"X-Organization-ID": str(organization_id)}


def unexpected_repository_call(
    *_args: object,
    **_kwargs: object,
) -> None:
    """Fail if authorization should prevent repository access."""

    raise AssertionError("Repository must not be called.")


def permit_cohort_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Permit active cohort-role checks."""

    monkeypatch.setattr(
        routes.membership_repository,
        "has_active_cohort_role",
        lambda *_args: True,
    )


def test_learner_can_list_only_own_blockers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_list_my_blockers(
        organization_id: UUID,
        learner_id: UUID,
        *,
        status_filter: BlockerStatus | None,
        severity_filter: BlockerSeverity | None,
        limit: int,
        offset: int,
    ) -> tuple[list[BlockerResponse], int]:
        calls["list"] = (
            organization_id,
            learner_id,
            status_filter,
            severity_filter,
            limit,
            offset,
        )
        return [BLOCKER_ITEM], 1

    monkeypatch.setattr(
        routes.repository,
        "list_my_blockers",
        fake_list_my_blockers,
    )
    application = create_test_application(MembershipRole.STUDENT)

    with TestClient(application) as client:
        response = client.get(
            (
                f"{MY_BLOCKERS_PATH}?status=assigned"
                "&severity=high&limit=10&offset=2"
            ),
            headers=organization_headers(),
        )

    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == str(BLOCKER_ID)
    assert calls["list"] == (
        ORGANIZATION_ID,
        AUTHENTICATED_USER_ID,
        BlockerStatus.ASSIGNED,
        BlockerSeverity.HIGH,
        10,
        2,
    )


def test_learner_can_get_own_blocker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_get_my_blocker(
        organization_id: UUID,
        learner_id: UUID,
        blocker_id: UUID,
    ) -> BlockerDetailResponse:
        calls["get"] = (
            organization_id,
            learner_id,
            blocker_id,
        )
        return BLOCKER_DETAIL

    monkeypatch.setattr(
        routes.repository,
        "get_my_blocker",
        fake_get_my_blocker,
    )
    application = create_test_application(MembershipRole.STUDENT)

    with TestClient(application) as client:
        response = client.get(
            f"{MY_BLOCKERS_PATH}/{BLOCKER_ID}",
            headers=organization_headers(),
        )

    assert response.status_code == 200
    assert response.json()["id"] == str(BLOCKER_ID)
    assert calls["get"] == (
        ORGANIZATION_ID,
        AUTHENTICATED_USER_ID,
        BLOCKER_ID,
    )


def test_missing_own_blocker_returns_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        routes.repository,
        "get_my_blocker",
        lambda *_args: None,
    )
    application = create_test_application(MembershipRole.STUDENT)

    with TestClient(application) as client:
        response = client.get(
            f"{MY_BLOCKERS_PATH}/{BLOCKER_ID}",
            headers=organization_headers(),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Blocker was not found."


def test_active_learner_can_create_own_blocker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_create_my_blocker(
        organization_id: UUID,
        course_id: UUID,
        cohort_id: UUID,
        learner_id: UUID,
        payload: object,
    ) -> BlockerDetailResponse:
        calls["create"] = (
            organization_id,
            course_id,
            cohort_id,
            learner_id,
        )
        calls["payload"] = payload
        return BLOCKER_DETAIL

    permit_cohort_access(monkeypatch)
    monkeypatch.setattr(
        routes.repository,
        "create_my_blocker",
        fake_create_my_blocker,
    )
    application = create_test_application(MembershipRole.STUDENT)

    with TestClient(application) as client:
        response = client.post(
            CREATE_MY_BLOCKER_PATH,
            headers=organization_headers(),
            json={
                "topic_id": str(TOPIC_ID),
                "title": "Private subnet routing confusion",
                "description": (
                    "Learner cannot explain the NAT gateway route path."
                ),
                "category": "concept",
                "severity": "high",
            },
        )

    assert response.status_code == 201
    assert response.json()["status"] == "assigned"
    assert calls["create"] == (
        ORGANIZATION_ID,
        COURSE_ID,
        COHORT_ID,
        AUTHENTICATED_USER_ID,
    )


def test_non_student_cannot_use_learner_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        routes.repository,
        "list_my_blockers",
        unexpected_repository_call,
    )
    application = create_test_application(MembershipRole.TUTOR)

    with TestClient(application) as client:
        response = client.get(
            MY_BLOCKERS_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 403


def test_inactive_learner_cannot_create_blocker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        routes.membership_repository,
        "has_active_cohort_role",
        lambda *_args: False,
    )
    monkeypatch.setattr(
        routes.repository,
        "create_my_blocker",
        unexpected_repository_call,
    )
    application = create_test_application(MembershipRole.STUDENT)

    with TestClient(application) as client:
        response = client.post(
            CREATE_MY_BLOCKER_PATH,
            headers=organization_headers(),
            json={
                "title": "Need help",
                "description": "Cannot complete the networking exercise.",
                "category": "practice",
                "severity": "medium",
            },
        )

    assert response.status_code == 403


def test_assigned_tutor_can_list_cohort_blockers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_list_cohort_blockers(
        organization_id: UUID,
        course_id: UUID,
        cohort_id: UUID,
        *,
        status_filter: BlockerStatus | None,
        severity_filter: BlockerSeverity | None,
        limit: int,
        offset: int,
    ) -> tuple[list[BlockerResponse], int]:
        calls["list"] = (
            organization_id,
            course_id,
            cohort_id,
            status_filter,
            severity_filter,
            limit,
            offset,
        )
        return [BLOCKER_ITEM], 1

    permit_cohort_access(monkeypatch)
    monkeypatch.setattr(
        routes.repository,
        "list_cohort_blockers",
        fake_list_cohort_blockers,
    )
    application = create_test_application(MembershipRole.TUTOR)

    with TestClient(application) as client:
        response = client.get(
            f"{COHORT_BLOCKERS_PATH}?status=assigned",
            headers=organization_headers(),
        )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert calls["list"] == (
        ORGANIZATION_ID,
        COURSE_ID,
        COHORT_ID,
        BlockerStatus.ASSIGNED,
        None,
        20,
        0,
    )


def test_admin_can_list_without_cohort_assignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        routes.membership_repository,
        "has_active_cohort_role",
        unexpected_repository_call,
    )
    monkeypatch.setattr(
        routes.repository,
        "list_cohort_blockers",
        lambda *_args, **_kwargs: ([BLOCKER_ITEM], 1),
    )
    application = create_test_application(MembershipRole.ADMIN)

    with TestClient(application) as client:
        response = client.get(
            COHORT_BLOCKERS_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_student_cannot_read_staff_blocker_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        routes.repository,
        "list_cohort_blockers",
        unexpected_repository_call,
    )
    application = create_test_application(MembershipRole.STUDENT)

    with TestClient(application) as client:
        response = client.get(
            COHORT_BLOCKERS_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 403


def test_unassigned_tutor_cannot_read_cohort_blockers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        routes.membership_repository,
        "has_active_cohort_role",
        lambda *_args: False,
    )
    monkeypatch.setattr(
        routes.repository,
        "list_cohort_blockers",
        unexpected_repository_call,
    )
    application = create_test_application(MembershipRole.TUTOR)

    with TestClient(application) as client:
        response = client.get(
            COHORT_BLOCKERS_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 403


def test_cross_organization_access_is_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        routes.repository,
        "list_cohort_blockers",
        unexpected_repository_call,
    )
    application = create_test_application(MembershipRole.TUTOR)

    with TestClient(application) as client:
        response = client.get(
            COHORT_BLOCKERS_PATH,
            headers=organization_headers(OTHER_ORGANIZATION_ID),
        )

    assert response.status_code == 403


def test_missing_cohort_blocker_returns_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    permit_cohort_access(monkeypatch)
    monkeypatch.setattr(
        routes.repository,
        "get_cohort_blocker",
        lambda *_args: None,
    )
    application = create_test_application(MembershipRole.TUTOR)

    with TestClient(application) as client:
        response = client.get(
            BLOCKER_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 404


def test_assigned_tutor_can_update_blocker_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    updated_blocker = BLOCKER_DETAIL.model_copy(
        update={"status": BlockerStatus.WAITING_STUDENT}
    )
    calls: dict[str, object] = {}

    def fake_update(
        organization_id: UUID,
        course_id: UUID,
        cohort_id: UUID,
        blocker_id: UUID,
        actor_id: UUID,
        payload: object,
    ) -> BlockerDetailResponse:
        calls["update"] = (
            organization_id,
            course_id,
            cohort_id,
            blocker_id,
            actor_id,
        )
        calls["payload"] = payload
        return updated_blocker

    permit_cohort_access(monkeypatch)
    monkeypatch.setattr(
        routes.repository,
        "get_cohort_blocker",
        lambda *_args: BLOCKER_DETAIL,
    )
    monkeypatch.setattr(
        routes.repository,
        "update_cohort_blocker",
        fake_update,
    )
    application = create_test_application(MembershipRole.TUTOR)

    with TestClient(application) as client:
        response = client.put(
            BLOCKER_PATH,
            headers=organization_headers(),
            json={
                "status": "waiting_student",
                "comment": "Waiting for the learner to retry the lab.",
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "waiting_student"
    assert calls["update"] == (
        ORGANIZATION_ID,
        COURSE_ID,
        COHORT_ID,
        BLOCKER_ID,
        AUTHENTICATED_USER_ID,
    )


def test_admin_can_resolve_blocker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolved = BLOCKER_DETAIL.model_copy(
        update={
            "status": BlockerStatus.RESOLVED,
            "resolved_at": _TIMESTAMP,
            "resolution_summary": "Learner demonstrated the route path.",
        }
    )
    monkeypatch.setattr(
        routes.membership_repository,
        "has_active_cohort_role",
        unexpected_repository_call,
    )
    monkeypatch.setattr(
        routes.repository,
        "get_cohort_blocker",
        lambda *_args: BLOCKER_DETAIL,
    )
    monkeypatch.setattr(
        routes.repository,
        "update_cohort_blocker",
        lambda *_args: resolved,
    )
    application = create_test_application(MembershipRole.ADMIN)

    with TestClient(application) as client:
        response = client.put(
            BLOCKER_PATH,
            headers=organization_headers(),
            json={
                "status": "resolved",
                "resolution_summary": (
                    "Learner demonstrated the route path."
                ),
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "resolved"


def test_invalid_blocker_transition_returns_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    permit_cohort_access(monkeypatch)
    monkeypatch.setattr(
        routes.repository,
        "get_cohort_blocker",
        lambda *_args: BLOCKER_DETAIL,
    )
    monkeypatch.setattr(
        routes.repository,
        "update_cohort_blocker",
        unexpected_repository_call,
    )
    application = create_test_application(MembershipRole.TUTOR)

    with TestClient(application) as client:
        response = client.put(
            BLOCKER_PATH,
            headers=organization_headers(),
            json={
                "status": "closed",
                "resolution_summary": "Attempted direct closure.",
            },
        )

    assert response.status_code == 409
    assert "cannot move" in response.json()["detail"]


def test_assigned_status_requires_tutor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    open_blocker = BLOCKER_DETAIL.model_copy(
        update={
            "status": BlockerStatus.OPEN,
            "assigned_tutor_id": None,
            "assigned_tutor_email": None,
            "assigned_tutor_full_name": None,
        }
    )
    permit_cohort_access(monkeypatch)
    monkeypatch.setattr(
        routes.repository,
        "get_cohort_blocker",
        lambda *_args: open_blocker,
    )
    monkeypatch.setattr(
        routes.repository,
        "update_cohort_blocker",
        unexpected_repository_call,
    )
    application = create_test_application(MembershipRole.TUTOR)

    with TestClient(application) as client:
        response = client.put(
            BLOCKER_PATH,
            headers=organization_headers(),
            json={"status": "assigned"},
        )

    assert response.status_code == 422
    assert "require an assigned tutor" in response.json()["detail"]


def test_resolved_status_requires_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    permit_cohort_access(monkeypatch)
    monkeypatch.setattr(
        routes.repository,
        "get_cohort_blocker",
        lambda *_args: BLOCKER_DETAIL,
    )
    monkeypatch.setattr(
        routes.repository,
        "update_cohort_blocker",
        unexpected_repository_call,
    )
    application = create_test_application(MembershipRole.TUTOR)

    with TestClient(application) as client:
        response = client.put(
            BLOCKER_PATH,
            headers=organization_headers(),
            json={"status": "resolved"},
        )

    assert response.status_code == 422
    assert "require a resolution summary" in response.json()["detail"]


def test_ineligible_tutor_assignment_returns_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_role_check(
        _organization_id: UUID,
        _course_id: UUID,
        _cohort_id: UUID,
        user_id: UUID,
        _cohort_role: object,
    ) -> bool:
        return user_id == AUTHENTICATED_USER_ID

    monkeypatch.setattr(
        routes.membership_repository,
        "has_active_cohort_role",
        fake_role_check,
    )
    monkeypatch.setattr(
        routes.repository,
        "get_cohort_blocker",
        lambda *_args: BLOCKER_DETAIL,
    )
    monkeypatch.setattr(
        routes.repository,
        "update_cohort_blocker",
        unexpected_repository_call,
    )
    application = create_test_application(MembershipRole.TUTOR)

    with TestClient(application) as client:
        response = client.put(
            BLOCKER_PATH,
            headers=organization_headers(),
            json={"assigned_tutor_id": str(OTHER_TUTOR_ID)},
        )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Assigned tutor must be active in this cohort."
    )


def test_closed_blocker_accepts_comment_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed = BLOCKER_DETAIL.model_copy(
        update={
            "status": BlockerStatus.CLOSED,
            "resolved_at": _TIMESTAMP,
            "resolution_summary": "Support completed.",
        }
    )
    permit_cohort_access(monkeypatch)
    monkeypatch.setattr(
        routes.repository,
        "get_cohort_blocker",
        lambda *_args: closed,
    )
    monkeypatch.setattr(
        routes.repository,
        "update_cohort_blocker",
        lambda *_args: closed,
    )
    application = create_test_application(MembershipRole.TUTOR)

    with TestClient(application) as client:
        response = client.put(
            BLOCKER_PATH,
            headers=organization_headers(),
            json={"comment": "Final follow-up recorded."},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "closed"


def test_closed_blocker_rejects_material_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed = BLOCKER_DETAIL.model_copy(
        update={
            "status": BlockerStatus.CLOSED,
            "resolved_at": _TIMESTAMP,
            "resolution_summary": "Support completed.",
        }
    )
    permit_cohort_access(monkeypatch)
    monkeypatch.setattr(
        routes.repository,
        "get_cohort_blocker",
        lambda *_args: closed,
    )
    monkeypatch.setattr(
        routes.repository,
        "update_cohort_blocker",
        unexpected_repository_call,
    )
    application = create_test_application(MembershipRole.TUTOR)

    with TestClient(application) as client:
        response = client.put(
            BLOCKER_PATH,
            headers=organization_headers(),
            json={"severity": "critical"},
        )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Closed blockers can only receive comments."
    )


def test_active_tutor_can_create_intervention(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_create_intervention(
        organization_id: UUID,
        course_id: UUID,
        cohort_id: UUID,
        blocker_id: UUID,
        tutor_id: UUID,
        payload: object,
    ) -> TutorInterventionResponse:
        calls["create"] = (
            organization_id,
            course_id,
            cohort_id,
            blocker_id,
            tutor_id,
        )
        calls["payload"] = payload
        return PENDING_INTERVENTION

    permit_cohort_access(monkeypatch)
    monkeypatch.setattr(
        routes.repository,
        "get_cohort_blocker",
        lambda *_args: BLOCKER_DETAIL,
    )
    monkeypatch.setattr(
        routes.repository,
        "create_blocker_intervention",
        fake_create_intervention,
    )
    application = create_test_application(MembershipRole.TUTOR)

    with TestClient(application) as client:
        response = client.post(
            INTERVENTIONS_PATH,
            headers=organization_headers(),
            json={
                "intervention_type": "one_to_one_support",
                "action_taken": (
                    "Scheduled a VPC route-table walkthrough."
                ),
                "baseline_metric": "topic_score",
                "baseline_value": 40,
            },
        )

    assert response.status_code == 201
    assert response.json()["outcome"] == "pending"
    assert calls["create"] == (
        ORGANIZATION_ID,
        COURSE_ID,
        COHORT_ID,
        BLOCKER_ID,
        AUTHENTICATED_USER_ID,
    )


def test_admin_without_tutor_assignment_cannot_create_intervention(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        routes.membership_repository,
        "has_active_cohort_role",
        lambda *_args: False,
    )
    monkeypatch.setattr(
        routes.repository,
        "get_cohort_blocker",
        lambda *_args: BLOCKER_DETAIL,
    )
    monkeypatch.setattr(
        routes.repository,
        "create_blocker_intervention",
        unexpected_repository_call,
    )
    application = create_test_application(MembershipRole.ADMIN)

    with TestClient(application) as client:
        response = client.post(
            INTERVENTIONS_PATH,
            headers=organization_headers(),
            json={
                "intervention_type": "targeted_practice",
                "action_taken": "Provided a routing exercise.",
            },
        )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Only an active cohort tutor can create interventions."
    )


def test_resolved_blocker_rejects_new_intervention(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolved = BLOCKER_DETAIL.model_copy(
        update={
            "status": BlockerStatus.RESOLVED,
            "resolved_at": _TIMESTAMP,
            "resolution_summary": "Learner demonstrated the route path.",
        }
    )
    permit_cohort_access(monkeypatch)
    monkeypatch.setattr(
        routes.repository,
        "get_cohort_blocker",
        lambda *_args: resolved,
    )
    monkeypatch.setattr(
        routes.repository,
        "create_blocker_intervention",
        unexpected_repository_call,
    )
    application = create_test_application(MembershipRole.TUTOR)

    with TestClient(application) as client:
        response = client.post(
            INTERVENTIONS_PATH,
            headers=organization_headers(),
            json={
                "intervention_type": "targeted_practice",
                "action_taken": "Provided a routing exercise.",
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Interventions can only be created for active blockers."
    )


def test_tutor_can_complete_own_intervention(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_complete(
        organization_id: UUID,
        course_id: UUID,
        cohort_id: UUID,
        blocker_id: UUID,
        intervention_id: UUID,
        actor_id: UUID,
        payload: object,
    ) -> TutorInterventionResponse:
        calls["complete"] = (
            organization_id,
            course_id,
            cohort_id,
            blocker_id,
            intervention_id,
            actor_id,
        )
        calls["payload"] = payload
        return COMPLETED_INTERVENTION

    permit_cohort_access(monkeypatch)
    monkeypatch.setattr(
        routes.repository,
        "get_cohort_intervention",
        lambda *_args: PENDING_INTERVENTION,
    )
    monkeypatch.setattr(
        routes.repository,
        "complete_blocker_intervention",
        fake_complete,
    )
    application = create_test_application(MembershipRole.TUTOR)

    with TestClient(application) as client:
        response = client.put(
            INTERVENTION_PATH,
            headers=organization_headers(),
            json={
                "outcome": "improved",
                "follow_up_value": 85,
            },
        )

    assert response.status_code == 200
    assert response.json()["outcome"] == "improved"
    assert calls["complete"] == (
        ORGANIZATION_ID,
        COURSE_ID,
        COHORT_ID,
        BLOCKER_ID,
        INTERVENTION_ID,
        AUTHENTICATED_USER_ID,
    )


def test_tutor_cannot_complete_another_tutors_intervention(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    other_tutors_intervention = PENDING_INTERVENTION.model_copy(
        update={"tutor_id": OTHER_TUTOR_ID}
    )
    permit_cohort_access(monkeypatch)
    monkeypatch.setattr(
        routes.repository,
        "get_cohort_intervention",
        lambda *_args: other_tutors_intervention,
    )
    monkeypatch.setattr(
        routes.repository,
        "complete_blocker_intervention",
        unexpected_repository_call,
    )
    application = create_test_application(MembershipRole.TUTOR)

    with TestClient(application) as client:
        response = client.put(
            INTERVENTION_PATH,
            headers=organization_headers(),
            json={"outcome": "improved"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Tutors can complete only their own interventions."
    )


def test_admin_can_complete_tutors_intervention(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    other_tutors_intervention = PENDING_INTERVENTION.model_copy(
        update={"tutor_id": OTHER_TUTOR_ID}
    )
    completed = COMPLETED_INTERVENTION.model_copy(
        update={"tutor_id": OTHER_TUTOR_ID}
    )
    monkeypatch.setattr(
        routes.membership_repository,
        "has_active_cohort_role",
        unexpected_repository_call,
    )
    monkeypatch.setattr(
        routes.repository,
        "get_cohort_intervention",
        lambda *_args: other_tutors_intervention,
    )
    monkeypatch.setattr(
        routes.repository,
        "complete_blocker_intervention",
        lambda *_args: completed,
    )
    application = create_test_application(MembershipRole.ADMIN)

    with TestClient(application) as client:
        response = client.put(
            INTERVENTION_PATH,
            headers=organization_headers(),
            json={"outcome": "improved"},
        )

    assert response.status_code == 200
    assert response.json()["tutor_id"] == str(OTHER_TUTOR_ID)


def test_completed_intervention_returns_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    permit_cohort_access(monkeypatch)
    monkeypatch.setattr(
        routes.repository,
        "get_cohort_intervention",
        lambda *_args: COMPLETED_INTERVENTION,
    )
    monkeypatch.setattr(
        routes.repository,
        "complete_blocker_intervention",
        unexpected_repository_call,
    )
    application = create_test_application(MembershipRole.TUTOR)

    with TestClient(application) as client:
        response = client.put(
            INTERVENTION_PATH,
            headers=organization_headers(),
            json={"outcome": "no_change"},
        )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Tutor intervention is already completed."
    )


def test_missing_intervention_returns_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    permit_cohort_access(monkeypatch)
    monkeypatch.setattr(
        routes.repository,
        "get_cohort_intervention",
        lambda *_args: None,
    )
    application = create_test_application(MembershipRole.TUTOR)

    with TestClient(application) as client:
        response = client.put(
            INTERVENTION_PATH,
            headers=organization_headers(),
            json={"outcome": "improved"},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Tutor intervention was not found."
    )


def test_database_failure_returns_controlled_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_list(*_args: object, **_kwargs: object) -> None:
        raise SQLAlchemyError("sensitive database failure")

    monkeypatch.setattr(
        routes.repository,
        "list_my_blockers",
        fail_list,
    )
    application = create_test_application(MembershipRole.STUDENT)

    with TestClient(application) as client:
        response = client.get(
            MY_BLOCKERS_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Blocker-intervention service is unavailable."
    )
    assert "sensitive" not in response.text


def test_openapi_registers_seven_paths_and_eight_operations() -> None:
    application = create_test_application(MembershipRole.STUDENT)
    paths = application.openapi()["paths"]
    blocker_paths = {
        path: operations
        for path, operations in paths.items()
        if "blocker" in path
    }
    operation_count = sum(
        1
        for operations in blocker_paths.values()
        for method in operations
        if method in {"get", "post", "put", "patch", "delete"}
    )

    assert len(blocker_paths) == 7
    assert operation_count == 8
