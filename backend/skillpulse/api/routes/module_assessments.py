"""Authenticated learner module assessment routes."""

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
from skillpulse.core.module_assessment import (
    InvalidAnswers,
    InvalidAssessment,
)
from skillpulse.db import module_assessments as repository
from skillpulse.db.identity import MembershipRole
from skillpulse.db.module_progress import (
    ModuleAccessDenied,
    ModuleLocked,
    ModuleNotFound,
)
from skillpulse.schemas.module_assessments import (
    ModuleCheckResponse,
    ModuleCheckResult,
    ModuleCheckSubmission,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/catalog",
    tags=["module assessments"],
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
    except ModuleNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail="Module was not found in this course.",
        ) from exc
    except ModuleLocked as exc:
        raise HTTPException(
            status_code=409,
            detail="Complete all earlier modules first.",
        ) from exc
    except repository.CheckUnavailable as exc:
        raise HTTPException(
            status_code=404,
            detail="No published check is available for this module.",
        ) from exc
    except repository.CheckConflict as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc
    except InvalidAnswers as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except (InvalidAssessment, SQLAlchemyError) as exc:
        logger.warning(
            "Module assessment operation failed: %s",
            exc.__class__.__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="Module assessment service is unavailable.",
        ) from exc


@router.get(
    (
        "/courses/{course_id}/cohorts/{cohort_id}"
        "/my-modules/{topic_id}/check"
    ),
    response_model=ModuleCheckResponse,
)
def get_my_module_check(
    course_id: UUID,
    cohort_id: UUID,
    topic_id: UUID,
    access: LearnerAccess,
):
    """Return questions without answer keys."""
    with _controlled_errors():
        return repository.get_module_check(
            organization_id=access.organization_id,
            course_id=course_id,
            cohort_id=cohort_id,
            learner_id=access.user.user_id,
            topic_id=topic_id,
        )


@router.post(
    (
        "/courses/{course_id}/cohorts/{cohort_id}"
        "/my-modules/{topic_id}/check/attempts"
    ),
    response_model=ModuleCheckResult,
)
def submit_my_module_check(
    course_id: UUID,
    cohort_id: UUID,
    topic_id: UUID,
    payload: ModuleCheckSubmission,
    access: LearnerAccess,
):
    """Grade an attempt and complete a passed module atomically."""
    with _controlled_errors():
        return repository.submit_module_check(
            organization_id=access.organization_id,
            course_id=course_id,
            cohort_id=cohort_id,
            learner_id=access.user.user_id,
            topic_id=topic_id,
            attempt_id=payload.attempt_id,
            version=payload.version,
            answers={
                str(question_id): selected
                for question_id, selected in payload.answers.items()
            },
        )
