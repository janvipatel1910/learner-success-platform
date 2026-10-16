"""Schemas for issued certificate and public verification responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class IssuedCertificateResponse(BaseModel):
    id: UUID
    eligibility_id: UUID
    certificate_number: str
    learner_id: UUID
    cohort_id: UUID
    course_id: UUID
    learner_name: str
    course_title: str
    certification_name: str
    issued_at: datetime
    revoked_at: datetime | None
    is_valid: bool
    verification_path: str


class CertificateVerificationResponse(BaseModel):
    certificate_number: str
    learner_name: str
    course_title: str
    certification_name: str
    issued_at: datetime
    revoked_at: datetime | None
    is_valid: bool
