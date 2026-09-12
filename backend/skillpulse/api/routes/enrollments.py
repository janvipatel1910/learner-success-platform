"""Organisation-scoped cohort enrollment and roster API routes."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from skillpulse.api.dependencies.auth import (
    OrganizationAccess,
    require_organization_roles,
)
from skillpulse.db import cohort_memberships as membership_repository
from skillpulse.db import cohorts as cohort_repository
from skillpulse.db.identity import MembershipRole
from skillpulse.schemas.catalog import PaginatedResponse
from skillpulse.schemas.enrollment import (
    CohortMembershipCreate,
    CohortMembershipResponse,
    CohortMembershipUpdate,
    MyCohortMembershipResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/catalog",
    tags=["cohort enrollments"],
)

_require_self_membership_access = require_organization_roles(
    MembershipRole.STUDENT,
    MembershipRole.TUTOR,
    MembershipRole.ADMIN,
)
_require_roster_role_access = require_organization_roles(
    MembershipRole.TUTOR,
    MembershipRole.ADMIN,
)
_require_enrollment_admin_access = require_organization_roles(
    MembershipRole.ADMIN,
)

SelfMembershipAccess = Annotated[
    OrganizationAccess,
    Depends(_require_self_membership_access),
]
RosterRoleAccess = Annotated[
    OrganizationAccess,
    Depends(_require_roster_role_access),
]
EnrollmentAdminAccess = Annotated[
    OrganizationAccess,
    Depends(_require_enrollment_admin_access),
]


def _cohort_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Cohort was not found.",
    )


def _membership_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Cohort membership was not found.",
    )


def _enrollment_unavailable(
    exc: SQLAlchemyError,
) -> HTTPException:
    logger.warning(
        "Cohort enrollment database operation failed: %s",
        exc.__class__.__name__,
    )
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Cohort enrollment service is unavailable.",
    )


def _resolve_roster_access(
    course_id: UUID,
    cohort_id: UUID,
    access: RosterRoleAccess,
) -> OrganizationAccess:
    """Allow administrators or the cohort's assigned active tutor."""

    if MembershipRole.ADMIN in access.roles:
        return access

    try:
        is_assigned = membership_repository.is_active_cohort_tutor(
            access.organization_id,
            course_id,
            cohort_id,
            access.user.user_id,
        )
    except SQLAlchemyError as exc:
        raise _enrollment_unavailable(exc) from exc

    if not is_assigned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tutor is not assigned to this cohort.",
        )

    return access


CohortRosterAccess = Annotated[
    OrganizationAccess,
    Depends(_resolve_roster_access),
]


@router.get(
    "/my-cohort-memberships",
    response_model=PaginatedResponse[MyCohortMembershipResponse],
)
def list_my_cohort_membership_records(
    access: SelfMembershipAccess,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedResponse[MyCohortMembershipResponse]:
    """List only the authenticated user's cohort memberships."""

    try:
        memberships, total = (
            membership_repository.list_my_cohort_memberships(
                access.organization_id,
                access.user.user_id,
                limit=limit,
                offset=offset,
            )
        )
    except SQLAlchemyError as exc:
        raise _enrollment_unavailable(exc) from exc

    return PaginatedResponse[MyCohortMembershipResponse](
        items=memberships,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/courses/{course_id}/cohorts/{cohort_id}/members",
    response_model=PaginatedResponse[CohortMembershipResponse],
)
def list_cohort_membership_records(
    course_id: UUID,
    cohort_id: UUID,
    access: CohortRosterAccess,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedResponse[CohortMembershipResponse]:
    """List a cohort roster as an administrator or assigned tutor."""

    try:
        cohort = cohort_repository.get_cohort(
            access.organization_id,
            course_id,
            cohort_id,
        )
        if cohort is None:
            raise _cohort_not_found()

        memberships, total = (
            membership_repository.list_cohort_memberships(
                access.organization_id,
                course_id,
                cohort_id,
                limit=limit,
                offset=offset,
            )
        )
    except SQLAlchemyError as exc:
        raise _enrollment_unavailable(exc) from exc

    return PaginatedResponse[CohortMembershipResponse](
        items=memberships,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    (
        "/courses/{course_id}/cohorts/{cohort_id}"
        "/members/{membership_id}"
    ),
    response_model=CohortMembershipResponse,
)
def get_cohort_membership_record(
    course_id: UUID,
    cohort_id: UUID,
    membership_id: UUID,
    access: CohortRosterAccess,
) -> CohortMembershipResponse:
    """Return one scoped roster membership."""

    try:
        membership = membership_repository.get_cohort_membership(
            access.organization_id,
            course_id,
            cohort_id,
            membership_id,
        )
    except SQLAlchemyError as exc:
        raise _enrollment_unavailable(exc) from exc

    if membership is None:
        raise _membership_not_found()

    return membership


@router.post(
    "/courses/{course_id}/cohorts/{cohort_id}/members",
    response_model=CohortMembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_cohort_membership_record(
    course_id: UUID,
    cohort_id: UUID,
    payload: CohortMembershipCreate,
    access: EnrollmentAdminAccess,
) -> CohortMembershipResponse:
    """Enroll an eligible organisation member as an administrator."""

    try:
        membership = membership_repository.create_cohort_membership(
            access.organization_id,
            course_id,
            cohort_id,
            payload,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already enrolled in this cohort.",
        ) from exc
    except SQLAlchemyError as exc:
        raise _enrollment_unavailable(exc) from exc

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Cohort or eligible organisation member "
                "was not found."
            ),
        )

    return membership


@router.put(
    (
        "/courses/{course_id}/cohorts/{cohort_id}"
        "/members/{membership_id}"
    ),
    response_model=CohortMembershipResponse,
)
def update_cohort_membership_record(
    course_id: UUID,
    cohort_id: UUID,
    membership_id: UUID,
    payload: CohortMembershipUpdate,
    access: EnrollmentAdminAccess,
) -> CohortMembershipResponse:
    """Update an eligible cohort membership as an administrator."""

    try:
        membership = membership_repository.update_cohort_membership(
            access.organization_id,
            course_id,
            cohort_id,
            membership_id,
            payload,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cohort membership conflicts with existing data.",
        ) from exc
    except SQLAlchemyError as exc:
        raise _enrollment_unavailable(exc) from exc

    if membership is None:
        raise _membership_not_found()

    return membership
