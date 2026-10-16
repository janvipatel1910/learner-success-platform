"""Issue and verify learner certificates."""

from uuid import UUID, uuid4

from sqlalchemy import text

from skillpulse.db.connection import get_engine
from skillpulse.db.module_progress import _SCOPE_SQL


class CertificateAccessDenied(Exception):
    """The learner is not active in this course cohort."""


class CertificateNotEligible(Exception):
    """The learner's latest eligibility evaluation did not pass."""


_CERTIFICATE_COLUMNS = """
    id,
    certificate_number,
    eligibility_id,
    learner_id,
    cohort_id,
    course_id,
    learner_name,
    course_title,
    certification_name,
    issued_at,
    revoked_at
"""


def issue_certificate(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    learner_id: UUID,
) -> dict[str, object]:
    """Issue one certificate after checking current eligibility."""
    parameters = {
        "organization_id": organization_id,
        "course_id": course_id,
        "cohort_id": cohort_id,
        "learner_id": learner_id,
    }

    with get_engine().begin() as connection:
        active_member = connection.execute(
            text(_SCOPE_SQL),
            parameters,
        ).scalar_one_or_none()

        if active_member is None:
            raise CertificateAccessDenied()

        existing = connection.execute(
            text(f"""
                SELECT {_CERTIFICATE_COLUMNS}
                FROM issued_certificates
                WHERE learner_id = :learner_id
                  AND cohort_id = :cohort_id
                  AND course_id = :course_id
            """),
            parameters,
        ).mappings().one_or_none()

        if existing is not None:
            return dict(existing)

        eligibility = connection.execute(
            text("""
                SELECT
                    ce.id AS eligibility_id,
                    ce.is_eligible,
                    u.full_name AS learner_name,
                    c.title AS course_title,
                    COALESCE(
                        NULLIF(c.certification_name, ''),
                        c.title
                    ) AS certification_name
                FROM certificate_eligibility AS ce
                JOIN cohorts AS h
                  ON h.id = ce.cohort_id
                 AND h.course_id = :course_id
                JOIN courses AS c
                  ON c.id = h.course_id
                 AND c.organization_id = :organization_id
                JOIN users AS u
                  ON u.id = ce.learner_id
                WHERE ce.learner_id = :learner_id
                  AND ce.cohort_id = :cohort_id
                ORDER BY ce.evaluated_at DESC, ce.id DESC
                LIMIT 1
                FOR UPDATE OF ce
            """),
            parameters,
        ).mappings().one_or_none()

        if eligibility is None or not eligibility["is_eligible"]:
            raise CertificateNotEligible()

        certificate_number = f"SP-{uuid4().hex[:24].upper()}"
        insert_parameters = {
            **parameters,
            "eligibility_id": eligibility["eligibility_id"],
            "certificate_number": certificate_number,
            "learner_name": eligibility["learner_name"],
            "course_title": eligibility["course_title"],
            "certification_name": eligibility["certification_name"],
        }

        issued = connection.execute(
            text(f"""
                INSERT INTO issued_certificates (
                    eligibility_id,
                    certificate_number,
                    learner_id,
                    cohort_id,
                    course_id,
                    learner_name,
                    course_title,
                    certification_name
                )
                VALUES (
                    :eligibility_id,
                    :certificate_number,
                    :learner_id,
                    :cohort_id,
                    :course_id,
                    :learner_name,
                    :course_title,
                    :certification_name
                )
                ON CONFLICT (learner_id, cohort_id, course_id)
                DO NOTHING
                RETURNING {_CERTIFICATE_COLUMNS}
            """),
            insert_parameters,
        ).mappings().one_or_none()

        if issued is not None:
            return dict(issued)

        # Another request may have issued it at the same time.
        existing = connection.execute(
            text(f"""
                SELECT {_CERTIFICATE_COLUMNS}
                FROM issued_certificates
                WHERE learner_id = :learner_id
                  AND cohort_id = :cohort_id
                  AND course_id = :course_id
            """),
            parameters,
        ).mappings().one()

        return dict(existing)


def verify_certificate(
    certificate_number: str,
) -> dict[str, object] | None:
    """Return the public verification details for a certificate number."""
    with get_engine().connect() as connection:
        row = connection.execute(
            text("""
                SELECT
                    certificate_number,
                    learner_name,
                    course_title,
                    certification_name,
                    issued_at,
                    revoked_at
                FROM issued_certificates
                WHERE certificate_number = :certificate_number
            """),
            {"certificate_number": certificate_number},
        ).mappings().one_or_none()

    if row is None:
        return None

    result = dict(row)
    result["is_valid"] = result["revoked_at"] is None
    return result
