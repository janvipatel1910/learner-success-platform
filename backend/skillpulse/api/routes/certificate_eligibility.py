"""Learner certificate eligibility route."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from skillpulse.api.dependencies.auth import (
    OrganizationAccess,
    require_organization_roles,
)
from skillpulse.db import certificate_eligibility as repository
from skillpulse.db.identity import MembershipRole
from skillpulse.schemas.certificate_eligibility import (
    CertificateEligibilityResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/catalog",
    tags=["certificate eligibility"],
)

_require_learner = require_organization_roles(MembershipRole.STUDENT)

LearnerAccess = Annotated[
    OrganizationAccess,
    Depends(_require_learner),
]


@router.post(
    (
        "/courses/{course_id}/cohorts/{cohort_id}"
        "/certificate-eligibility/me/evaluate"
    ),
    response_model=CertificateEligibilityResponse,
    status_code=status.HTTP_201_CREATED,
)
def evaluate_my_certificate_eligibility(
    course_id: UUID,
    cohort_id: UUID,
    access: LearnerAccess,
) -> CertificateEligibilityResponse:
    """Evaluate and save the authenticated learner's certificate status."""
    try:
        result = repository.evaluate_certificate_eligibility(
            access.organization_id,
            course_id,
            cohort_id,
            access.user.user_id,
        )
    except repository.CertificateAccessDenied as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Learner is not active in this course cohort.",
        ) from exc
    except SQLAlchemyError as exc:
        logger.warning(
            "Certificate eligibility operation failed: %s",
            exc.__class__.__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Certificate eligibility service is unavailable.",
        ) from exc

    return CertificateEligibilityResponse.model_validate(result)
