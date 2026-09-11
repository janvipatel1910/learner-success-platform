from datetime import UTC, datetime
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
    CourseCreate,
    CourseResponse,
    CourseStatus,
    CourseUpdate,
)

ORGANIZATION_ID = UUID("10000000-0000-0000-0000-000000000001")
OTHER_ORGANIZATION_ID = UUID(
    "10000000-0000-0000-0000-000000000099"
)
COURSE_ID = UUID("40000000-0000-0000-0000-000000000001")

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


def build_user(role: MembershipRole) -> AuthenticatedUser:
    """Create a user with one controlled organisation role."""

    return AuthenticatedUser(
        user_id=UUID("20000000-0000-0000-0000-000000000001"),
        email="catalog.user@skillpulse.example",
        full_name="Catalog User",
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


def valid_course_payload() -> dict[str, str]:
    """Return a valid complete course payload."""

    return {
        "title": "AWS Foundations",
        "code": "AWS-FOUND",
        "description": "AWS and cloud foundations.",
        "certification_name": "AWS Certified Cloud Practitioner",
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
def test_all_organization_roles_can_list_courses(
    role: MembershipRole,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_list_courses(
        organization_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[CourseResponse], int]:
        calls.update(
            {
                "organization_id": organization_id,
                "limit": limit,
                "offset": offset,
            }
        )
        return [COURSE], 1

    monkeypatch.setattr(
        catalog_routes.course_repository,
        "list_courses",
        fake_list_courses,
    )

    application = create_test_application(role)

    with TestClient(application) as client:
        response = client.get(
            "/api/v1/catalog/courses?limit=10&offset=5",
            headers=organization_headers(),
        )

    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == str(COURSE_ID)
    assert response.json()["items"][0]["status"] == "active"
    assert response.json()["total"] == 1
    assert response.json()["limit"] == 10
    assert response.json()["offset"] == 5
    assert calls == {
        "organization_id": ORGANIZATION_ID,
        "limit": 10,
        "offset": 5,
    }


def test_user_cannot_list_another_organizations_courses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_repository_call(
        *_args: object,
        **_kwargs: object,
    ) -> None:
        raise AssertionError("Repository must not be called.")

    monkeypatch.setattr(
        catalog_routes.course_repository,
        "list_courses",
        unexpected_repository_call,
    )

    application = create_test_application(MembershipRole.ADMIN)

    with TestClient(application) as client:
        response = client.get(
            "/api/v1/catalog/courses",
            headers=organization_headers(OTHER_ORGANIZATION_ID),
        )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Insufficient organization permissions."
    }


def test_student_cannot_create_course(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_repository_call(
        *_args: object,
        **_kwargs: object,
    ) -> None:
        raise AssertionError("Repository must not be called.")

    monkeypatch.setattr(
        catalog_routes.course_repository,
        "create_course",
        unexpected_repository_call,
    )

    application = create_test_application(MembershipRole.STUDENT)

    with TestClient(application) as client:
        response = client.post(
            "/api/v1/catalog/courses",
            headers=organization_headers(),
            json=valid_course_payload(),
        )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Insufficient organization permissions."
    }


def test_admin_can_create_course(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_create_course(
        organization_id: UUID,
        payload: CourseCreate,
    ) -> CourseResponse:
        calls["organization_id"] = organization_id
        calls["payload"] = payload
        return COURSE

    monkeypatch.setattr(
        catalog_routes.course_repository,
        "create_course",
        fake_create_course,
    )

    application = create_test_application(MembershipRole.ADMIN)

    with TestClient(application) as client:
        response = client.post(
            "/api/v1/catalog/courses",
            headers=organization_headers(),
            json=valid_course_payload(),
        )

    assert response.status_code == 201
    assert response.json()["id"] == str(COURSE_ID)
    assert calls["organization_id"] == ORGANIZATION_ID

    payload = calls["payload"]
    assert isinstance(payload, CourseCreate)
    assert payload.code == "AWS-FOUND"
    assert payload.status is CourseStatus.ACTIVE


def test_unknown_course_returns_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_get_course(
        organization_id: UUID,
        course_id: UUID,
    ) -> None:
        assert organization_id == ORGANIZATION_ID
        assert course_id == COURSE_ID
        return None

    monkeypatch.setattr(
        catalog_routes.course_repository,
        "get_course",
        fake_get_course,
    )

    application = create_test_application(MembershipRole.TUTOR)

    with TestClient(application) as client:
        response = client.get(
            f"/api/v1/catalog/courses/{COURSE_ID}",
            headers=organization_headers(),
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Course was not found."}


def test_admin_can_update_course(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_update_course(
        organization_id: UUID,
        course_id: UUID,
        payload: CourseUpdate,
    ) -> CourseResponse:
        calls["organization_id"] = organization_id
        calls["course_id"] = course_id
        calls["payload"] = payload
        return COURSE.model_copy(
            update={
                **payload.model_dump(),
                "updated_at": datetime(
                    2026,
                    9,
                    2,
                    9,
                    0,
                    tzinfo=UTC,
                ),
            }
        )

    monkeypatch.setattr(
        catalog_routes.course_repository,
        "update_course",
        fake_update_course,
    )

    application = create_test_application(MembershipRole.ADMIN)
    update_payload = valid_course_payload()
    update_payload["title"] = "Updated AWS Foundations"
    update_payload["status"] = "archived"

    with TestClient(application) as client:
        response = client.put(
            f"/api/v1/catalog/courses/{COURSE_ID}",
            headers=organization_headers(),
            json=update_payload,
        )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated AWS Foundations"
    assert response.json()["status"] == "archived"
    assert calls["organization_id"] == ORGANIZATION_ID
    assert calls["course_id"] == COURSE_ID

    payload = calls["payload"]
    assert isinstance(payload, CourseUpdate)
    assert payload.status is CourseStatus.ARCHIVED


def test_duplicate_course_returns_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def duplicate_course(
        *_args: object,
        **_kwargs: object,
    ) -> CourseResponse:
        raise IntegrityError(
            "INSERT INTO courses",
            {},
            RuntimeError("duplicate"),
        )

    monkeypatch.setattr(
        catalog_routes.course_repository,
        "create_course",
        duplicate_course,
    )

    application = create_test_application(MembershipRole.ADMIN)

    with TestClient(application) as client:
        response = client.post(
            "/api/v1/catalog/courses",
            headers=organization_headers(),
            json=valid_course_payload(),
        )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Course conflicts with an existing record."
    }


def test_database_failure_returns_service_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable_courses(
        *_args: object,
        **_kwargs: object,
    ) -> tuple[list[CourseResponse], int]:
        raise SQLAlchemyError("database unavailable")

    monkeypatch.setattr(
        catalog_routes.course_repository,
        "list_courses",
        unavailable_courses,
    )

    application = create_test_application(MembershipRole.ADMIN)

    with TestClient(application) as client:
        response = client.get(
            "/api/v1/catalog/courses",
            headers=organization_headers(),
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Catalog service is unavailable."
    }


def test_invalid_pagination_is_rejected() -> None:
    application = create_test_application(MembershipRole.STUDENT)

    with TestClient(application) as client:
        response = client.get(
            "/api/v1/catalog/courses?limit=0&offset=-1",
            headers=organization_headers(),
        )

    assert response.status_code == 422
