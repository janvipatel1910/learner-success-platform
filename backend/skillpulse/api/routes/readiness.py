"""Organisation-scoped learner readiness endpoints."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from skillpulse.api.dependencies.auth import (
    OrganizationAccess,
    require_organization_roles,
)
from skillpulse.core.readiness import calculate_readiness
from skillpulse.db import cohort_memberships as membership_repository
from skillpulse.db import readiness as readiness_repository
from skillpulse.db.identity import MembershipRole
from skillpulse.schemas.enrollment import CohortRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/catalog", tags=["readiness"])

_require_staff_role = require_organization_roles(
    MembershipRole.TUTOR,
    MembershipRole.ADMIN,
)
_require_student_role = require_organization_roles(
    MembershipRole.STUDENT,
)

StaffAccess = Annotated[
    OrganizationAccess, Depends(_require_staff_role)
]
StudentAccess = Annotated[
    OrganizationAccess, Depends(_require_student_role)
]


def _service_unavailable(exc: Exception) -> HTTPException:
    logger.warning(
        "Readiness operation failed: %s",
        exc.__class__.__name__,
    )
    return HTTPException(
        status_code=503,
        detail="Readiness service is unavailable.",
    )


def _require_cohort_role(
    access: OrganizationAccess,
    course_id: UUID,
    cohort_id: UUID,
    role: CohortRole,
) -> None:
    try:
        allowed = membership_repository.has_active_cohort_role(
            access.organization_id,
            course_id,
            cohort_id,
            access.user.user_id,
            role,
        )
    except SQLAlchemyError as exc:
        raise _service_unavailable(exc) from exc

    if not allowed:
        raise HTTPException(
            status_code=403,
            detail="Required active cohort membership was not found.",
        )


def _calculate_learner_readiness(
    access: OrganizationAccess,
    course_id: UUID,
    cohort_id: UUID,
    learner_id: UUID,
) -> dict[str, object]:
    try:
        inputs = readiness_repository.get_readiness_inputs(
            access.organization_id,
            course_id,
            cohort_id,
            learner_id,
        )
    except SQLAlchemyError as exc:
        raise _service_unavailable(exc) from exc

    if inputs is None:
        raise HTTPException(
            status_code=404,
            detail="Active learner or readiness model was not found.",
        )

    column_mapping = {
        "quiz": "quiz_component",
        "mock": "mock_component",
        "lab": "lab_component",
        "attendance": "attendance_component",
        "blockers": "blocker_component",
    }

    try:
        components = {
            name: float(inputs[column])
            for name, column in column_mapping.items()
        }
        weights = {
            name: float(value)
            for name, value in inputs["component_weights_json"].items()
        }
        thresholds = {
            name: float(inputs[name])
            for name in (
                "readiness_threshold",
                "minimum_mock_score",
                "minimum_lab_completion",
            )
        }
        result = calculate_readiness(
            components=components,
            weights=weights,
            **thresholds,
        )
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise _service_unavailable(exc) from exc

    return {
        "organization_id": access.organization_id,
        "course_id": course_id,
        "cohort_id": cohort_id,
        "learner_id": learner_id,
        "readiness_model_id": inputs["readiness_model_id"],
        "thresholds": thresholds,
        **result,
    }


@router.get(
    "/courses/{course_id}/cohorts/{cohort_id}/readiness/me"
)
def get_my_readiness(
    course_id: UUID,
    cohort_id: UUID,
    access: StudentAccess,
) -> dict[str, object]:
    _require_cohort_role(
        access, course_id, cohort_id, CohortRole.LEARNER
    )
    return _calculate_learner_readiness(
        access, course_id, cohort_id, access.user.user_id
    )


@router.get(
    "/courses/{course_id}/cohorts/{cohort_id}"
    "/learners/{learner_id}/readiness"
)
def get_learner_readiness(
    course_id: UUID,
    cohort_id: UUID,
    learner_id: UUID,
    access: StaffAccess,
) -> dict[str, object]:
    if MembershipRole.ADMIN not in access.roles:
        _require_cohort_role(
            access, course_id, cohort_id, CohortRole.TUTOR
        )

    return _calculate_learner_readiness(
        access, course_id, cohort_id, learner_id
    )


@router.post(
    "/courses/{course_id}/cohorts/{cohort_id}"
    "/learners/{learner_id}/readiness/snapshots",
    status_code=201,
)
def create_learner_readiness_snapshot(
    course_id: UUID,
    cohort_id: UUID,
    learner_id: UUID,
    access: StaffAccess,
) -> dict[str, object]:
    if MembershipRole.ADMIN not in access.roles:
        _require_cohort_role(
            access, course_id, cohort_id, CohortRole.TUTOR
        )

    try:
        snapshot = readiness_repository.create_readiness_snapshot(
            access.organization_id,
            course_id,
            cohort_id,
            learner_id,
        )
    except SQLAlchemyError as exc:
        raise _service_unavailable(exc) from exc
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise _service_unavailable(exc) from exc

    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="Active learner or readiness model was not found.",
        )

    return dict(snapshot)

def _read_snapshot_history(
    access: OrganizationAccess,
    course_id: UUID,
    cohort_id: UUID,
    learner_id: UUID,
    limit: int,
    offset: int,
) -> list[dict[str, object]]:
    try:
        snapshots = readiness_repository.list_readiness_snapshots(
            access.organization_id,
            course_id,
            cohort_id,
            learner_id,
            limit=limit,
            offset=offset,
        )
    except SQLAlchemyError as exc:
        raise _service_unavailable(exc) from exc

    return [dict(snapshot) for snapshot in snapshots]


@router.get(
    "/courses/{course_id}/cohorts/{cohort_id}"
    "/readiness/me/snapshots"
)
def get_my_readiness_history(
    course_id: UUID,
    cohort_id: UUID,
    access: StudentAccess,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict[str, object]]:
    _require_cohort_role(
        access, course_id, cohort_id, CohortRole.LEARNER
    )

    return _read_snapshot_history(
        access,
        course_id,
        cohort_id,
        access.user.user_id,
        limit,
        offset,
    )


@router.get(
    "/courses/{course_id}/cohorts/{cohort_id}"
    "/learners/{learner_id}/readiness/snapshots"
)
def get_learner_readiness_history(
    course_id: UUID,
    cohort_id: UUID,
    learner_id: UUID,
    access: StaffAccess,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict[str, object]]:
    if MembershipRole.ADMIN not in access.roles:
        _require_cohort_role(
            access, course_id, cohort_id, CohortRole.TUTOR
        )

    return _read_snapshot_history(
        access,
        course_id,
        cohort_id,
        learner_id,
        limit,
        offset,
    )
