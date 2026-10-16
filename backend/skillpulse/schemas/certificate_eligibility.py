"""Certificate eligibility response schema."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CertificateEligibilityResponse(BaseModel):
    id: UUID
    learner_id: UUID
    cohort_id: UUID
    attendance_met: bool
    assignment_met: bool
    lab_met: bool
    mock_score_met: bool
    blockers_cleared: bool
    module_checks_met: bool
    final_project_met: bool
    is_eligible: bool
    missing_requirements_json: list[str]
    evaluated_at: datetime
