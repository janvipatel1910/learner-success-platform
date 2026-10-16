"""Learner certificate issuance and public verification routes."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from skillpulse.api.dependencies.auth import (
    OrganizationAccess,
    require_organization_roles,
)
from skillpulse.db import issued_certificates as repository
from skillpulse.db.identity import MembershipRole
from skillpulse.schemas.issued_certificates import (
    CertificateVerificationResponse,
    IssuedCertificateResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/catalog",
    tags=["certificates"],
)

_require_learner = require_organization_roles(MembershipRole.STUDENT)

LearnerAccess = Annotated[
    OrganizationAccess,
    Depends(_require_learner),
]


@router.post(
    "/courses/{course_id}/cohorts/{cohort_id}/certificates/me/issue",
    response_model=IssuedCertificateResponse,
)
def issue_my_certificate(
    course_id: UUID,
    cohort_id: UUID,
    access: LearnerAccess,
) -> IssuedCertificateResponse:
    """Issue or return the active learner's eligible certificate."""
    try:
        result = repository.issue_certificate(
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
    except repository.CertificateNotEligible as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Certificate requirements are not met. "
                "Complete all requirements and check eligibility again."
            ),
        ) from exc
    except SQLAlchemyError as exc:
        logger.warning(
            "Certificate issuance failed: %s",
            exc.__class__.__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Certificate service is unavailable.",
        ) from exc

    certificate_number = str(result["certificate_number"])
    return IssuedCertificateResponse.model_validate({
        **result,
        "is_valid": result["revoked_at"] is None,
        "verification_path": (
            f"/api/v1/catalog/certificates/"
            f"{certificate_number}/verify"
        ),
    })


@router.get(
    "/certificates/{certificate_number}/verify",
    response_model=CertificateVerificationResponse,
)
def verify_certificate(
    certificate_number: str,
) -> CertificateVerificationResponse:
    """Publicly verify a certificate without exposing learner contact data."""
    try:
        result = repository.verify_certificate(certificate_number)
    except SQLAlchemyError as exc:
        logger.warning(
            "Certificate verification failed: %s",
            exc.__class__.__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Certificate verification is unavailable.",
        ) from exc

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate was not found.",
        )

    return CertificateVerificationResponse.model_validate(result)
