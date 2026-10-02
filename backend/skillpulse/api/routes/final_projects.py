"""Authenticated learner final project routes."""

import logging
from contextlib import contextmanager
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from skillpulse.api.dependencies.auth import (
    OrganizationAccess,
    require_organization_roles,
)
from skillpulse.db import final_projects as repository
from skillpulse.db.identity import MembershipRole
from skillpulse.db.module_progress import ModuleAccessDenied
from skillpulse.schemas.final_projects import (
    FinalProjectResponse,
    FinalProjectSubmissionCreate,
    FinalProjectSubmissionResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/catalog",
    tags=["final projects"],
)

_require_learner = require_organization_roles(MembershipRole.STUDENT)

LearnerAccess = Annotated[
    OrganizationAccess,
    Depends(_require_learner),
]


@contextmanager
def _controlled_errors():
    try:
        yield
    except ModuleAccessDenied as exc:
        raise HTTPException(
            status_code=403,
            detail="Student is not an active learner in this cohort.",
        ) from exc
    except repository.FinalProjectNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail="No published final project is available for this course.",
        ) from exc
    except repository.FinalProjectConflict as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc
    except SQLAlchemyError as exc:
        logger.warning(
            "Final project database operation failed: %s",
            exc.__class__.__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="Final project service is unavailable.",
        ) from exc


@router.get(
    "/courses/{course_id}/cohorts/{cohort_id}/my-final-project",
    response_model=FinalProjectResponse,
)
def get_my_final_project(
    course_id: UUID,
    cohort_id: UUID,
    access: LearnerAccess,
):
    """Return the project and this learner's latest submission."""
    with _controlled_errors():
        return repository.get_learner_final_project(
            organization_id=access.organization_id,
            course_id=course_id,
            cohort_id=cohort_id,
            learner_id=access.user.user_id,
        )


@router.post(
    (
        "/courses/{course_id}/cohorts/{cohort_id}"
        "/my-final-project/submissions"
    ),
    response_model=FinalProjectSubmissionResponse,
)
def submit_my_final_project(
    course_id: UUID,
    cohort_id: UUID,
    payload: FinalProjectSubmissionCreate,
    access: LearnerAccess,
):
    """Save a project submission for the authenticated learner."""
    with _controlled_errors():
        return repository.submit_learner_final_project(
            organization_id=access.organization_id,
            course_id=course_id,
            cohort_id=cohort_id,
            learner_id=access.user.user_id,
            submission_id=payload.submission_id,
            submission_url=str(payload.submission_url),
            note=payload.note,
        )
