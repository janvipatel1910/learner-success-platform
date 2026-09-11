from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from skillpulse.api.dependencies.auth import get_current_user
from skillpulse.api.routes import catalog as catalog_routes
from skillpulse.db.identity import (
    AuthenticatedUser,
    MembershipRole,
    OrganizationMembership,
)
from skillpulse.schemas.catalog import (
    CohortCreate,
    CohortResponse,
    CohortStatus,
    CohortUpdate,
    CourseResponse,
    CourseStatus,
    DeliveryMode,
)

ORGANIZATION_ID = UUID("10000000-0000-0000-0000-000000000001")
OTHER_ORGANIZATION_ID = UUID(
    "10000000-0000-0000-0000-000000000099"
)
COURSE_ID = UUID("40000000-0000-0000-0000-000000000001")
COHORT_ID = UUID("42000000-0000-0000-0000-000000000001")

COURSE = CourseResponse(
    id=COURSE_ID,
    organization_id=ORGANIZATION_ID,
    title="AWS Foundations",
    code="AWS-FOUND",
    description="AWS and cloud foundations.",
    certification_name="AWS Certified Cloud Practitioner",
    status=CourseStatus.ACTIVE,
    created_at=datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
    updated_at=datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
)

COHORT = CohortResponse(
    id=COHORT_ID,
    course_id=COURSE_ID,
    name="September 2026 Cohort",
    start_date=date(2026, 9, 15),
    end_date=date(2026, 12, 15),
    delivery_mode=DeliveryMode.HYBRID,
    status=CohortStatus.ACTIVE,
    created_at=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
    updated_at=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
)


def build_user(role: MembershipRole) -> AuthenticatedUser:
    """Create a user with one controlled organisation role."""

    return AuthenticatedUser(
        user_id=UUID("20000000-0000-0000-0000-000000000001"),
        email="cohort.user@skillpulse.example",
        full_name="Cohort User",
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
    """Create an isolated application with catalog routes."""

    application = FastAPI()
    application.include_router(
        catalog_routes.router,
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


def valid_cohort_payload() -> dict[str, str]:
    """Return a valid complete cohort payload."""

    return {
        "name": "September 2026 Cohort",
        "start_date": "2026-09-15",
        "end_date": "2026-12-15",
        "delivery_mode": "hybrid",
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
def test_all_organization_roles_can_list_cohorts(
    role: MembershipRole,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_get_course(
        organization_id: UUID,
        course_id: UUID,
    ) -> CourseResponse:
        assert organization_id == ORGANIZATION_ID
        assert course_id == COURSE_ID
        return COURSE

    def fake_list_cohorts(
        organization_id: UUID,
        course_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[CohortResponse], int]:
        calls.update(
            {
                "organization_id": organization_id,
                "course_id": course_id,
                "limit": limit,
                "offset": offset,
            }
        )
        return [COHORT], 1

    monkeypatch.setattr(
        catalog_routes.course_repository,
        "get_course",
        fake_get_course,
    )
    monkeypatch.setattr(
        catalog_routes.cohort_repository,
        "list_cohorts",
        fake_list_cohorts,
    )

    application = create_test_application(role)

    with TestClient(application) as client:
        response = client.get(
            (
                f"/api/v1/catalog/courses/{COURSE_ID}/cohorts"
                "?limit=10&offset=5"
            ),
            headers=organization_headers(),
        )

    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == str(COHORT_ID)
    assert response.json()["items"][0]["delivery_mode"] == "hybrid"
    assert response.json()["total"] == 1
    assert calls == {
        "organization_id": ORGANIZATION_ID,
        "course_id": COURSE_ID,
        "limit": 10,
        "offset": 5,
    }


@pytest.mark.parametrize(
    "role",
    [
        MembershipRole.STUDENT,
        MembershipRole.TUTOR,
    ],
)
def test_non_admin_cannot_create_cohort(
    role: MembershipRole,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_repository_call(
        *_args: object,
        **_kwargs: object,
    ) -> None:
        raise AssertionError("Repository must not be called.")

    monkeypatch.setattr(
        catalog_routes.cohort_repository,
        "create_cohort",
        unexpected_repository_call,
    )

    application = create_test_application(role)

    with TestClient(application) as client:
        response = client.post(
            f"/api/v1/catalog/courses/{COURSE_ID}/cohorts",
            headers=organization_headers(),
            json=valid_cohort_payload(),
        )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Insufficient organization permissions."
    }


def test_admin_can_create_cohort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_create_cohort(
        organization_id: UUID,
        course_id: UUID,
        payload: CohortCreate,
    ) -> CohortResponse:
        calls["organization_id"] = organization_id
        calls["course_id"] = course_id
        calls["payload"] = payload
        return COHORT

    monkeypatch.setattr(
        catalog_routes.cohort_repository,
        "create_cohort",
        fake_create_cohort,
    )

    application = create_test_application(MembershipRole.ADMIN)

    with TestClient(application) as client:
        response = client.post(
            f"/api/v1/catalog/courses/{COURSE_ID}/cohorts",
            headers=organization_headers(),
            json=valid_cohort_payload(),
        )

    assert response.status_code == 201
    assert response.json()["id"] == str(COHORT_ID)
    assert calls["organization_id"] == ORGANIZATION_ID
    assert calls["course_id"] == COURSE_ID

    payload = calls["payload"]
    assert isinstance(payload, CohortCreate)
    assert payload.delivery_mode is DeliveryMode.HYBRID
    assert payload.status is CohortStatus.ACTIVE


def test_admin_can_update_cohort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_update_cohort(
        organization_id: UUID,
        course_id: UUID,
        cohort_id: UUID,
        payload: CohortUpdate,
    ) -> CohortResponse:
        calls["organization_id"] = organization_id
        calls["course_id"] = course_id
        calls["cohort_id"] = cohort_id
        calls["payload"] = payload
        return COHORT.model_copy(
            update={
                **payload.model_dump(),
                "updated_at": datetime(
                    2026,
                    9,
                    2,
                    10,
                    0,
                    tzinfo=UTC,
                ),
            }
        )

    monkeypatch.setattr(
        catalog_routes.cohort_repository,
        "update_cohort",
        fake_update_cohort,
    )

    application = create_test_application(MembershipRole.ADMIN)
    update_payload = valid_cohort_payload()
    update_payload["name"] = "Completed September Cohort"
    update_payload["delivery_mode"] = "online"
    update_payload["status"] = "completed"

    with TestClient(application) as client:
        response = client.put(
            (
                f"/api/v1/catalog/courses/{COURSE_ID}"
                f"/cohorts/{COHORT_ID}"
            ),
            headers=organization_headers(),
            json=update_payload,
        )

    assert response.status_code == 200
    assert response.json()["name"] == "Completed September Cohort"
    assert response.json()["delivery_mode"] == "online"
    assert response.json()["status"] == "completed"
    assert calls["organization_id"] == ORGANIZATION_ID
    assert calls["course_id"] == COURSE_ID
    assert calls["cohort_id"] == COHORT_ID

    payload = calls["payload"]
    assert isinstance(payload, CohortUpdate)
    assert payload.status is CohortStatus.COMPLETED


def test_unknown_parent_course_returns_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        catalog_routes.course_repository,
        "get_course",
        lambda *_args, **_kwargs: None,
    )

    application = create_test_application(MembershipRole.STUDENT)

    with TestClient(application) as client:
        response = client.get(
            f"/api/v1/catalog/courses/{COURSE_ID}/cohorts",
            headers=organization_headers(),
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Course was not found."}


def test_unknown_cohort_returns_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        catalog_routes.cohort_repository,
        "get_cohort",
        lambda *_args, **_kwargs: None,
    )

    application = create_test_application(MembershipRole.TUTOR)

    with TestClient(application) as client:
        response = client.get(
            (
                f"/api/v1/catalog/courses/{COURSE_ID}"
                f"/cohorts/{COHORT_ID}"
            ),
            headers=organization_headers(),
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Cohort was not found."}


def test_duplicate_cohort_returns_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def duplicate_cohort(
        *_args: object,
        **_kwargs: object,
    ) -> CohortResponse:
        raise IntegrityError(
            "INSERT INTO cohorts",
            {},
            RuntimeError("duplicate"),
        )

    monkeypatch.setattr(
        catalog_routes.cohort_repository,
        "create_cohort",
        duplicate_cohort,
    )

    application = create_test_application(MembershipRole.ADMIN)

    with TestClient(application) as client:
        response = client.post(
            f"/api/v1/catalog/courses/{COURSE_ID}/cohorts",
            headers=organization_headers(),
            json=valid_cohort_payload(),
        )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Cohort conflicts with an existing record."
    }


def test_cohort_database_failure_returns_service_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable_cohort(
        *_args: object,
        **_kwargs: object,
    ) -> CohortResponse:
        raise SQLAlchemyError("database unavailable")

    monkeypatch.setattr(
        catalog_routes.cohort_repository,
        "get_cohort",
        unavailable_cohort,
    )

    application = create_test_application(MembershipRole.ADMIN)

    with TestClient(application) as client:
        response = client.get(
            (
                f"/api/v1/catalog/courses/{COURSE_ID}"
                f"/cohorts/{COHORT_ID}"
            ),
            headers=organization_headers(),
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Catalog service is unavailable."
    }


def test_cross_organization_cohort_access_is_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_repository_call(
        *_args: object,
        **_kwargs: object,
    ) -> None:
        raise AssertionError("Repository must not be called.")

    monkeypatch.setattr(
        catalog_routes.cohort_repository,
        "get_cohort",
        unexpected_repository_call,
    )

    application = create_test_application(MembershipRole.ADMIN)

    with TestClient(application) as client:
        response = client.get(
            (
                f"/api/v1/catalog/courses/{COURSE_ID}"
                f"/cohorts/{COHORT_ID}"
            ),
            headers=organization_headers(OTHER_ORGANIZATION_ID),
        )

    assert response.status_code == 403


def test_invalid_cohort_date_range_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_repository_call(
        *_args: object,
        **_kwargs: object,
    ) -> None:
        raise AssertionError("Repository must not be called.")

    monkeypatch.setattr(
        catalog_routes.cohort_repository,
        "create_cohort",
        unexpected_repository_call,
    )

    payload = valid_cohort_payload()
    payload["end_date"] = "2026-09-01"

    application = create_test_application(MembershipRole.ADMIN)

    with TestClient(application) as client:
        response = client.post(
            f"/api/v1/catalog/courses/{COURSE_ID}/cohorts",
            headers=organization_headers(),
            json=payload,
        )

    assert response.status_code == 422
