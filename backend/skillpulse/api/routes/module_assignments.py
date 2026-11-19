"""Module assignment routes for learners and their cohort tutors."""

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
from skillpulse.db import module_assignments as repository
from skillpulse.db.identity import MembershipRole
from skillpulse.schemas.catalog import PaginatedResponse
from skillpulse.schemas.module_assignments import (
    AssignmentReview,
    AssignmentReviewStatus,
    AssignmentSubmissionCreate,
    AssignmentSubmissionResponse,
    LearnerAssignmentResponse,
    TutorAssignmentSubmissionResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/catalog", tags=["module assignments"])

LearnerAccess = Annotated[
    OrganizationAccess,
    Depends(require_organization_roles(MembershipRole.STUDENT)),
]
TutorAccess = Annotated[
    OrganizationAccess,
    Depends(require_organization_roles(MembershipRole.TUTOR)),
]

_COHORT = "/courses/{course_id}/cohorts/{cohort_id}"


@contextmanager
def _controlled_errors():
    try:
        yield
    except repository.ModuleAccessDenied as exc:
        raise HTTPException(
            status_code=403,
            detail="Student is not an active learner in this cohort.",
        ) from exc
    except repository.TutorAccessDenied as exc:
        raise HTTPException(
            status_code=403,
            detail="An active assigned cohort tutor is required.",
        ) from exc
    except repository.AssignmentNotFound as exc:
        raise HTTPException(
            status_code=404, detail="Assignment was not found."
        ) from exc
    except repository.SubmissionNotFound as exc:
        raise HTTPException(
            status_code=404, detail="Assignment answer was not found."
        ) from exc
    except repository.AssignmentConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        logger.warning(
            "Assignment database operation failed: %s",
            exc.__class__.__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="Assignment service is unavailable.",
        ) from exc


@router.get(
    _COHORT + "/my-assignments",
    response_model=list[LearnerAssignmentResponse],
)
def list_my_assignments(
    course_id: UUID,
    cohort_id: UUID,
    access: LearnerAccess,
):
    """Return each module's assignment and this learner's latest answer."""
    with _controlled_errors():
        return repository.list_learner_assignments(
            organization_id=access.organization_id,
            course_id=course_id,
            cohort_id=cohort_id,
            learner_id=access.user.user_id,
        )


@router.post(
    _COHORT + "/my-assignments/{assignment_id}/submissions",
    response_model=AssignmentSubmissionResponse,
)
def submit_my_assignment(
    course_id: UUID,
    cohort_id: UUID,
    assignment_id: UUID,
    payload: AssignmentSubmissionCreate,
    access: LearnerAccess,
):
    """Save the learner's answer for tutor review."""
    with _controlled_errors():
        return repository.submit_assignment(
            organization_id=access.organization_id,
            course_id=course_id,
            cohort_id=cohort_id,
            learner_id=access.user.user_id,
            assignment_id=assignment_id,
            submission_id=payload.submission_id,
            answer_text=payload.answer_text,
            link_url=str(payload.link_url) if payload.link_url else None,
        )


@router.get(
    _COHORT + "/assignment-submissions",
    response_model=PaginatedResponse[TutorAssignmentSubmissionResponse],
)
def list_assignment_submissions(
    course_id: UUID,
    cohort_id: UUID,
    access: TutorAccess,
    review_status: AssignmentReviewStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """List the cohort's answers for its tutor, waiting ones first."""
    with _controlled_errors():
        items, total = repository.list_assignment_submissions(
            organization_id=access.organization_id,
            course_id=course_id,
            cohort_id=cohort_id,
            tutor_id=access.user.user_id,
            review_status=review_status,
            limit=limit,
            offset=offset,
        )
        return PaginatedResponse[TutorAssignmentSubmissionResponse](
            items=items, total=total, limit=limit, offset=offset
        )


@router.put(
    _COHORT + "/assignment-submissions/{submission_id}/review",
    response_model=TutorAssignmentSubmissionResponse,
)
def review_assignment_submission(
    course_id: UUID,
    cohort_id: UUID,
    submission_id: UUID,
    payload: AssignmentReview,
    access: TutorAccess,
):
    """Approve an answer or send it back with feedback."""
    with _controlled_errors():
        return repository.review_assignment_submission(
            organization_id=access.organization_id,
            course_id=course_id,
            cohort_id=cohort_id,
            tutor_id=access.user.user_id,
            submission_id=submission_id,
            review_status=payload.review_status,
            tutor_feedback=payload.tutor_feedback,
        )
