"""Organisation-scoped learner blocker and tutor intervention routes."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError

from skillpulse.api.dependencies.auth import (
    OrganizationAccess,
    require_organization_roles,
)
from skillpulse.db import blocker_interventions as repository
from skillpulse.db import cohort_memberships as membership_repository
from skillpulse.db.identity import MembershipRole
from skillpulse.schemas.blocker_interventions import (
    BlockerCreate,
    BlockerDetailResponse,
    BlockerResponse,
    BlockerSeverity,
    BlockerStatus,
    BlockerUpdate,
    InterventionCompletion,
    InterventionCreate,
    InterventionOutcome,
    TutorInterventionResponse,
)
from skillpulse.schemas.catalog import PaginatedResponse
from skillpulse.schemas.enrollment import CohortRole

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/catalog",
    tags=["blocker interventions"],
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


def _service_unavailable(exc: SQLAlchemyError) -> HTTPException:
    """Return a controlled database-service error."""

    logger.warning(
        "Blocker-intervention database operation failed: %s",
        exc.__class__.__name__,
    )
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Blocker-intervention service is unavailable.",
    )


def _blocker_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Blocker was not found.",
    )


def _intervention_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Tutor intervention was not found.",
    )


def _resolve_staff_access(
    course_id: UUID,
    cohort_id: UUID,
    access: StaffRoleAccess,
) -> OrganizationAccess:
    """Allow administrators or active tutors assigned to the cohort."""

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
        raise _service_unavailable(exc) from exc

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
    """Require the authenticated student to be an active cohort learner."""

    try:
        is_active_learner = membership_repository.has_active_cohort_role(
            access.organization_id,
            course_id,
            cohort_id,
            access.user.user_id,
            CohortRole.LEARNER,
        )
    except SQLAlchemyError as exc:
        raise _service_unavailable(exc) from exc

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
LearnerCohortAccess = Annotated[
    OrganizationAccess,
    Depends(_resolve_learner_access),
]

_ALLOWED_TRANSITIONS: dict[BlockerStatus, frozenset[BlockerStatus]] = {
    BlockerStatus.OPEN: frozenset(
        {
            BlockerStatus.ASSIGNED,
            BlockerStatus.RESOLVED,
        }
    ),
    BlockerStatus.ASSIGNED: frozenset(
        {
            BlockerStatus.OPEN,
            BlockerStatus.WAITING_STUDENT,
            BlockerStatus.RESOLVED,
        }
    ),
    BlockerStatus.WAITING_STUDENT: frozenset(
        {
            BlockerStatus.OPEN,
            BlockerStatus.ASSIGNED,
            BlockerStatus.RESOLVED,
        }
    ),
    BlockerStatus.RESOLVED: frozenset(
        {
            BlockerStatus.OPEN,
            BlockerStatus.ASSIGNED,
            BlockerStatus.CLOSED,
        }
    ),
    BlockerStatus.CLOSED: frozenset(),
}


def _get_cohort_blocker(
    access: OrganizationAccess,
    course_id: UUID,
    cohort_id: UUID,
    blocker_id: UUID,
) -> BlockerDetailResponse:
    """Return one staff-scoped blocker or a controlled 404."""

    try:
        blocker = repository.get_cohort_blocker(
            access.organization_id,
            course_id,
            cohort_id,
            blocker_id,
        )
    except SQLAlchemyError as exc:
        raise _service_unavailable(exc) from exc

    if blocker is None:
        raise _blocker_not_found()

    return blocker


def _get_intervention(
    access: OrganizationAccess,
    course_id: UUID,
    cohort_id: UUID,
    blocker_id: UUID,
    intervention_id: UUID,
) -> TutorInterventionResponse:
    """Return one scoped intervention or a controlled 404."""

    try:
        intervention = repository.get_cohort_intervention(
            access.organization_id,
            course_id,
            cohort_id,
            blocker_id,
            intervention_id,
        )
    except SQLAlchemyError as exc:
        raise _service_unavailable(exc) from exc

    if intervention is None:
        raise _intervention_not_found()

    return intervention


def _validate_assignment(
    access: OrganizationAccess,
    course_id: UUID,
    cohort_id: UUID,
    payload: BlockerUpdate,
) -> None:
    """Ensure a requested assignee is an active cohort tutor."""

    if (
        "assigned_tutor_id" not in payload.model_fields_set
        or payload.assigned_tutor_id is None
    ):
        return

    try:
        is_active_tutor = membership_repository.has_active_cohort_role(
            access.organization_id,
            course_id,
            cohort_id,
            payload.assigned_tutor_id,
            CohortRole.TUTOR,
        )
    except SQLAlchemyError as exc:
        raise _service_unavailable(exc) from exc

    if not is_active_tutor:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Assigned tutor must be active in this cohort.",
        )


def _validate_blocker_update(
    blocker: BlockerDetailResponse,
    payload: BlockerUpdate,
) -> None:
    """Validate workflow transitions and resulting blocker state."""

    fields = payload.model_fields_set

    if blocker.status is BlockerStatus.CLOSED and fields != {"comment"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Closed blockers can only receive comments.",
        )

    if "status" in fields and payload.status is not None:
        if payload.status is blocker.status:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Blocker already has the requested status.",
            )

        if payload.status not in _ALLOWED_TRANSITIONS[blocker.status]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Blocker cannot move from {blocker.status.value} "
                    f"to {payload.status.value}."
                ),
            )

    resulting_status = (
        payload.status
        if "status" in fields and payload.status is not None
        else blocker.status
    )
    resulting_tutor_id = (
        payload.assigned_tutor_id
        if "assigned_tutor_id" in fields
        else blocker.assigned_tutor_id
    )
    resulting_summary = (
        payload.resolution_summary
        if "resolution_summary" in fields
        else blocker.resolution_summary
    )

    if (
        resulting_status
        in {
            BlockerStatus.ASSIGNED,
            BlockerStatus.WAITING_STUDENT,
        }
        and resulting_tutor_id is None
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Assigned and waiting blockers require an assigned tutor.",
        )

    if (
        resulting_status
        in {
            BlockerStatus.RESOLVED,
            BlockerStatus.CLOSED,
        }
        and resulting_summary is None
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Resolved and closed blockers require a resolution summary.",
        )

    if (
        resulting_status
        not in {
            BlockerStatus.RESOLVED,
            BlockerStatus.CLOSED,
        }
        and "resolution_summary" in fields
        and payload.resolution_summary is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "A resolution summary can only be stored for "
                "resolved or closed blockers."
            ),
        )


def _require_active_intervention_tutor(
    access: OrganizationAccess,
    course_id: UUID,
    cohort_id: UUID,
) -> None:
    """Require the actor to hold the cohort tutor role."""

    try:
        is_active_tutor = membership_repository.has_active_cohort_role(
            access.organization_id,
            course_id,
            cohort_id,
            access.user.user_id,
            CohortRole.TUTOR,
        )
    except SQLAlchemyError as exc:
        raise _service_unavailable(exc) from exc

    if not is_active_tutor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an active cohort tutor can create interventions.",
        )


@router.get(
    "/my-blockers",
    response_model=PaginatedResponse[BlockerResponse],
)
def list_my_blockers(
    access: LearnerRoleAccess,
    status_filter: Annotated[
        BlockerStatus | None,
        Query(alias="status"),
    ] = None,
    severity_filter: Annotated[
        BlockerSeverity | None,
        Query(alias="severity"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedResponse[BlockerResponse]:
    """List only the authenticated learner's blockers."""

    try:
        blockers, total = repository.list_my_blockers(
            access.organization_id,
            access.user.user_id,
            status_filter=status_filter,
            severity_filter=severity_filter,
            limit=limit,
            offset=offset,
        )
    except SQLAlchemyError as exc:
        raise _service_unavailable(exc) from exc

    return PaginatedResponse[BlockerResponse](
        items=blockers,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/my-blockers/{blocker_id}",
    response_model=BlockerDetailResponse,
)
def get_my_blocker(
    blocker_id: UUID,
    access: LearnerRoleAccess,
) -> BlockerDetailResponse:
    """Return one blocker owned by the authenticated learner."""

    try:
        blocker = repository.get_my_blocker(
            access.organization_id,
            access.user.user_id,
            blocker_id,
        )
    except SQLAlchemyError as exc:
        raise _service_unavailable(exc) from exc

    if blocker is None:
        raise _blocker_not_found()

    return blocker


@router.post(
    "/courses/{course_id}/cohorts/{cohort_id}/my-blockers",
    response_model=BlockerDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_my_blocker(
    course_id: UUID,
    cohort_id: UUID,
    payload: BlockerCreate,
    access: LearnerCohortAccess,
) -> BlockerDetailResponse:
    """Create a blocker for the authenticated cohort learner."""

    try:
        blocker = repository.create_my_blocker(
            access.organization_id,
            course_id,
            cohort_id,
            access.user.user_id,
            payload,
        )
    except SQLAlchemyError as exc:
        raise _service_unavailable(exc) from exc

    if blocker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active learner, cohort or topic was not found.",
        )

    return blocker


@router.get(
    "/courses/{course_id}/cohorts/{cohort_id}/blockers",
    response_model=PaginatedResponse[BlockerResponse],
)
def list_cohort_blockers(
    course_id: UUID,
    cohort_id: UUID,
    access: StaffAccess,
    status_filter: Annotated[
        BlockerStatus | None,
        Query(alias="status"),
    ] = None,
    severity_filter: Annotated[
        BlockerSeverity | None,
        Query(alias="severity"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedResponse[BlockerResponse]:
    """List cohort blockers for an administrator or assigned tutor."""

    try:
        blockers, total = repository.list_cohort_blockers(
            access.organization_id,
            course_id,
            cohort_id,
            status_filter=status_filter,
            severity_filter=severity_filter,
            limit=limit,
            offset=offset,
        )
    except SQLAlchemyError as exc:
        raise _service_unavailable(exc) from exc

    return PaginatedResponse[BlockerResponse](
        items=blockers,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/courses/{course_id}/cohorts/{cohort_id}/blockers/{blocker_id}",
    response_model=BlockerDetailResponse,
)
def get_cohort_blocker(
    course_id: UUID,
    cohort_id: UUID,
    blocker_id: UUID,
    access: StaffAccess,
) -> BlockerDetailResponse:
    """Return one cohort blocker with its complete history."""

    return _get_cohort_blocker(
        access,
        course_id,
        cohort_id,
        blocker_id,
    )


@router.put(
    "/courses/{course_id}/cohorts/{cohort_id}/blockers/{blocker_id}",
    response_model=BlockerDetailResponse,
)
def update_cohort_blocker(
    course_id: UUID,
    cohort_id: UUID,
    blocker_id: UUID,
    payload: BlockerUpdate,
    access: StaffAccess,
) -> BlockerDetailResponse:
    """Update a blocker and append an auditable event."""

    blocker = _get_cohort_blocker(
        access,
        course_id,
        cohort_id,
        blocker_id,
    )
    _validate_blocker_update(blocker, payload)
    _validate_assignment(
        access,
        course_id,
        cohort_id,
        payload,
    )

    try:
        updated = repository.update_cohort_blocker(
            access.organization_id,
            course_id,
            cohort_id,
            blocker_id,
            access.user.user_id,
            payload,
        )
    except SQLAlchemyError as exc:
        raise _service_unavailable(exc) from exc

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Blocker could not be updated because its state "
                "or assignment changed."
            ),
        )

    return updated


@router.post(
    (
        "/courses/{course_id}/cohorts/{cohort_id}"
        "/blockers/{blocker_id}/interventions"
    ),
    response_model=TutorInterventionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_blocker_intervention(
    course_id: UUID,
    cohort_id: UUID,
    blocker_id: UUID,
    payload: InterventionCreate,
    access: StaffAccess,
) -> TutorInterventionResponse:
    """Create an intervention for an active blocker."""

    blocker = _get_cohort_blocker(
        access,
        course_id,
        cohort_id,
        blocker_id,
    )
    _require_active_intervention_tutor(
        access,
        course_id,
        cohort_id,
    )

    if blocker.status in {
        BlockerStatus.RESOLVED,
        BlockerStatus.CLOSED,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Interventions can only be created for active blockers."
            ),
        )

    try:
        intervention = repository.create_blocker_intervention(
            access.organization_id,
            course_id,
            cohort_id,
            blocker_id,
            access.user.user_id,
            payload,
        )
    except SQLAlchemyError as exc:
        raise _service_unavailable(exc) from exc

    if intervention is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The blocker is no longer available for intervention.",
        )

    return intervention


@router.put(
    (
        "/courses/{course_id}/cohorts/{cohort_id}"
        "/blockers/{blocker_id}/interventions/{intervention_id}"
    ),
    response_model=TutorInterventionResponse,
)
def complete_blocker_intervention(
    course_id: UUID,
    cohort_id: UUID,
    blocker_id: UUID,
    intervention_id: UUID,
    payload: InterventionCompletion,
    access: StaffAccess,
) -> TutorInterventionResponse:
    """Complete one pending tutor intervention."""

    intervention = _get_intervention(
        access,
        course_id,
        cohort_id,
        blocker_id,
        intervention_id,
    )

    if (
        MembershipRole.ADMIN not in access.roles
        and intervention.tutor_id != access.user.user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tutors can complete only their own interventions.",
        )

    if (
        intervention.outcome is not InterventionOutcome.PENDING
        or intervention.completed_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tutor intervention is already completed.",
        )

    try:
        completed = repository.complete_blocker_intervention(
            access.organization_id,
            course_id,
            cohort_id,
            blocker_id,
            intervention_id,
            access.user.user_id,
            payload,
        )
    except SQLAlchemyError as exc:
        raise _service_unavailable(exc) from exc

    if completed is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tutor intervention is no longer pending.",
        )

    return completed
