"""Authenticated learner module progression routes."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from skillpulse.api.dependencies.auth import (
    OrganizationAccess,
    require_organization_roles,
)
from skillpulse.db import module_progress as repository
from skillpulse.db.identity import MembershipRole
from skillpulse.schemas.module_progress import ModuleProgressResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/catalog",
    tags=["module progression"],
)

_require_learner = require_organization_roles(
    MembershipRole.STUDENT,
)

LearnerAccess = Annotated[
    OrganizationAccess,
    Depends(_require_learner),
]


def _database_error(exc: SQLAlchemyError) -> HTTPException:
    logger.warning(
        "Module progression database operation failed: %s",
        exc.__class__.__name__,
    )
    return HTTPException(
        status_code=503,
        detail="Module progression service is unavailable.",
    )


@router.get(
    "/courses/{course_id}/cohorts/{cohort_id}/my-modules",
    response_model=list[ModuleProgressResponse],
)
def list_my_modules(
    course_id: UUID,
    cohort_id: UUID,
    access: LearnerAccess,
) -> list[dict[str, object]]:
    """Return the authenticated learner's ordered modules."""
    try:
        return repository.list_learner_modules(
            organization_id=access.organization_id,
            course_id=course_id,
            cohort_id=cohort_id,
            learner_id=access.user.user_id,
        )
    except repository.ModuleAccessDenied as exc:
        raise HTTPException(
            status_code=403,
            detail="Student is not an active learner in this cohort.",
        ) from exc
    except SQLAlchemyError as exc:
        raise _database_error(exc) from exc


@router.post(
    (
        "/courses/{course_id}/cohorts/{cohort_id}"
        "/my-modules/{topic_id}/start"
    ),
    response_model=ModuleProgressResponse,
)
def start_my_module(
    course_id: UUID,
    cohort_id: UUID,
    topic_id: UUID,
    access: LearnerAccess,
) -> dict[str, object]:
    """Start an available module or return its existing progress."""
    try:
        return repository.start_learner_module(
            organization_id=access.organization_id,
            course_id=course_id,
            cohort_id=cohort_id,
            learner_id=access.user.user_id,
            topic_id=topic_id,
        )
    except repository.ModuleAccessDenied as exc:
        raise HTTPException(
            status_code=403,
            detail="Student is not an active learner in this cohort.",
        ) from exc
    except repository.ModuleNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail="Module was not found in this course.",
        ) from exc
    except repository.ModuleLocked as exc:
        raise HTTPException(
            status_code=409,
            detail="Complete all earlier modules before starting this one.",
        ) from exc
    except SQLAlchemyError as exc:
        raise _database_error(exc) from exc
