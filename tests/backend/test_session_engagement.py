"""Tests for attendance and understanding API routes."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from skillpulse.api.dependencies.auth import get_current_user
from skillpulse.api.routes import session_engagement as engagement_routes
from skillpulse.db.identity import (
    AuthenticatedUser,
    MembershipRole,
    OrganizationMembership,
)
from skillpulse.schemas.class_sessions import (
    ClassSessionResponse,
    SessionStatus,
)
from skillpulse.schemas.session_engagement import (
    AttendanceRecordResponse,
    AttendanceRosterItem,
    AttendanceStatus,
    AttendanceUpsert,
    UnderstandingCheckResponse,
    UnderstandingCheckUpsert,
    UnderstandingRating,
    UnderstandingRosterItem,
)

ORGANIZATION_ID = UUID("10000000-0000-0000-0000-000000000001")
OTHER_ORGANIZATION_ID = UUID(
    "10000000-0000-0000-0000-000000000099"
)
AUTHENTICATED_USER_ID = UUID(
    "20000000-0000-0000-0000-000000000002"
)
LEARNER_ID = UUID("20000000-0000-0000-0000-000000000003")
COURSE_ID = UUID("40000000-0000-0000-0000-000000000001")
COHORT_ID = UUID("42000000-0000-0000-0000-000000000001")
TOPIC_ID = UUID("41000000-0000-0000-0000-000000000001")
SESSION_ID = UUID("50000000-0000-0000-0000-000000000001")

SESSION_PATH = (
    f"/api/v1/catalog/courses/{COURSE_ID}"
    f"/cohorts/{COHORT_ID}/sessions/{SESSION_ID}"
)
ATTENDANCE_PATH = f"{SESSION_PATH}/attendance"
MY_ATTENDANCE_PATH = f"{SESSION_PATH}/my-attendance"
UNDERSTANDING_PATH = f"{SESSION_PATH}/understanding-checks"
MY_UNDERSTANDING_PATH = f"{SESSION_PATH}/my-understanding-check"

_TIMESTAMP = datetime(2026, 8, 5, 11, 5, tzinfo=UTC)

COMPLETED_SESSION = ClassSessionResponse(
    id=SESSION_ID,
    cohort_id=COHORT_ID,
    topic_id=TOPIC_ID,
    title="VPC Foundations",
    scheduled_start=datetime(2026, 8, 5, 9, 0, tzinfo=UTC),
    scheduled_end=datetime(2026, 8, 5, 11, 0, tzinfo=UTC),
    delivery_link="https://meet.example.com/vpc-foundations",
    recording_url=None,
    status=SessionStatus.COMPLETED,
    created_at=_TIMESTAMP,
    updated_at=_TIMESTAMP,
)

SCHEDULED_SESSION = COMPLETED_SESSION.model_copy(
    update={"status": SessionStatus.SCHEDULED}
)

ATTENDANCE_RECORD = AttendanceRecordResponse(
    id=UUID("51000000-0000-0000-0000-000000000001"),
    session_id=SESSION_ID,
    learner_id=LEARNER_ID,
    email="learner@skillpulse.example",
    full_name="Synthetic Learner",
    attendance_status=AttendanceStatus.PRESENT,
    minutes_attended=120,
    recorded_by=AUTHENTICATED_USER_ID,
    recorded_at=_TIMESTAMP,
    created_at=_TIMESTAMP,
    updated_at=_TIMESTAMP,
)

ATTENDANCE_ITEM = AttendanceRosterItem(
    session_id=SESSION_ID,
    learner_id=LEARNER_ID,
    email="learner@skillpulse.example",
    full_name="Synthetic Learner",
    attendance_id=ATTENDANCE_RECORD.id,
    attendance_status=AttendanceStatus.PRESENT,
    minutes_attended=120,
    recorded_by=AUTHENTICATED_USER_ID,
    recorded_at=_TIMESTAMP,
)

UNDERSTANDING_CHECK = UnderstandingCheckResponse(
    id=UUID("52000000-0000-0000-0000-000000000001"),
    session_id=SESSION_ID,
    learner_id=LEARNER_ID,
    email="learner@skillpulse.example",
    full_name="Synthetic Learner",
    rating=UnderstandingRating.GREEN,
    confidence_score=100,
    comment="Comfortable with subnet and routing concepts.",
    submitted_at=_TIMESTAMP,
    created_at=_TIMESTAMP,
    updated_at=_TIMESTAMP,
)

UNDERSTANDING_ITEM = UnderstandingRosterItem(
    session_id=SESSION_ID,
    learner_id=LEARNER_ID,
    email="learner@skillpulse.example",
    full_name="Synthetic Learner",
    understanding_check_id=UNDERSTANDING_CHECK.id,
    rating=UnderstandingRating.GREEN,
    confidence_score=100,
    comment="Comfortable with subnet and routing concepts.",
    submitted_at=_TIMESTAMP,
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
    """Create an isolated application with engagement routes."""

    application = FastAPI()
    application.include_router(
        engagement_routes.router,
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
    """Fail when authorization should prevent repository access."""

    raise AssertionError("Repository must not be called.")


def permit_scoped_access(
    monkeypatch: pytest.MonkeyPatch,
    class_session: ClassSessionResponse = COMPLETED_SESSION,
) -> None:
    """Permit cohort access and return a scoped class session."""

    monkeypatch.setattr(
        engagement_routes.membership_repository,
        "has_active_cohort_role",
        lambda *_args: True,
    )
    monkeypatch.setattr(
        engagement_routes.session_repository,
        "get_class_session",
        lambda *_args: class_session,
    )


def test_assigned_tutor_can_list_attendance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_list_attendance(
        organization_id: UUID,
        course_id: UUID,
        cohort_id: UUID,
        session_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[AttendanceRosterItem], int]:
        calls["list"] = (
            organization_id,
            course_id,
            cohort_id,
            session_id,
            limit,
            offset,
        )
        return [ATTENDANCE_ITEM], 1

    permit_scoped_access(monkeypatch)
    monkeypatch.setattr(
        engagement_routes.engagement_repository,
        "list_session_attendance",
        fake_list_attendance,
    )

    application = create_test_application(MembershipRole.TUTOR)
    with TestClient(application) as client:
        response = client.get(
            f"{ATTENDANCE_PATH}?limit=10&offset=2",
            headers=organization_headers(),
        )

    assert response.status_code == 200
    assert response.json()["items"][0]["learner_id"] == str(
        LEARNER_ID
    )
    assert response.json()["total"] == 1
    assert response.json()["limit"] == 10
    assert response.json()["offset"] == 2
    assert calls["list"] == (
        ORGANIZATION_ID,
        COURSE_ID,
        COHORT_ID,
        SESSION_ID,
        10,
        2,
    )


def test_admin_can_list_attendance_without_assignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        engagement_routes.membership_repository,
        "has_active_cohort_role",
        unexpected_repository_call,
    )
    monkeypatch.setattr(
        engagement_routes.session_repository,
        "get_class_session",
        lambda *_args: COMPLETED_SESSION,
    )
    monkeypatch.setattr(
        engagement_routes.engagement_repository,
        "list_session_attendance",
        lambda *_args, **_kwargs: ([ATTENDANCE_ITEM], 1),
    )

    application = create_test_application(MembershipRole.ADMIN)
    with TestClient(application) as client:
        response = client.get(
            ATTENDANCE_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 200
    assert response.json()["items"][0]["attendance_status"] == (
        "present"
    )


@pytest.mark.parametrize(
    "path",
    [
        ATTENDANCE_PATH,
        UNDERSTANDING_PATH,
    ],
)
def test_student_cannot_read_staff_rosters(
    path: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        engagement_routes.membership_repository,
        "has_active_cohort_role",
        unexpected_repository_call,
    )
    monkeypatch.setattr(
        engagement_routes.session_repository,
        "get_class_session",
        unexpected_repository_call,
    )

    application = create_test_application(MembershipRole.STUDENT)
    with TestClient(application) as client:
        response = client.get(
            path,
            headers=organization_headers(),
        )

    assert response.status_code == 403


def test_unassigned_tutor_cannot_read_attendance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        engagement_routes.membership_repository,
        "has_active_cohort_role",
        lambda *_args: False,
    )
    monkeypatch.setattr(
        engagement_routes.session_repository,
        "get_class_session",
        unexpected_repository_call,
    )

    application = create_test_application(MembershipRole.TUTOR)
    with TestClient(application) as client:
        response = client.get(
            ATTENDANCE_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Tutor is not assigned to this cohort."
    }


def test_cross_organization_access_is_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        engagement_routes.membership_repository,
        "has_active_cohort_role",
        unexpected_repository_call,
    )
    monkeypatch.setattr(
        engagement_routes.session_repository,
        "get_class_session",
        unexpected_repository_call,
    )

    application = create_test_application(MembershipRole.TUTOR)
    with TestClient(application) as client:
        response = client.get(
            ATTENDANCE_PATH,
            headers=organization_headers(OTHER_ORGANIZATION_ID),
        )

    assert response.status_code == 403


def test_active_learner_gets_only_own_attendance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_get_attendance(
        organization_id: UUID,
        course_id: UUID,
        cohort_id: UUID,
        session_id: UUID,
        learner_id: UUID,
    ) -> AttendanceRecordResponse:
        calls["get"] = (
            organization_id,
            course_id,
            cohort_id,
            session_id,
            learner_id,
        )
        return ATTENDANCE_RECORD.model_copy(
            update={"learner_id": learner_id}
        )

    permit_scoped_access(monkeypatch)
    monkeypatch.setattr(
        engagement_routes.engagement_repository,
        "get_session_attendance",
        fake_get_attendance,
    )

    application = create_test_application(MembershipRole.STUDENT)
    with TestClient(application) as client:
        response = client.get(
            MY_ATTENDANCE_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 200
    assert response.json()["learner_id"] == str(
        AUTHENTICATED_USER_ID
    )
    assert calls["get"][-1] == AUTHENTICATED_USER_ID


@pytest.mark.parametrize(
    "role",
    [
        MembershipRole.TUTOR,
        MembershipRole.ADMIN,
    ],
)
def test_non_student_cannot_read_my_attendance(
    role: MembershipRole,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        engagement_routes.membership_repository,
        "has_active_cohort_role",
        unexpected_repository_call,
    )
    monkeypatch.setattr(
        engagement_routes.engagement_repository,
        "get_session_attendance",
        unexpected_repository_call,
    )

    application = create_test_application(role)
    with TestClient(application) as client:
        response = client.get(
            MY_ATTENDANCE_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 403


def test_missing_own_attendance_returns_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    permit_scoped_access(monkeypatch)
    monkeypatch.setattr(
        engagement_routes.engagement_repository,
        "get_session_attendance",
        lambda *_args: None,
    )

    application = create_test_application(MembershipRole.STUDENT)
    with TestClient(application) as client:
        response = client.get(
            MY_ATTENDANCE_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Attendance record was not found."
    }


def test_assigned_tutor_can_upsert_attendance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_upsert_attendance(
        organization_id: UUID,
        course_id: UUID,
        cohort_id: UUID,
        session_id: UUID,
        learner_id: UUID,
        recorded_by: UUID,
        payload: AttendanceUpsert,
    ) -> AttendanceRecordResponse:
        calls["upsert"] = (
            organization_id,
            course_id,
            cohort_id,
            session_id,
            learner_id,
            recorded_by,
            payload,
        )
        return ATTENDANCE_RECORD.model_copy(
            update={
                "attendance_status": payload.attendance_status,
                "minutes_attended": payload.minutes_attended,
            }
        )

    permit_scoped_access(monkeypatch)
    monkeypatch.setattr(
        engagement_routes.engagement_repository,
        "upsert_session_attendance",
        fake_upsert_attendance,
    )

    application = create_test_application(MembershipRole.TUTOR)
    with TestClient(application) as client:
        response = client.put(
            f"{ATTENDANCE_PATH}/{LEARNER_ID}",
            headers=organization_headers(),
            json={
                "attendance_status": "late",
                "minutes_attended": 75,
            },
        )

    assert response.status_code == 200
    assert response.json()["attendance_status"] == "late"
    assert response.json()["minutes_attended"] == 75
    assert calls["upsert"][4] == LEARNER_ID
    assert calls["upsert"][5] == AUTHENTICATED_USER_ID
    assert calls["upsert"][6].attendance_status is (
        AttendanceStatus.LATE
    )


def test_student_cannot_record_attendance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        engagement_routes.engagement_repository,
        "upsert_session_attendance",
        unexpected_repository_call,
    )

    application = create_test_application(MembershipRole.STUDENT)
    with TestClient(application) as client:
        response = client.put(
            f"{ATTENDANCE_PATH}/{LEARNER_ID}",
            headers=organization_headers(),
            json={
                "attendance_status": "present",
                "minutes_attended": 120,
            },
        )

    assert response.status_code == 403


def test_attendance_write_requires_completed_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    permit_scoped_access(
        monkeypatch,
        SCHEDULED_SESSION,
    )
    monkeypatch.setattr(
        engagement_routes.engagement_repository,
        "upsert_session_attendance",
        unexpected_repository_call,
    )

    application = create_test_application(MembershipRole.TUTOR)
    with TestClient(application) as client:
        response = client.put(
            f"{ATTENDANCE_PATH}/{LEARNER_ID}",
            headers=organization_headers(),
            json={
                "attendance_status": "present",
                "minutes_attended": 120,
            },
        )

    assert response.status_code == 409
    assert "completed class sessions" in response.json()["detail"]


def test_attendance_rejects_minutes_beyond_duration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    permit_scoped_access(monkeypatch)
    monkeypatch.setattr(
        engagement_routes.engagement_repository,
        "upsert_session_attendance",
        unexpected_repository_call,
    )

    application = create_test_application(MembershipRole.TUTOR)
    with TestClient(application) as client:
        response = client.put(
            f"{ATTENDANCE_PATH}/{LEARNER_ID}",
            headers=organization_headers(),
            json={
                "attendance_status": "present",
                "minutes_attended": 121,
            },
        )

    assert response.status_code == 422
    assert "cannot exceed" in response.json()["detail"]


def test_ineligible_attendance_target_returns_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    permit_scoped_access(monkeypatch)
    monkeypatch.setattr(
        engagement_routes.engagement_repository,
        "upsert_session_attendance",
        lambda *_args: None,
    )

    application = create_test_application(MembershipRole.TUTOR)
    with TestClient(application) as client:
        response = client.put(
            f"{ATTENDANCE_PATH}/{LEARNER_ID}",
            headers=organization_headers(),
            json={
                "attendance_status": "absent",
                "minutes_attended": 0,
            },
        )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Active learner was not found in this cohort."
    }


def test_assigned_tutor_can_list_understanding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    permit_scoped_access(monkeypatch)
    monkeypatch.setattr(
        engagement_routes.engagement_repository,
        "list_session_understanding",
        lambda *_args, **_kwargs: ([UNDERSTANDING_ITEM], 1),
    )

    application = create_test_application(MembershipRole.TUTOR)
    with TestClient(application) as client:
        response = client.get(
            UNDERSTANDING_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 200
    assert response.json()["items"][0]["rating"] == "green"
    assert response.json()["items"][0]["confidence_score"] == 100


def test_active_learner_can_get_own_understanding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_get_understanding(
        organization_id: UUID,
        course_id: UUID,
        cohort_id: UUID,
        session_id: UUID,
        learner_id: UUID,
    ) -> UnderstandingCheckResponse:
        calls["learner_id"] = learner_id
        return UNDERSTANDING_CHECK.model_copy(
            update={"learner_id": learner_id}
        )

    permit_scoped_access(monkeypatch)
    monkeypatch.setattr(
        engagement_routes.engagement_repository,
        "get_session_understanding",
        fake_get_understanding,
    )

    application = create_test_application(MembershipRole.STUDENT)
    with TestClient(application) as client:
        response = client.get(
            MY_UNDERSTANDING_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 200
    assert response.json()["learner_id"] == str(
        AUTHENTICATED_USER_ID
    )
    assert calls["learner_id"] == AUTHENTICATED_USER_ID


def test_learner_can_upsert_only_own_understanding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_upsert_understanding(
        organization_id: UUID,
        course_id: UUID,
        cohort_id: UUID,
        session_id: UUID,
        learner_id: UUID,
        payload: UnderstandingCheckUpsert,
    ) -> UnderstandingCheckResponse:
        calls["upsert"] = (
            organization_id,
            course_id,
            cohort_id,
            session_id,
            learner_id,
            payload,
        )
        return UNDERSTANDING_CHECK.model_copy(
            update={
                "learner_id": learner_id,
                "rating": payload.rating,
                "comment": payload.comment,
            }
        )

    permit_scoped_access(monkeypatch)
    monkeypatch.setattr(
        engagement_routes.engagement_repository,
        "upsert_session_understanding",
        fake_upsert_understanding,
    )

    application = create_test_application(MembershipRole.STUDENT)
    with TestClient(application) as client:
        response = client.put(
            MY_UNDERSTANDING_PATH,
            headers=organization_headers(),
            json={
                "rating": "yellow",
                "comment": "Needs more routing practice.",
            },
        )

    assert response.status_code == 200
    assert response.json()["rating"] == "yellow"
    assert response.json()["comment"] == (
        "Needs more routing practice."
    )
    assert calls["upsert"][4] == AUTHENTICATED_USER_ID
    assert calls["upsert"][5].rating is (
        UnderstandingRating.YELLOW
    )


@pytest.mark.parametrize(
    "role",
    [
        MembershipRole.TUTOR,
        MembershipRole.ADMIN,
    ],
)
def test_staff_cannot_edit_learner_understanding(
    role: MembershipRole,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        engagement_routes.engagement_repository,
        "upsert_session_understanding",
        unexpected_repository_call,
    )

    application = create_test_application(role)
    with TestClient(application) as client:
        response = client.put(
            MY_UNDERSTANDING_PATH,
            headers=organization_headers(),
            json={"rating": "red"},
        )

    assert response.status_code == 403


def test_understanding_write_requires_completed_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    permit_scoped_access(
        monkeypatch,
        SCHEDULED_SESSION,
    )
    monkeypatch.setattr(
        engagement_routes.engagement_repository,
        "upsert_session_understanding",
        unexpected_repository_call,
    )

    application = create_test_application(MembershipRole.STUDENT)
    with TestClient(application) as client:
        response = client.put(
            MY_UNDERSTANDING_PATH,
            headers=organization_headers(),
            json={"rating": "green"},
        )

    assert response.status_code == 409


def test_database_failure_returns_controlled_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        engagement_routes.membership_repository,
        "has_active_cohort_role",
        lambda *_args: True,
    )

    def fail_get_session(*_args: object) -> None:
        raise SQLAlchemyError("internal database detail")

    monkeypatch.setattr(
        engagement_routes.session_repository,
        "get_class_session",
        fail_get_session,
    )

    application = create_test_application(MembershipRole.TUTOR)
    with TestClient(application) as client:
        response = client.get(
            ATTENDANCE_PATH,
            headers=organization_headers(),
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Session-engagement service is unavailable."
    }
    assert "internal database detail" not in response.text


def test_openapi_registers_five_paths_and_six_operations() -> None:
    application = FastAPI()
    application.include_router(
        engagement_routes.router,
        prefix="/api/v1",
    )

    schema = application.openapi()
    openapi_session_path = (
        "/api/v1/catalog/courses/{course_id}"
        "/cohorts/{cohort_id}/sessions/{session_id}"
    )
    expected_operations = {
        f"{openapi_session_path}/attendance": {"get"},
        f"{openapi_session_path}/my-attendance": {"get"},
        (
            f"{openapi_session_path}/attendance"
            "/{learner_id}"
        ): {"put"},
        f"{openapi_session_path}/understanding-checks": {"get"},
        f"{openapi_session_path}/my-understanding-check": {
            "get",
            "put",
        },
    }
    actual_operations = {
        path: set(schema["paths"][path])
        for path in expected_operations
    }

    assert actual_operations == expected_operations
    assert sum(
        len(operations)
        for operations in actual_operations.values()
    ) == 6
