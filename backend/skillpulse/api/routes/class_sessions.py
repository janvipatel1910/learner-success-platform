"""Organisation-scoped class-session API routes."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from skillpulse.api.dependencies.auth import (
    OrganizationAccess,
    require_organization_roles,
)
from skillpulse.db import class_sessions as session_repository
from skillpulse.db import cohort_memberships as membership_repository
from skillpulse.db import cohorts as cohort_repository
from skillpulse.db.identity import MembershipRole
from skillpulse.schemas.catalog import PaginatedResponse
from skillpulse.schemas.class_sessions import (
    ClassSessionCreate,
    ClassSessionResponse,
    ClassSessionUpdate,
)
from skillpulse.schemas.enrollment import CohortRole

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/catalog",
    tags=["class sessions"],
)

_require_session_member_role = require_organization_roles(
    MembershipRole.STUDENT,
    MembershipRole.TUTOR,
    MembershipRole.ADMIN,
)

_require_session_writer_role = require_organization_roles(
    MembershipRole.TUTOR,
    MembershipRole.ADMIN,
)

SessionMemberRoleAccess = Annotated[
    OrganizationAccess,
    Depends(_require_session_member_role),
]

SessionWriterRoleAccess = Annotated[
    OrganizationAccess,
    Depends(_require_session_writer_role),
]


def _cohort_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Cohort was not found.",
    )


def _session_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Class session was not found.",
    )


def _session_service_unavailable(
    exc: SQLAlchemyError,
) -> HTTPException:
    logger.warning(
        "Class-session database operation failed: %s",
        exc.__class__.__name__,
    )
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Class-session service is unavailable.",
    )


def _resolve_session_read_access(
    course_id: UUID,
    cohort_id: UUID,
    access: SessionMemberRoleAccess,
) -> OrganizationAccess:
    """Allow admins or users with a matching active cohort role."""

    if MembershipRole.ADMIN in access.roles:
        return access

    allowed_cohort_roles: list[CohortRole] = []
    if MembershipRole.STUDENT in access.roles:
        allowed_cohort_roles.append(CohortRole.LEARNER)
    if MembershipRole.TUTOR in access.roles:
        allowed_cohort_roles.append(CohortRole.TUTOR)

    try:
        is_active_member = any(
            membership_repository.has_active_cohort_role(
                access.organization_id,
                course_id,
                cohort_id,
                access.user.user_id,
                cohort_role,
            )
            for cohort_role in allowed_cohort_roles
        )
    except SQLAlchemyError as exc:
        raise _session_service_unavailable(exc) from exc

    if not is_active_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not an active member of this cohort.",
        )

    return access


def _resolve_session_write_access(
    course_id: UUID,
    cohort_id: UUID,
    access: SessionWriterRoleAccess,
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
        raise _session_service_unavailable(exc) from exc

    if not is_active_tutor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tutor is not assigned to this cohort.",
        )

    return access


SessionReadAccess = Annotated[
    OrganizationAccess,
    Depends(_resolve_session_read_access),
]

SessionWriteAccess = Annotated[
    OrganizationAccess,
    Depends(_resolve_session_write_access),
]


@router.get(
    "/courses/{course_id}/cohorts/{cohort_id}/sessions",
    response_model=PaginatedResponse[ClassSessionResponse],
)
def list_class_session_records(
    course_id: UUID,
    cohort_id: UUID,
    access: SessionReadAccess,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedResponse[ClassSessionResponse]:
    """List sessions for an authorised cohort member."""

    try:
        cohort = cohort_repository.get_cohort(
            access.organization_id,
            course_id,
            cohort_id,
        )
        if cohort is None:
            raise _cohort_not_found()

        sessions, total = session_repository.list_class_sessions(
            access.organization_id,
            course_id,
            cohort_id,
            limit=limit,
            offset=offset,
        )
    except SQLAlchemyError as exc:
        raise _session_service_unavailable(exc) from exc

    return PaginatedResponse[ClassSessionResponse](
        items=sessions,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    (
        "/courses/{course_id}/cohorts/{cohort_id}"
        "/sessions/{session_id}"
    ),
    response_model=ClassSessionResponse,
)
def get_class_session_record(
    course_id: UUID,
    cohort_id: UUID,
    session_id: UUID,
    access: SessionReadAccess,
) -> ClassSessionResponse:
    """Return one session to an authorised cohort member."""

    try:
        class_session = session_repository.get_class_session(
            access.organization_id,
            course_id,
            cohort_id,
            session_id,
        )
    except SQLAlchemyError as exc:
        raise _session_service_unavailable(exc) from exc

    if class_session is None:
        raise _session_not_found()

    return class_session


@router.post(
    "/courses/{course_id}/cohorts/{cohort_id}/sessions",
    response_model=ClassSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_class_session_record(
    course_id: UUID,
    cohort_id: UUID,
    payload: ClassSessionCreate,
    access: SessionWriteAccess,
) -> ClassSessionResponse:
    """Create a session as an admin or assigned tutor."""

    try:
        class_session = session_repository.create_class_session(
            access.organization_id,
            course_id,
            cohort_id,
            payload,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A class session already exists at this "
                "cohort start time."
            ),
        ) from exc
    except SQLAlchemyError as exc:
        raise _session_service_unavailable(exc) from exc

    if class_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cohort or topic was not found in this course.",
        )

    return class_session


@router.put(
    (
        "/courses/{course_id}/cohorts/{cohort_id}"
        "/sessions/{session_id}"
    ),
    response_model=ClassSessionResponse,
)
def update_class_session_record(
    course_id: UUID,
    cohort_id: UUID,
    session_id: UUID,
    payload: ClassSessionUpdate,
    access: SessionWriteAccess,
) -> ClassSessionResponse:
    """Update a session as an admin or assigned tutor."""

    try:
        class_session = session_repository.update_class_session(
            access.organization_id,
            course_id,
            cohort_id,
            session_id,
            payload,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Class-session schedule conflicts with "
                "an existing session."
            ),
        ) from exc
    except SQLAlchemyError as exc:
        raise _session_service_unavailable(exc) from exc

    if class_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Class session or topic was not found "
                "in this course."
            ),
        )

    return class_session
