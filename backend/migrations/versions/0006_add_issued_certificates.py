"""Add issued certificate records.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the issued certificate registry."""
    op.create_table(
        "issued_certificates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "eligibility_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "certificate_eligibility.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "certificate_number",
            sa.String(length=40),
            nullable=False,
        ),
        sa.Column(
            "learner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "cohort_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cohorts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "course_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("courses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("learner_name", sa.String(length=200), nullable=False),
        sa.Column("course_title", sa.String(length=200), nullable=False),
        sa.Column(
            "certification_name",
            sa.String(length=150),
            nullable=False,
        ),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "eligibility_id",
            name="uq_issued_certificate_eligibility",
        ),
        sa.UniqueConstraint(
            "certificate_number",
            name="uq_issued_certificate_number",
        ),
        sa.UniqueConstraint(
            "learner_id",
            "cohort_id",
            "course_id",
            name="uq_issued_certificate_learner_course",
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= issued_at",
            name="ck_issued_certificate_revocation_date",
        ),
    )

    op.create_index(
        "ix_issued_certificates_learner_cohort",
        "issued_certificates",
        ["learner_id", "cohort_id"],
    )


def downgrade() -> None:
    """Remove the issued certificate registry."""
    op.drop_index(
        "ix_issued_certificates_learner_cohort",
        table_name="issued_certificates",
    )
    op.drop_table("issued_certificates")
