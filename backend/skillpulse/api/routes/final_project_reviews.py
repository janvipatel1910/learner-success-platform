"""Assigned-tutor final project review routes."""

import logging
from contextlib import contextmanager
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from skillpulse.api.dependencies.auth import (
    OrganizationAccess,
    require_organization_roles,
)
from skillpulse.db import final_project_reviews as repository
from skillpulse.db.identity import MembershipRole
from skillpulse.schemas.catalog import PaginatedResponse
from skillpulse.schemas.final_project_reviews import (
    TutorProjectReview,
    TutorProjectSubmissionResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/catalog",
    tags=["final project reviews"],
)

_require_tutor = require_organization_roles(MembershipRole.TUTOR)

TutorAccess = Annotated[
    OrganizationAccess,
    Depends(_require_tutor),
]


@contextmanager
def _controlled_errors():
    try:
        yield
    except repository.TutorAccessDenied as exc:
        raise HTTPException(
            status_code=403,
            detail="An active assigned cohort tutor is required.",
        ) from exc
    except repository.SubmissionNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail="Project submission was not found.",
        ) from exc
    except repository.ReviewConflict as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc
    except repository.InvalidReview as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except SQLAlchemyError as exc:
        logger.warning(
            "Final project review operation failed: %s",
            exc.__class__.__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="Final project review service is unavailable.",
        ) from exc


@router.get(
    (
        "/courses/{course_id}/cohorts/{cohort_id}"
        "/final-project/submissions"
    ),
    response_model=PaginatedResponse[TutorProjectSubmissionResponse],
)
def list_final_project_submissions(
    course_id: UUID,
    cohort_id: UUID,
    access: TutorAccess,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """List submissions for an active assigned tutor."""
    with _controlled_errors():
        items, total = repository.list_project_submissions(
            organization_id=access.organization_id,
            course_id=course_id,
            cohort_id=cohort_id,
            tutor_id=access.user.user_id,
            limit=limit,
            offset=offset,
        )

        return PaginatedResponse[TutorProjectSubmissionResponse](
            items=items,
            total=total,
            limit=limit,
            offset=offset,
        )


@router.put(
    (
        "/courses/{course_id}/cohorts/{cohort_id}"
        "/final-project/submissions/{submission_id}/review"
    ),
    response_model=TutorProjectSubmissionResponse,
)
def review_final_project_submission(
    course_id: UUID,
    cohort_id: UUID,
    submission_id: UUID,
    payload: TutorProjectReview,
    access: TutorAccess,
):
    """Record tutor feedback and a permitted review transition."""
    with _controlled_errors():
        return repository.review_project_submission(
            organization_id=access.organization_id,
            course_id=course_id,
            cohort_id=cohort_id,
            tutor_id=access.user.user_id,
            submission_id=submission_id,
            expected_review_status=payload.expected_review_status,
            review_status=payload.review_status,
            score=payload.score,
            tutor_feedback=payload.tutor_feedback,
        )
