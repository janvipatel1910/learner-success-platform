"""Organisation-scoped attendance and understanding API routes."""

import logging
from math import ceil
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError

from skillpulse.api.dependencies.auth import (
    OrganizationAccess,
    require_organization_roles,
)
from skillpulse.db import class_sessions as session_repository
from skillpulse.db import cohort_memberships as membership_repository
from skillpulse.db import session_engagement as engagement_repository
from skillpulse.db.identity import MembershipRole
from skillpulse.schemas.catalog import PaginatedResponse
from skillpulse.schemas.class_sessions import (
    ClassSessionResponse,
    SessionStatus,
)
from skillpulse.schemas.enrollment import CohortRole
from skillpulse.schemas.session_engagement import (
    AttendanceRecordResponse,
    AttendanceRosterItem,
    AttendanceUpsert,
    UnderstandingCheckResponse,
    UnderstandingCheckUpsert,
    UnderstandingRosterItem,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/catalog",
    tags=["session engagement"],
)

_require_staff_role = require_organization_roles(
    MembershipRole.TUTOR,
    MembershipRole.ADMIN,
)

_require_learner_role = require_organization_roles(
    MembershipRole.STUDENT,
)

StaffRoleAccess = Annotated[
    OrganizationAccess,
    Depends(_require_staff_role),
]

LearnerRoleAccess = Annotated[
    OrganizationAccess,
    Depends(_require_learner_role),
]


def _session_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Class session was not found.",
    )


def _record_not_found(record_name: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{record_name} was not found.",
    )


def _learner_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Active learner was not found in this cohort.",
    )


def _engagement_service_unavailable(
    exc: SQLAlchemyError,
) -> HTTPException:
    logger.warning(
        "Session-engagement database operation failed: %s",
        exc.__class__.__name__,
    )

    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Session-engagement service is unavailable.",
    )


def _resolve_staff_access(
    course_id: UUID,
    cohort_id: UUID,
    access: StaffRoleAccess,
) -> OrganizationAccess:
    """Allow admins or the cohort's active assigned tutor."""

    if MembershipRole.ADMIN in access.roles:
        return access

    try:
        is_active_tutor = membership_repository.has_active_cohort_role(
            access.organization_id,
            course_id,
            cohort_id,
            access.user.user_id,
            CohortRole.TUTOR,
        )
    except SQLAlchemyError as exc:
        raise _engagement_service_unavailable(exc) from exc

    if not is_active_tutor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tutor is not assigned to this cohort.",
        )

    return access


def _resolve_learner_access(
    course_id: UUID,
    cohort_id: UUID,
    access: LearnerRoleAccess,
) -> OrganizationAccess:
    """Require the authenticated student to be an active learner."""

    try:
        is_active_learner = membership_repository.has_active_cohort_role(
            access.organization_id,
            course_id,
            cohort_id,
            access.user.user_id,
            CohortRole.LEARNER,
        )
    except SQLAlchemyError as exc:
        raise _engagement_service_unavailable(exc) from exc

    if not is_active_learner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student is not an active learner in this cohort.",
        )

    return access


StaffAccess = Annotated[
    OrganizationAccess,
    Depends(_resolve_staff_access),
]

LearnerAccess = Annotated[
    OrganizationAccess,
    Depends(_resolve_learner_access),
]


def _get_scoped_session(
    access: OrganizationAccess,
    course_id: UUID,
    cohort_id: UUID,
    session_id: UUID,
) -> ClassSessionResponse:
    """Return a scoped class session or a controlled error."""

    try:
        class_session = session_repository.get_class_session(
            access.organization_id,
            course_id,
            cohort_id,
            session_id,
        )
    except SQLAlchemyError as exc:
        raise _engagement_service_unavailable(exc) from exc

    if class_session is None:
        raise _session_not_found()

    return class_session


def _require_completed_session(
    class_session: ClassSessionResponse,
) -> None:
    """Allow engagement writes only after a class is completed."""

    if class_session.status is not SessionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Attendance and understanding can be recorded "
                "only for completed class sessions."
            ),
        )


def _validate_attendance_duration(
    class_session: ClassSessionResponse,
    payload: AttendanceUpsert,
) -> None:
    """Prevent attended minutes exceeding the scheduled duration."""

    if payload.minutes_attended is None:
        return

    duration_minutes = ceil(
        (
            class_session.scheduled_end
            - class_session.scheduled_start
        ).total_seconds()
        / 60
    )

    if payload.minutes_attended > duration_minutes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "minutes_attended cannot exceed the "
                "class-session duration."
            ),
        )


@router.get(
    (
        "/courses/{course_id}/cohorts/{cohort_id}"
        "/sessions/{session_id}/attendance"
    ),
    response_model=PaginatedResponse[AttendanceRosterItem],
)
def list_attendance_roster(
    course_id: UUID,
    cohort_id: UUID,
    session_id: UUID,
    access: StaffAccess,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedResponse[AttendanceRosterItem]:
    """List attendance for an admin or assigned tutor."""

    _get_scoped_session(
        access,
        course_id,
        cohort_id,
        session_id,
    )

    try:
        attendance, total = (
            engagement_repository.list_session_attendance(
                access.organization_id,
                course_id,
                cohort_id,
                session_id,
                limit=limit,
                offset=offset,
            )
        )
    except SQLAlchemyError as exc:
        raise _engagement_service_unavailable(exc) from exc

    return PaginatedResponse[AttendanceRosterItem](
        items=attendance,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    (
        "/courses/{course_id}/cohorts/{cohort_id}"
        "/sessions/{session_id}/my-attendance"
    ),
    response_model=AttendanceRecordResponse,
)
def get_my_attendance(
    course_id: UUID,
    cohort_id: UUID,
    session_id: UUID,
    access: LearnerAccess,
) -> AttendanceRecordResponse:
    """Return only the authenticated learner's attendance."""

    _get_scoped_session(
        access,
        course_id,
        cohort_id,
        session_id,
    )

    try:
        attendance = engagement_repository.get_session_attendance(
            access.organization_id,
            course_id,
            cohort_id,
            session_id,
            access.user.user_id,
        )
    except SQLAlchemyError as exc:
        raise _engagement_service_unavailable(exc) from exc

    if attendance is None:
        raise _record_not_found("Attendance record")

    return attendance


@router.put(
    (
        "/courses/{course_id}/cohorts/{cohort_id}"
        "/sessions/{session_id}/attendance/{learner_id}"
    ),
    response_model=AttendanceRecordResponse,
)
def upsert_learner_attendance(
    course_id: UUID,
    cohort_id: UUID,
    session_id: UUID,
    learner_id: UUID,
    payload: AttendanceUpsert,
    access: StaffAccess,
) -> AttendanceRecordResponse:
    """Record attendance as an admin or assigned tutor."""

    class_session = _get_scoped_session(
        access,
        course_id,
        cohort_id,
        session_id,
    )
    _require_completed_session(class_session)
    _validate_attendance_duration(
        class_session,
        payload,
    )

    try:
        attendance = engagement_repository.upsert_session_attendance(
            access.organization_id,
            course_id,
            cohort_id,
            session_id,
            learner_id,
            access.user.user_id,
            payload,
        )
    except SQLAlchemyError as exc:
        raise _engagement_service_unavailable(exc) from exc

    if attendance is None:
        raise _learner_not_found()

    return attendance


@router.get(
    (
        "/courses/{course_id}/cohorts/{cohort_id}"
        "/sessions/{session_id}/understanding-checks"
    ),
    response_model=PaginatedResponse[UnderstandingRosterItem],
)
def list_understanding_roster(
    course_id: UUID,
    cohort_id: UUID,
    session_id: UUID,
    access: StaffAccess,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedResponse[UnderstandingRosterItem]:
    """List understanding checks for an admin or assigned tutor."""

    _get_scoped_session(
        access,
        course_id,
        cohort_id,
        session_id,
    )

    try:
        checks, total = (
            engagement_repository.list_session_understanding(
                access.organization_id,
                course_id,
                cohort_id,
                session_id,
                limit=limit,
                offset=offset,
            )
        )
    except SQLAlchemyError as exc:
        raise _engagement_service_unavailable(exc) from exc

    return PaginatedResponse[UnderstandingRosterItem](
        items=checks,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    (
        "/courses/{course_id}/cohorts/{cohort_id}"
        "/sessions/{session_id}/my-understanding-check"
    ),
    response_model=UnderstandingCheckResponse,
)
def get_my_understanding_check(
    course_id: UUID,
    cohort_id: UUID,
    session_id: UUID,
    access: LearnerAccess,
) -> UnderstandingCheckResponse:
    """Return only the authenticated learner's understanding check."""

    _get_scoped_session(
        access,
        course_id,
        cohort_id,
        session_id,
    )

    try:
        check = engagement_repository.get_session_understanding(
            access.organization_id,
            course_id,
            cohort_id,
            session_id,
            access.user.user_id,
        )
    except SQLAlchemyError as exc:
        raise _engagement_service_unavailable(exc) from exc

    if check is None:
        raise _record_not_found("Understanding check")

    return check


@router.put(
    (
        "/courses/{course_id}/cohorts/{cohort_id}"
        "/sessions/{session_id}/my-understanding-check"
    ),
    response_model=UnderstandingCheckResponse,
)
def upsert_my_understanding_check(
    course_id: UUID,
    cohort_id: UUID,
    session_id: UUID,
    payload: UnderstandingCheckUpsert,
    access: LearnerAccess,
) -> UnderstandingCheckResponse:
    """Create or update the authenticated learner's own check."""

    class_session = _get_scoped_session(
        access,
        course_id,
        cohort_id,
        session_id,
    )
    _require_completed_session(class_session)

    try:
        check = engagement_repository.upsert_session_understanding(
            access.organization_id,
            course_id,
            cohort_id,
            session_id,
            access.user.user_id,
            payload,
        )
    except SQLAlchemyError as exc:
        raise _engagement_service_unavailable(exc) from exc

    if check is None:
        raise _learner_not_found()

    return check
