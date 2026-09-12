from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from skillpulse.api.dependencies.auth import get_current_user
from skillpulse.api.routes import enrollments as enrollment_routes
from skillpulse.db.identity import (
    AuthenticatedUser,
    MembershipRole,
    OrganizationMembership,
)
from skillpulse.schemas.enrollment import (
    CohortMembershipCreate,
    CohortMembershipResponse,
    CohortMembershipStatus,
    CohortMembershipUpdate,
    CohortRole,
    MyCohortMembershipResponse,
)

ORGANIZATION_ID = UUID("10000000-0000-0000-0000-000000000001")
OTHER_ORGANIZATION_ID = UUID(
    "10000000-0000-0000-0000-000000000099"
)
AUTHENTICATED_USER_ID = UUID(
    "20000000-0000-0000-0000-000000000001"
)
TARGET_USER_ID = UUID("20000000-0000-0000-0000-000000000002")
COURSE_ID = UUID("40000000-0000-0000-0000-000000000001")
COHORT_ID = UUID("42000000-0000-0000-0000-000000000001")
MEMBERSHIP_ID = UUID("43000000-0000-0000-0000-000000000001")

ROSTER_PATH = (
    f"/api/v1/catalog/courses/{COURSE_ID}"
    f"/cohorts/{COHORT_ID}/members"
)
MEMBERSHIP_PATH = f"{ROSTER_PATH}/{MEMBERSHIP_ID}"
MY_MEMBERSHIPS_PATH = "/api/v1/catalog/my-cohort-memberships"

MEMBERSHIP = CohortMembershipResponse(
    id=MEMBERSHIP_ID,
    cohort_id=COHORT_ID,
    user_id=TARGET_USER_ID,
    email="learner@skillpulse.example",
    full_name="Example Learner",
    cohort_role=CohortRole.LEARNER,
    status=CohortMembershipStatus.ACTIVE,
    enrolled_at=datetime(2026, 9, 12, 9, 0, tzinfo=UTC),
    created_at=datetime(2026, 9, 12, 9, 0, tzinfo=UTC),
    updated_at=datetime(2026, 9, 12, 9, 0, tzinfo=UTC),
)

MY_MEMBERSHIP = MyCohortMembershipResponse(
    id=MEMBERSHIP_ID,
    course_id=COURSE_ID,
    course_title="AWS Foundations",
    cohort_id=COHORT_ID,
    cohort_name="September 2026 Cohort",
    cohort_role=CohortRole.LEARNER,
    status=CohortMembershipStatus.ACTIVE,
    start_date=date(2026, 9, 15),
    end_date=date(2026, 12, 15),
    enrolled_at=datetime(2026, 9, 12, 9, 0, tzinfo=UTC),
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
    """Create an isolated application with enrollment routes."""

    application = FastAPI()
    application.include_router(
        enrollment_routes.router,
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


def valid_membership_payload() -> dict[str, str]:
    """Return a valid cohort enrollment payload."""

    return {
        "user_id": str(TARGET_USER_ID),
        "cohort_role": "learner",
        "status": "active",
    }


@pytest.mark.parametrize(
    "role",
    [
        MembershipRole.STUDENT,
        MembershipRole.TUTOR,
        MembershipRole.ADMIN,
    ],
)
def test_all_roles_can_list_only_their_own_memberships(
    role: MembershipRole,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_list_my_memberships(
        organization_id: UUID,
        user_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[MyCohortMembershipResponse], int]:
        calls.update(
            {
                "organization_id": organization_id,
                "user_id": user_id,
                "limit": limit,
                "offset": offset,
            }
        )
        return [MY_MEMBERSHIP], 1

    monkeypatch.setattr(
        enrollment_routes.membership_repository,
        "list_my_cohort_memberships",
        fake_list_my_memberships,
    )

    application = create_test_application(role)
    with TestClient(application) as client:
        response = client.get(
            f"{MY_MEMBERSHIPS_PATH}?limit=10&offset=2",
            headers=organization_headers(),
        )

    assert response.status_code == 200
    assert response.json()["items"][0]["cohort_id"] == str(COHORT_ID)
    assert response.json()["items"][0]["course_title"] == (
        "AWS Foundations"
    )
    assert response.json()["total"] == 1
    assert calls == {
        "organization_id": ORGANIZATION_ID,
        "user_id": AUTHENTICATED_USER_ID,
        "limit": 10,
        "offset": 2,
    }


def test_cross_organization_self_membership_access_is_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_repository_call(
        *_args: object,
        **_kwargs: object,
    ) -> None:
        raise AssertionError("Repository must not be called.")

    monkeypatch.setattr(
        enrollment_routes.membership_repository,
        "list_my_cohort_memberships",
        unexpected_repository_call,
    )

    application = create_test_application(MembershipRole.STUDENT)
    with TestClient(application) as client:
        response = client.get(
            MY_MEMBERSHIPS_PATH,
            headers=organization_headers(OTHER_ORGANIZATION_ID),
        )

    assert response.status_code == 403


def test_student_cannot_read_cohort_roster(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_repository_call(
        *_args: object,
        **_kwargs: object,
    ) -> None:
        raise AssertionError("Repository must not be called.")

    monkeypatch.setattr(
        enrollment_routes.membership_repository,
        "list_cohort_memberships",
        unexpected_repository_call,
    )

    application = create_test_application(MembershipRole.STUDENT)
    with TestClient(application) as client:
        response = client.get(
            ROSTER_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Insufficient organization permissions."
    }


def test_unassigned_tutor_cannot_read_cohort_roster(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        enrollment_routes.membership_repository,
        "is_active_cohort_tutor",
        lambda *_args: False,
    )

    application = create_test_application(MembershipRole.TUTOR)
    with TestClient(application) as client:
        response = client.get(
            ROSTER_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Tutor is not assigned to this cohort."
    }


def test_assigned_tutor_can_read_cohort_roster(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_is_active_tutor(
        organization_id: UUID,
        course_id: UUID,
        cohort_id: UUID,
        user_id: UUID,
    ) -> bool:
        calls["tutor_check"] = (
            organization_id,
            course_id,
            cohort_id,
            user_id,
        )
        return True

    def fake_get_cohort(
        organization_id: UUID,
        course_id: UUID,
        cohort_id: UUID,
    ) -> object:
        calls["cohort_check"] = (
            organization_id,
            course_id,
            cohort_id,
        )
        return object()

    def fake_list_memberships(
        organization_id: UUID,
        course_id: UUID,
        cohort_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[CohortMembershipResponse], int]:
        calls["list"] = (
            organization_id,
            course_id,
            cohort_id,
            limit,
            offset,
        )
        return [MEMBERSHIP], 1

    monkeypatch.setattr(
        enrollment_routes.membership_repository,
        "is_active_cohort_tutor",
        fake_is_active_tutor,
    )
    monkeypatch.setattr(
        enrollment_routes.cohort_repository,
        "get_cohort",
        fake_get_cohort,
    )
    monkeypatch.setattr(
        enrollment_routes.membership_repository,
        "list_cohort_memberships",
        fake_list_memberships,
    )

    application = create_test_application(MembershipRole.TUTOR)
    with TestClient(application) as client:
        response = client.get(
            f"{ROSTER_PATH}?limit=25&offset=0",
            headers=organization_headers(),
        )

    assert response.status_code == 200
    assert response.json()["items"][0]["user_id"] == str(TARGET_USER_ID)
    assert response.json()["items"][0]["cohort_role"] == "learner"
    assert calls["tutor_check"] == (
        ORGANIZATION_ID,
        COURSE_ID,
        COHORT_ID,
        AUTHENTICATED_USER_ID,
    )
    assert calls["cohort_check"] == (
        ORGANIZATION_ID,
        COURSE_ID,
        COHORT_ID,
    )
    assert calls["list"] == (
        ORGANIZATION_ID,
        COURSE_ID,
        COHORT_ID,
        25,
        0,
    )


def test_admin_can_read_roster_without_tutor_assignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_assignment_check(
        *_args: object,
        **_kwargs: object,
    ) -> None:
        raise AssertionError("Admin must bypass tutor assignment check.")

    monkeypatch.setattr(
        enrollment_routes.membership_repository,
        "is_active_cohort_tutor",
        unexpected_assignment_check,
    )
    monkeypatch.setattr(
        enrollment_routes.cohort_repository,
        "get_cohort",
        lambda *_args: object(),
    )
    monkeypatch.setattr(
        enrollment_routes.membership_repository,
        "list_cohort_memberships",
        lambda *_args, **_kwargs: ([MEMBERSHIP], 1),
    )

    application = create_test_application(MembershipRole.ADMIN)
    with TestClient(application) as client:
        response = client.get(
            ROSTER_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_missing_membership_returns_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        enrollment_routes.membership_repository,
        "get_cohort_membership",
        lambda *_args: None,
    )

    application = create_test_application(MembershipRole.ADMIN)
    with TestClient(application) as client:
        response = client.get(
            MEMBERSHIP_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Cohort membership was not found."
    }


@pytest.mark.parametrize(
    "role",
    [
        MembershipRole.STUDENT,
        MembershipRole.TUTOR,
    ],
)
def test_non_admin_cannot_create_membership(
    role: MembershipRole,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_repository_call(
        *_args: object,
        **_kwargs: object,
    ) -> None:
        raise AssertionError("Repository must not be called.")

    monkeypatch.setattr(
        enrollment_routes.membership_repository,
        "create_cohort_membership",
        unexpected_repository_call,
    )

    application = create_test_application(role)
    with TestClient(application) as client:
        response = client.post(
            ROSTER_PATH,
            headers=organization_headers(),
            json=valid_membership_payload(),
        )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Insufficient organization permissions."
    }


def test_admin_can_create_membership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_create_membership(
        organization_id: UUID,
        course_id: UUID,
        cohort_id: UUID,
        payload: CohortMembershipCreate,
    ) -> CohortMembershipResponse:
        calls.update(
            {
                "organization_id": organization_id,
                "course_id": course_id,
                "cohort_id": cohort_id,
                "payload": payload,
            }
        )
        return MEMBERSHIP

    monkeypatch.setattr(
        enrollment_routes.membership_repository,
        "create_cohort_membership",
        fake_create_membership,
    )

    application = create_test_application(MembershipRole.ADMIN)
    with TestClient(application) as client:
        response = client.post(
            ROSTER_PATH,
            headers=organization_headers(),
            json=valid_membership_payload(),
        )

    assert response.status_code == 201
    assert response.json()["id"] == str(MEMBERSHIP_ID)
    assert calls["organization_id"] == ORGANIZATION_ID
    assert calls["course_id"] == COURSE_ID
    assert calls["cohort_id"] == COHORT_ID

    payload = calls["payload"]
    assert isinstance(payload, CohortMembershipCreate)
    assert payload.user_id == TARGET_USER_ID
    assert payload.cohort_role is CohortRole.LEARNER
    assert payload.status is CohortMembershipStatus.ACTIVE


def test_duplicate_membership_returns_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def duplicate_membership(
        *_args: object,
        **_kwargs: object,
    ) -> CohortMembershipResponse:
        raise IntegrityError(
            "INSERT INTO cohort_memberships",
            {},
            RuntimeError("duplicate"),
        )

    monkeypatch.setattr(
        enrollment_routes.membership_repository,
        "create_cohort_membership",
        duplicate_membership,
    )

    application = create_test_application(MembershipRole.ADMIN)
    with TestClient(application) as client:
        response = client.post(
            ROSTER_PATH,
            headers=organization_headers(),
            json=valid_membership_payload(),
        )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "User is already enrolled in this cohort."
    }


def test_ineligible_target_user_returns_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        enrollment_routes.membership_repository,
        "create_cohort_membership",
        lambda *_args: None,
    )

    application = create_test_application(MembershipRole.ADMIN)
    with TestClient(application) as client:
        response = client.post(
            ROSTER_PATH,
            headers=organization_headers(),
            json=valid_membership_payload(),
        )

    assert response.status_code == 404
    assert response.json() == {
        "detail": (
            "Cohort or eligible organisation member was not found."
        )
    }


def test_admin_can_update_membership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}
    inactive_membership = MEMBERSHIP.model_copy(
        update={
            "status": CohortMembershipStatus.INACTIVE,
            "updated_at": datetime(
                2026,
                9,
                12,
                10,
                0,
                tzinfo=UTC,
            ),
        }
    )

    def fake_update_membership(
        organization_id: UUID,
        course_id: UUID,
        cohort_id: UUID,
        membership_id: UUID,
        payload: CohortMembershipUpdate,
    ) -> CohortMembershipResponse:
        calls.update(
            {
                "organization_id": organization_id,
                "course_id": course_id,
                "cohort_id": cohort_id,
                "membership_id": membership_id,
                "payload": payload,
            }
        )
        return inactive_membership

    monkeypatch.setattr(
        enrollment_routes.membership_repository,
        "update_cohort_membership",
        fake_update_membership,
    )

    application = create_test_application(MembershipRole.ADMIN)
    with TestClient(application) as client:
        response = client.put(
            MEMBERSHIP_PATH,
            headers=organization_headers(),
            json={
                "cohort_role": "learner",
                "status": "inactive",
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "inactive"
    assert calls["membership_id"] == MEMBERSHIP_ID

    payload = calls["payload"]
    assert isinstance(payload, CohortMembershipUpdate)
    assert payload.cohort_role is CohortRole.LEARNER
    assert payload.status is CohortMembershipStatus.INACTIVE


@pytest.mark.parametrize(
    "role",
    [
        MembershipRole.STUDENT,
        MembershipRole.TUTOR,
    ],
)
def test_non_admin_cannot_update_membership(
    role: MembershipRole,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_repository_call(
        *_args: object,
        **_kwargs: object,
    ) -> None:
        raise AssertionError("Repository must not be called.")

    monkeypatch.setattr(
        enrollment_routes.membership_repository,
        "update_cohort_membership",
        unexpected_repository_call,
    )

    application = create_test_application(role)
    with TestClient(application) as client:
        response = client.put(
            MEMBERSHIP_PATH,
            headers=organization_headers(),
            json={
                "cohort_role": "learner",
                "status": "inactive",
            },
        )

    assert response.status_code == 403


def test_missing_or_ineligible_update_returns_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        enrollment_routes.membership_repository,
        "update_cohort_membership",
        lambda *_args: None,
    )

    application = create_test_application(MembershipRole.ADMIN)
    with TestClient(application) as client:
        response = client.put(
            MEMBERSHIP_PATH,
            headers=organization_headers(),
            json={
                "cohort_role": "tutor",
                "status": "active",
            },
        )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Cohort membership was not found."
    }


def test_invalid_cohort_role_returns_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_repository_call(
        *_args: object,
        **_kwargs: object,
    ) -> None:
        raise AssertionError("Repository must not be called.")

    monkeypatch.setattr(
        enrollment_routes.membership_repository,
        "create_cohort_membership",
        unexpected_repository_call,
    )

    payload = valid_membership_payload()
    payload["cohort_role"] = "student"

    application = create_test_application(MembershipRole.ADMIN)
    with TestClient(application) as client:
        response = client.post(
            ROSTER_PATH,
            headers=organization_headers(),
            json=payload,
        )

    assert response.status_code == 422


def test_missing_cohort_returns_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        enrollment_routes.cohort_repository,
        "get_cohort",
        lambda *_args: None,
    )

    application = create_test_application(MembershipRole.ADMIN)
    with TestClient(application) as client:
        response = client.get(
            ROSTER_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Cohort was not found."
    }


def test_enrollment_database_failure_returns_service_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable_memberships(
        *_args: object,
        **_kwargs: object,
    ) -> tuple[list[MyCohortMembershipResponse], int]:
        raise SQLAlchemyError("database unavailable")

    monkeypatch.setattr(
        enrollment_routes.membership_repository,
        "list_my_cohort_memberships",
        unavailable_memberships,
    )

    application = create_test_application(MembershipRole.STUDENT)
    with TestClient(application) as client:
        response = client.get(
            MY_MEMBERSHIPS_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Cohort enrollment service is unavailable."
    }


def test_tutor_assignment_failure_returns_service_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable_assignment_check(
        *_args: object,
        **_kwargs: object,
    ) -> bool:
        raise SQLAlchemyError("database unavailable")

    monkeypatch.setattr(
        enrollment_routes.membership_repository,
        "is_active_cohort_tutor",
        unavailable_assignment_check,
    )

    application = create_test_application(MembershipRole.TUTOR)
    with TestClient(application) as client:
        response = client.get(
            ROSTER_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Cohort enrollment service is unavailable."
    }


def test_openapi_exposes_five_enrollment_operations() -> None:
    application = create_test_application(MembershipRole.ADMIN)
    paths = application.openapi()["paths"]

    roster_schema_path = (
        "/api/v1/catalog/courses/{course_id}"
        "/cohorts/{cohort_id}/members"
    )
    membership_schema_path = (
        f"{roster_schema_path}/{{membership_id}}"
    )

    assert set(paths[MY_MEMBERSHIPS_PATH]) == {"get"}
    assert set(paths[roster_schema_path]) == {"get", "post"}
    assert set(paths[membership_schema_path]) == {"get", "put"}
