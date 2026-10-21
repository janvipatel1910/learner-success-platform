"""Authenticated learner practice quiz and mock exam routes."""

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
from skillpulse.core.assessment_grading import InvalidAnswers, InvalidAssessment
from skillpulse.db import practice_assessments as repository
from skillpulse.db.identity import MembershipRole
from skillpulse.schemas.practice_assessments import (
    PracticeAssessmentSummary,
    PracticeAttempt,
    PracticeResult,
    PracticeSubmission,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/catalog",
    tags=["practice assessments"],
)

LearnerAccess = Annotated[
    OrganizationAccess,
    Depends(require_organization_roles(MembershipRole.STUDENT)),
]

_BASE = "/courses/{course_id}/cohorts/{cohort_id}/practice-assessments"


@contextmanager
def _controlled_errors():
    try:
        yield
    except repository.PracticeAccessDenied as exc:
        raise HTTPException(
            status_code=403,
            detail="Student is not an active learner in this cohort.",
        ) from exc
    except repository.PracticeNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail="Practice assessment or attempt was not found.",
        ) from exc
    except repository.PracticeConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidAnswers as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (InvalidAssessment, SQLAlchemyError) as exc:
        logger.warning(
            "Practice assessment operation failed: %s",
            exc.__class__.__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="Practice assessment service is unavailable.",
        ) from exc


@router.get(_BASE, response_model=list[PracticeAssessmentSummary])
def list_my_practice_assessments(
    course_id: UUID,
    cohort_id: UUID,
    access: LearnerAccess,
):
    """List practice quizzes and mock exams with this learner's progress."""
    with _controlled_errors():
        return repository.list_practice_assessments(
            organization_id=access.organization_id,
            course_id=course_id,
            cohort_id=cohort_id,
            learner_id=access.user.user_id,
        )


@router.post(f"{_BASE}/{{assessment_id}}/attempts", response_model=PracticeAttempt)
def start_my_practice_attempt(
    course_id: UUID,
    cohort_id: UUID,
    assessment_id: UUID,
    access: LearnerAccess,
):
    """Start an attempt, or resume the open one. Answer keys are never sent."""
    with _controlled_errors():
        return repository.start_attempt(
            organization_id=access.organization_id,
            course_id=course_id,
            cohort_id=cohort_id,
            learner_id=access.user.user_id,
            assessment_id=assessment_id,
        )


@router.post(
    f"{_BASE}/{{assessment_id}}/attempts/{{attempt_id}}/submit",
    response_model=PracticeResult,
)
def submit_my_practice_attempt(
    course_id: UUID,
    cohort_id: UUID,
    assessment_id: UUID,
    attempt_id: UUID,
    payload: PracticeSubmission,
    access: LearnerAccess,
):
    """Grade the attempt on the server and return a full review."""
    with _controlled_errors():
        return repository.submit_attempt(
            organization_id=access.organization_id,
            course_id=course_id,
            cohort_id=cohort_id,
            learner_id=access.user.user_id,
            assessment_id=assessment_id,
            attempt_id=attempt_id,
            answers={
                str(question_id): selected
                for question_id, selected in payload.answers.items()
            },
        )


@router.get(
    f"{_BASE}/{{assessment_id}}/attempts/{{attempt_id}}",
    response_model=PracticeResult,
)
def review_my_practice_attempt(
    course_id: UUID,
    cohort_id: UUID,
    assessment_id: UUID,
    attempt_id: UUID,
    access: LearnerAccess,
):
    """Return the marked review of a submitted attempt."""
    with _controlled_errors():
        return repository.get_attempt_review(
            organization_id=access.organization_id,
            course_id=course_id,
            cohort_id=cohort_id,
            learner_id=access.user.user_id,
            assessment_id=assessment_id,
            attempt_id=attempt_id,
        )
