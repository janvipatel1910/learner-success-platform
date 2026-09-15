"""Tests for organisation-scoped class-session API routes."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from skillpulse.api.dependencies.auth import get_current_user
from skillpulse.api.routes import class_sessions as session_routes
from skillpulse.db.identity import (
    AuthenticatedUser,
    MembershipRole,
    OrganizationMembership,
)
from skillpulse.schemas.class_sessions import (
    ClassSessionCreate,
    ClassSessionResponse,
    ClassSessionUpdate,
    SessionStatus,
)
from skillpulse.schemas.enrollment import CohortRole

ORGANIZATION_ID = UUID("10000000-0000-0000-0000-000000000001")
OTHER_ORGANIZATION_ID = UUID(
    "10000000-0000-0000-0000-000000000099"
)
AUTHENTICATED_USER_ID = UUID(
    "20000000-0000-0000-0000-000000000001"
)
COURSE_ID = UUID("40000000-0000-0000-0000-000000000001")
COHORT_ID = UUID("42000000-0000-0000-0000-000000000001")
TOPIC_ID = UUID("41000000-0000-0000-0000-000000000001")
SESSION_ID = UUID("50000000-0000-0000-0000-000000000001")

SESSIONS_PATH = (
    f"/api/v1/catalog/courses/{COURSE_ID}"
    f"/cohorts/{COHORT_ID}/sessions"
)
SESSION_PATH = f"{SESSIONS_PATH}/{SESSION_ID}"

CLASS_SESSION = ClassSessionResponse(
    id=SESSION_ID,
    cohort_id=COHORT_ID,
    topic_id=TOPIC_ID,
    title="VPC Foundations",
    scheduled_start=datetime(2026, 9, 15, 9, 0, tzinfo=UTC),
    scheduled_end=datetime(2026, 9, 15, 11, 0, tzinfo=UTC),
    delivery_link="https://meet.example.com/vpc-foundations",
    recording_url=None,
    status=SessionStatus.SCHEDULED,
    created_at=datetime(2026, 9, 13, 10, 0, tzinfo=UTC),
    updated_at=datetime(2026, 9, 13, 10, 0, tzinfo=UTC),
)

UPDATED_CLASS_SESSION = CLASS_SESSION.model_copy(
    update={
        "title": "VPC Foundations Recording",
        "recording_url": (
            "https://recordings.example.com/vpc-foundations"
        ),
        "status": SessionStatus.COMPLETED,
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
    """Create an isolated application with class-session routes."""

    application = FastAPI()
    application.include_router(
        session_routes.router,
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


def valid_create_payload() -> dict[str, str]:
    """Return a valid class-session creation payload."""

    return {
        "topic_id": str(TOPIC_ID),
        "title": "VPC Foundations",
        "scheduled_start": "2026-09-15T09:00:00Z",
        "scheduled_end": "2026-09-15T11:00:00Z",
        "delivery_link": (
            "https://meet.example.com/vpc-foundations"
        ),
    }


def valid_update_payload() -> dict[str, str]:
    """Return a valid complete class-session update payload."""

    return {
        **valid_create_payload(),
        "title": "VPC Foundations Recording",
        "recording_url": (
            "https://recordings.example.com/vpc-foundations"
        ),
        "status": "completed",
    }


def unexpected_repository_call(
    *_args: object,
    **_kwargs: object,
) -> None:
    """Fail when authorization should prevent repository access."""

    raise AssertionError("Repository must not be called.")


@pytest.mark.parametrize(
    ("organization_role", "expected_cohort_role"),
    [
        (MembershipRole.STUDENT, CohortRole.LEARNER),
        (MembershipRole.TUTOR, CohortRole.TUTOR),
    ],
)
def test_active_cohort_members_can_list_sessions(
    organization_role: MembershipRole,
    expected_cohort_role: CohortRole,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_has_active_role(
        organization_id: UUID,
        course_id: UUID,
        cohort_id: UUID,
        user_id: UUID,
        cohort_role: CohortRole,
    ) -> bool:
        calls["access"] = (
            organization_id,
            course_id,
            cohort_id,
            user_id,
            cohort_role,
        )
        return cohort_role is expected_cohort_role

    def fake_list_sessions(
        organization_id: UUID,
        course_id: UUID,
        cohort_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[ClassSessionResponse], int]:
        calls["list"] = (
            organization_id,
            course_id,
            cohort_id,
            limit,
            offset,
        )
        return [CLASS_SESSION], 1

    monkeypatch.setattr(
        session_routes.membership_repository,
        "has_active_cohort_role",
        fake_has_active_role,
    )
    monkeypatch.setattr(
        session_routes.cohort_repository,
        "get_cohort",
        lambda *_args: object(),
    )
    monkeypatch.setattr(
        session_routes.session_repository,
        "list_class_sessions",
        fake_list_sessions,
    )

    application = create_test_application(organization_role)
    with TestClient(application) as client:
        response = client.get(
            f"{SESSIONS_PATH}?limit=10&offset=2",
            headers=organization_headers(),
        )

    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == str(SESSION_ID)
    assert response.json()["total"] == 1
    assert response.json()["limit"] == 10
    assert response.json()["offset"] == 2
    assert calls["access"] == (
        ORGANIZATION_ID,
        COURSE_ID,
        COHORT_ID,
        AUTHENTICATED_USER_ID,
        expected_cohort_role,
    )
    assert calls["list"] == (
        ORGANIZATION_ID,
        COURSE_ID,
        COHORT_ID,
        10,
        2,
    )


def test_admin_can_list_without_cohort_assignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        session_routes.membership_repository,
        "has_active_cohort_role",
        unexpected_repository_call,
    )
    monkeypatch.setattr(
        session_routes.cohort_repository,
        "get_cohort",
        lambda *_args: object(),
    )
    monkeypatch.setattr(
        session_routes.session_repository,
        "list_class_sessions",
        lambda *_args, **_kwargs: ([CLASS_SESSION], 1),
    )

    application = create_test_application(MembershipRole.ADMIN)
    with TestClient(application) as client:
        response = client.get(
            SESSIONS_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 200
    assert response.json()["items"][0]["title"] == "VPC Foundations"


@pytest.mark.parametrize(
    "role",
    [
        MembershipRole.STUDENT,
        MembershipRole.TUTOR,
    ],
)
def test_user_without_active_cohort_role_cannot_read_sessions(
    role: MembershipRole,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        session_routes.membership_repository,
        "has_active_cohort_role",
        lambda *_args: False,
    )
    monkeypatch.setattr(
        session_routes.session_repository,
        "list_class_sessions",
        unexpected_repository_call,
    )

    application = create_test_application(role)
    with TestClient(application) as client:
        response = client.get(
            SESSIONS_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "User is not an active member of this cohort."
    }


def test_cross_organization_session_access_is_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        session_routes.membership_repository,
        "has_active_cohort_role",
        unexpected_repository_call,
    )
    monkeypatch.setattr(
        session_routes.session_repository,
        "list_class_sessions",
        unexpected_repository_call,
    )

    application = create_test_application(MembershipRole.STUDENT)
    with TestClient(application) as client:
        response = client.get(
            SESSIONS_PATH,
            headers=organization_headers(OTHER_ORGANIZATION_ID),
        )

    assert response.status_code == 403


def test_active_learner_can_get_one_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        session_routes.membership_repository,
        "has_active_cohort_role",
        lambda *_args: True,
    )
    monkeypatch.setattr(
        session_routes.session_repository,
        "get_class_session",
        lambda *_args: CLASS_SESSION,
    )

    application = create_test_application(MembershipRole.STUDENT)
    with TestClient(application) as client:
        response = client.get(
            SESSION_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 200
    assert response.json()["id"] == str(SESSION_ID)
    assert response.json()["status"] == "scheduled"


def test_missing_session_returns_scoped_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        session_routes.membership_repository,
        "has_active_cohort_role",
        unexpected_repository_call,
    )
    monkeypatch.setattr(
        session_routes.session_repository,
        "get_class_session",
        lambda *_args: None,
    )

    application = create_test_application(MembershipRole.ADMIN)
    with TestClient(application) as client:
        response = client.get(
            SESSION_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Class session was not found."
    }


def test_missing_cohort_returns_not_found_for_session_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        session_routes.cohort_repository,
        "get_cohort",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        session_routes.session_repository,
        "list_class_sessions",
        unexpected_repository_call,
    )

    application = create_test_application(MembershipRole.ADMIN)
    with TestClient(application) as client:
        response = client.get(
            SESSIONS_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Cohort was not found."}


@pytest.mark.parametrize(
    "query_string",
    [
        "?limit=0",
        "?limit=101",
        "?offset=-1",
    ],
)
def test_session_list_rejects_invalid_pagination(
    query_string: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        session_routes.session_repository,
        "list_class_sessions",
        unexpected_repository_call,
    )

    application = create_test_application(MembershipRole.ADMIN)
    with TestClient(application) as client:
        response = client.get(
            f"{SESSIONS_PATH}{query_string}",
            headers=organization_headers(),
        )

    assert response.status_code == 422


def test_student_cannot_create_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        session_routes.membership_repository,
        "has_active_cohort_role",
        unexpected_repository_call,
    )
    monkeypatch.setattr(
        session_routes.session_repository,
        "create_class_session",
        unexpected_repository_call,
    )

    application = create_test_application(MembershipRole.STUDENT)
    with TestClient(application) as client:
        response = client.post(
            SESSIONS_PATH,
            headers=organization_headers(),
            json=valid_create_payload(),
        )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Insufficient organization permissions."
    }


def test_assigned_tutor_can_create_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_has_active_role(
        organization_id: UUID,
        course_id: UUID,
        cohort_id: UUID,
        user_id: UUID,
        cohort_role: CohortRole,
    ) -> bool:
        calls["cohort_role"] = cohort_role
        calls["user_id"] = user_id
        return True

    def fake_create_session(
        organization_id: UUID,
        course_id: UUID,
        cohort_id: UUID,
        payload: ClassSessionCreate,
    ) -> ClassSessionResponse:
        calls["create"] = (
            organization_id,
            course_id,
            cohort_id,
        )
        calls["payload"] = payload
        return CLASS_SESSION

    monkeypatch.setattr(
        session_routes.membership_repository,
        "has_active_cohort_role",
        fake_has_active_role,
    )
    monkeypatch.setattr(
        session_routes.session_repository,
        "create_class_session",
        fake_create_session,
    )

    application = create_test_application(MembershipRole.TUTOR)
    with TestClient(application) as client:
        response = client.post(
            SESSIONS_PATH,
            headers=organization_headers(),
            json=valid_create_payload(),
        )

    assert response.status_code == 201
    assert response.json()["id"] == str(SESSION_ID)
    assert calls["cohort_role"] is CohortRole.TUTOR
    assert calls["user_id"] == AUTHENTICATED_USER_ID
    assert calls["create"] == (
        ORGANIZATION_ID,
        COURSE_ID,
        COHORT_ID,
    )
    assert isinstance(calls["payload"], ClassSessionCreate)
    assert calls["payload"].status is SessionStatus.SCHEDULED


def test_admin_create_bypasses_assignment_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        session_routes.membership_repository,
        "has_active_cohort_role",
        unexpected_repository_call,
    )
    monkeypatch.setattr(
        session_routes.session_repository,
        "create_class_session",
        lambda *_args: CLASS_SESSION,
    )

    application = create_test_application(MembershipRole.ADMIN)
    with TestClient(application) as client:
        response = client.post(
            SESSIONS_PATH,
            headers=organization_headers(),
            json=valid_create_payload(),
        )

    assert response.status_code == 201


def test_create_rejects_invalid_schedule_before_repository_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        **valid_create_payload(),
        "scheduled_end": "2026-09-15T09:00:00Z",
    }
    monkeypatch.setattr(
        session_routes.session_repository,
        "create_class_session",
        unexpected_repository_call,
    )

    application = create_test_application(MembershipRole.ADMIN)
    with TestClient(application) as client:
        response = client.post(
            SESSIONS_PATH,
            headers=organization_headers(),
            json=payload,
        )

    assert response.status_code == 422


def test_duplicate_session_start_returns_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_duplicate(*_args: object) -> None:
        raise IntegrityError(
            "statement",
            {},
            Exception("private duplicate detail"),
        )

    monkeypatch.setattr(
        session_routes.session_repository,
        "create_class_session",
        raise_duplicate,
    )

    application = create_test_application(MembershipRole.ADMIN)
    with TestClient(application) as client:
        response = client.post(
            SESSIONS_PATH,
            headers=organization_headers(),
            json=valid_create_payload(),
        )

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            "A class session already exists at this "
            "cohort start time."
        )
    }
    assert "private duplicate" not in response.text


def test_create_with_invalid_parent_returns_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        session_routes.session_repository,
        "create_class_session",
        lambda *_args: None,
    )

    application = create_test_application(MembershipRole.ADMIN)
    with TestClient(application) as client:
        response = client.post(
            SESSIONS_PATH,
            headers=organization_headers(),
            json=valid_create_payload(),
        )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Cohort or topic was not found in this course."
    }


def test_assigned_tutor_can_update_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_has_active_role(
        organization_id: UUID,
        course_id: UUID,
        cohort_id: UUID,
        user_id: UUID,
        cohort_role: CohortRole,
    ) -> bool:
        calls["access"] = (
            organization_id,
            course_id,
            cohort_id,
            user_id,
            cohort_role,
        )
        return True

    def fake_update_session(
        organization_id: UUID,
        course_id: UUID,
        cohort_id: UUID,
        session_id: UUID,
        payload: ClassSessionUpdate,
    ) -> ClassSessionResponse:
        calls["update"] = (
            organization_id,
            course_id,
            cohort_id,
            session_id,
        )
        calls["payload"] = payload
        return UPDATED_CLASS_SESSION

    monkeypatch.setattr(
        session_routes.membership_repository,
        "has_active_cohort_role",
        fake_has_active_role,
    )
    monkeypatch.setattr(
        session_routes.session_repository,
        "update_class_session",
        fake_update_session,
    )

    application = create_test_application(MembershipRole.TUTOR)
    with TestClient(application) as client:
        response = client.put(
            SESSION_PATH,
            headers=organization_headers(),
            json=valid_update_payload(),
        )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert calls["access"] == (
        ORGANIZATION_ID,
        COURSE_ID,
        COHORT_ID,
        AUTHENTICATED_USER_ID,
        CohortRole.TUTOR,
    )
    assert calls["update"] == (
        ORGANIZATION_ID,
        COURSE_ID,
        COHORT_ID,
        SESSION_ID,
    )
    assert isinstance(calls["payload"], ClassSessionUpdate)
    assert calls["payload"].status is SessionStatus.COMPLETED


def test_update_schedule_conflict_returns_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_duplicate(*_args: object) -> None:
        raise IntegrityError(
            "statement",
            {},
            Exception("private duplicate detail"),
        )

    monkeypatch.setattr(
        session_routes.session_repository,
        "update_class_session",
        raise_duplicate,
    )

    application = create_test_application(MembershipRole.ADMIN)
    with TestClient(application) as client:
        response = client.put(
            SESSION_PATH,
            headers=organization_headers(),
            json=valid_update_payload(),
        )

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            "Class-session schedule conflicts with "
            "an existing session."
        )
    }
    assert "private duplicate" not in response.text


def test_update_with_invalid_session_or_topic_returns_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        session_routes.session_repository,
        "update_class_session",
        lambda *_args: None,
    )

    application = create_test_application(MembershipRole.ADMIN)
    with TestClient(application) as client:
        response = client.put(
            SESSION_PATH,
            headers=organization_headers(),
            json=valid_update_payload(),
        )

    assert response.status_code == 404
    assert response.json() == {
        "detail": (
            "Class session or topic was not found "
            "in this course."
        )
    }


def test_cohort_access_database_failure_returns_controlled_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable_access(*_args: object) -> None:
        raise SQLAlchemyError("private access failure")

    monkeypatch.setattr(
        session_routes.membership_repository,
        "has_active_cohort_role",
        unavailable_access,
    )

    application = create_test_application(MembershipRole.STUDENT)
    with TestClient(application) as client:
        response = client.get(
            SESSIONS_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Class-session service is unavailable."
    }
    assert "private access failure" not in response.text


def test_session_list_database_failure_returns_controlled_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable_list(
        *_args: object,
        **_kwargs: object,
    ) -> None:
        raise SQLAlchemyError("private list failure")

    monkeypatch.setattr(
        session_routes.cohort_repository,
        "get_cohort",
        lambda *_args: object(),
    )
    monkeypatch.setattr(
        session_routes.session_repository,
        "list_class_sessions",
        unavailable_list,
    )

    application = create_test_application(MembershipRole.ADMIN)
    with TestClient(application) as client:
        response = client.get(
            SESSIONS_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Class-session service is unavailable."
    }
    assert "private list failure" not in response.text


@pytest.mark.parametrize(
    ("method", "path", "repository_method", "payload"),
    [
        (
            "POST",
            SESSIONS_PATH,
            "create_class_session",
            valid_create_payload(),
        ),
        (
            "PUT",
            SESSION_PATH,
            "update_class_session",
            valid_update_payload(),
        ),
    ],
)
def test_session_write_database_failures_return_controlled_503(
    method: str,
    path: str,
    repository_method: str,
    payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable_write(*_args: object) -> None:
        raise SQLAlchemyError("private write failure")

    monkeypatch.setattr(
        session_routes.session_repository,
        repository_method,
        unavailable_write,
    )

    application = create_test_application(MembershipRole.ADMIN)
    with TestClient(application) as client:
        response = client.request(
            method,
            path,
            headers=organization_headers(),
            json=payload,
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Class-session service is unavailable."
    }
    assert "private write failure" not in response.text


def test_openapi_exposes_four_operations_without_delete() -> None:
    application = create_test_application(MembershipRole.ADMIN)
    schema = application.openapi()["paths"]

    collection_path = (
        "/api/v1/catalog/courses/{course_id}"
        "/cohorts/{cohort_id}/sessions"
    )
    item_path = f"{collection_path}/{{session_id}}"

    assert set(schema[collection_path]) == {"get", "post"}
    assert set(schema[item_path]) == {"get", "put"}
    assert "delete" not in schema[collection_path]
    assert "delete" not in schema[item_path]
