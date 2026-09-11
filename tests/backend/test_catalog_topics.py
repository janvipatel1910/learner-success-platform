from datetime import UTC, datetime
from decimal import Decimal
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
    CourseResponse,
    CourseStatus,
    TopicCreate,
    TopicResponse,
    TopicUpdate,
)

ORGANIZATION_ID = UUID("10000000-0000-0000-0000-000000000001")
OTHER_ORGANIZATION_ID = UUID(
    "10000000-0000-0000-0000-000000000099"
)
COURSE_ID = UUID("40000000-0000-0000-0000-000000000001")
TOPIC_ID = UUID("41000000-0000-0000-0000-000000000001")

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

TOPIC = TopicResponse(
    id=TOPIC_ID,
    course_id=COURSE_ID,
    title="Cloud Concepts",
    sequence_number=1,
    exam_domain="Cloud Concepts",
    expected_hours=Decimal("6.50"),
    created_at=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
    updated_at=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
)


def build_user(role: MembershipRole) -> AuthenticatedUser:
    """Create a user with one controlled organisation role."""

    return AuthenticatedUser(
        user_id=UUID("20000000-0000-0000-0000-000000000001"),
        email="topic.user@skillpulse.example",
        full_name="Topic User",
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


def valid_topic_payload() -> dict[str, str | int | float]:
    """Return a valid complete topic payload."""

    return {
        "title": "Cloud Concepts",
        "sequence_number": 1,
        "exam_domain": "Cloud Concepts",
        "expected_hours": 6.5,
    }


@pytest.mark.parametrize(
    "role",
    [
        MembershipRole.STUDENT,
        MembershipRole.TUTOR,
        MembershipRole.ADMIN,
    ],
)
def test_all_organization_roles_can_list_topics(
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

    def fake_list_topics(
        organization_id: UUID,
        course_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[TopicResponse], int]:
        calls.update(
            {
                "organization_id": organization_id,
                "course_id": course_id,
                "limit": limit,
                "offset": offset,
            }
        )
        return [TOPIC], 1

    monkeypatch.setattr(
        catalog_routes.course_repository,
        "get_course",
        fake_get_course,
    )
    monkeypatch.setattr(
        catalog_routes.topic_repository,
        "list_topics",
        fake_list_topics,
    )

    application = create_test_application(role)

    with TestClient(application) as client:
        response = client.get(
            (
                f"/api/v1/catalog/courses/{COURSE_ID}/topics"
                "?limit=10&offset=5"
            ),
            headers=organization_headers(),
        )

    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == str(TOPIC_ID)
    assert response.json()["items"][0]["sequence_number"] == 1
    assert response.json()["total"] == 1
    assert response.json()["limit"] == 10
    assert response.json()["offset"] == 5
    assert calls == {
        "organization_id": ORGANIZATION_ID,
        "course_id": COURSE_ID,
        "limit": 10,
        "offset": 5,
    }


def test_unknown_parent_course_returns_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_get_course(
        organization_id: UUID,
        course_id: UUID,
    ) -> None:
        assert organization_id == ORGANIZATION_ID
        assert course_id == COURSE_ID
        return None

    def unexpected_topic_query(
        *_args: object,
        **_kwargs: object,
    ) -> None:
        raise AssertionError("Topic repository must not be called.")

    monkeypatch.setattr(
        catalog_routes.course_repository,
        "get_course",
        fake_get_course,
    )
    monkeypatch.setattr(
        catalog_routes.topic_repository,
        "list_topics",
        unexpected_topic_query,
    )

    application = create_test_application(MembershipRole.STUDENT)

    with TestClient(application) as client:
        response = client.get(
            f"/api/v1/catalog/courses/{COURSE_ID}/topics",
            headers=organization_headers(),
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Course was not found."}


@pytest.mark.parametrize(
    "role",
    [
        MembershipRole.STUDENT,
        MembershipRole.TUTOR,
    ],
)
def test_non_admin_cannot_create_topic(
    role: MembershipRole,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_repository_call(
        *_args: object,
        **_kwargs: object,
    ) -> None:
        raise AssertionError("Repository must not be called.")

    monkeypatch.setattr(
        catalog_routes.topic_repository,
        "create_topic",
        unexpected_repository_call,
    )

    application = create_test_application(role)

    with TestClient(application) as client:
        response = client.post(
            f"/api/v1/catalog/courses/{COURSE_ID}/topics",
            headers=organization_headers(),
            json=valid_topic_payload(),
        )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Insufficient organization permissions."
    }


def test_admin_can_create_topic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_create_topic(
        organization_id: UUID,
        course_id: UUID,
        payload: TopicCreate,
    ) -> TopicResponse:
        calls["organization_id"] = organization_id
        calls["course_id"] = course_id
        calls["payload"] = payload
        return TOPIC

    monkeypatch.setattr(
        catalog_routes.topic_repository,
        "create_topic",
        fake_create_topic,
    )

    application = create_test_application(MembershipRole.ADMIN)

    with TestClient(application) as client:
        response = client.post(
            f"/api/v1/catalog/courses/{COURSE_ID}/topics",
            headers=organization_headers(),
            json=valid_topic_payload(),
        )

    assert response.status_code == 201
    assert response.json()["id"] == str(TOPIC_ID)
    assert calls["organization_id"] == ORGANIZATION_ID
    assert calls["course_id"] == COURSE_ID

    payload = calls["payload"]
    assert isinstance(payload, TopicCreate)
    assert payload.sequence_number == 1
    assert payload.expected_hours == Decimal("6.50")


def test_create_topic_for_unknown_course_returns_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_create_topic(
        organization_id: UUID,
        course_id: UUID,
        payload: TopicCreate,
    ) -> None:
        assert organization_id == ORGANIZATION_ID
        assert course_id == COURSE_ID
        assert payload.title == "Cloud Concepts"
        return None

    monkeypatch.setattr(
        catalog_routes.topic_repository,
        "create_topic",
        fake_create_topic,
    )

    application = create_test_application(MembershipRole.ADMIN)

    with TestClient(application) as client:
        response = client.post(
            f"/api/v1/catalog/courses/{COURSE_ID}/topics",
            headers=organization_headers(),
            json=valid_topic_payload(),
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Course was not found."}


def test_unknown_topic_returns_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_get_topic(
        organization_id: UUID,
        course_id: UUID,
        topic_id: UUID,
    ) -> None:
        assert organization_id == ORGANIZATION_ID
        assert course_id == COURSE_ID
        assert topic_id == TOPIC_ID
        return None

    monkeypatch.setattr(
        catalog_routes.topic_repository,
        "get_topic",
        fake_get_topic,
    )

    application = create_test_application(MembershipRole.TUTOR)

    with TestClient(application) as client:
        response = client.get(
            (
                f"/api/v1/catalog/courses/{COURSE_ID}"
                f"/topics/{TOPIC_ID}"
            ),
            headers=organization_headers(),
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Topic was not found."}


def test_admin_can_update_topic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_update_topic(
        organization_id: UUID,
        course_id: UUID,
        topic_id: UUID,
        payload: TopicUpdate,
    ) -> TopicResponse:
        calls["organization_id"] = organization_id
        calls["course_id"] = course_id
        calls["topic_id"] = topic_id
        calls["payload"] = payload
        return TOPIC.model_copy(
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
        catalog_routes.topic_repository,
        "update_topic",
        fake_update_topic,
    )

    application = create_test_application(MembershipRole.ADMIN)
    update_payload = valid_topic_payload()
    update_payload["title"] = "Updated Cloud Concepts"
    update_payload["sequence_number"] = 2

    with TestClient(application) as client:
        response = client.put(
            (
                f"/api/v1/catalog/courses/{COURSE_ID}"
                f"/topics/{TOPIC_ID}"
            ),
            headers=organization_headers(),
            json=update_payload,
        )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated Cloud Concepts"
    assert response.json()["sequence_number"] == 2
    assert calls["organization_id"] == ORGANIZATION_ID
    assert calls["course_id"] == COURSE_ID
    assert calls["topic_id"] == TOPIC_ID

    payload = calls["payload"]
    assert isinstance(payload, TopicUpdate)
    assert payload.sequence_number == 2


def test_duplicate_topic_returns_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def duplicate_topic(
        *_args: object,
        **_kwargs: object,
    ) -> TopicResponse:
        raise IntegrityError(
            "INSERT INTO topics",
            {},
            RuntimeError("duplicate"),
        )

    monkeypatch.setattr(
        catalog_routes.topic_repository,
        "create_topic",
        duplicate_topic,
    )

    application = create_test_application(MembershipRole.ADMIN)

    with TestClient(application) as client:
        response = client.post(
            f"/api/v1/catalog/courses/{COURSE_ID}/topics",
            headers=organization_headers(),
            json=valid_topic_payload(),
        )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Topic conflicts with an existing record."
    }


def test_topic_database_failure_returns_service_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable_topic(
        *_args: object,
        **_kwargs: object,
    ) -> TopicResponse:
        raise SQLAlchemyError("database unavailable")

    monkeypatch.setattr(
        catalog_routes.topic_repository,
        "get_topic",
        unavailable_topic,
    )

    application = create_test_application(MembershipRole.ADMIN)

    with TestClient(application) as client:
        response = client.get(
            (
                f"/api/v1/catalog/courses/{COURSE_ID}"
                f"/topics/{TOPIC_ID}"
            ),
            headers=organization_headers(),
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Catalog service is unavailable."
    }


def test_user_cannot_access_topics_in_another_organization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_repository_call(
        *_args: object,
        **_kwargs: object,
    ) -> None:
        raise AssertionError("Repository must not be called.")

    monkeypatch.setattr(
        catalog_routes.topic_repository,
        "get_topic",
        unexpected_repository_call,
    )

    application = create_test_application(MembershipRole.ADMIN)

    with TestClient(application) as client:
        response = client.get(
            (
                f"/api/v1/catalog/courses/{COURSE_ID}"
                f"/topics/{TOPIC_ID}"
            ),
            headers=organization_headers(OTHER_ORGANIZATION_ID),
        )

    assert response.status_code == 403


def test_invalid_topic_pagination_is_rejected() -> None:
    application = create_test_application(MembershipRole.STUDENT)

    with TestClient(application) as client:
        response = client.get(
            (
                f"/api/v1/catalog/courses/{COURSE_ID}/topics"
                "?limit=101&offset=-1"
            ),
            headers=organization_headers(),
        )

    assert response.status_code == 422
