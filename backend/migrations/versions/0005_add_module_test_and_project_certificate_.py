"""Add module test and project certificate requirements.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Require passed module tests and a passing final project."""
    op.add_column(
        "course_final_projects",
        sa.Column(
            "minimum_passing_percentage",
            sa.Numeric(5, 2),
            nullable=False,
            server_default=sa.text("70.00"),
        ),
    )
    op.create_check_constraint(
        "ck_final_project_passing_percentage",
        "course_final_projects",
        "minimum_passing_percentage BETWEEN 0 AND 100",
    )

    op.drop_constraint(
        "ck_certificate_eligibility_result",
        "certificate_eligibility",
        type_="check",
    )
    op.add_column(
        "certificate_eligibility",
        sa.Column(
            "module_checks_met",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "certificate_eligibility",
        sa.Column(
            "final_project_met",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # Existing evaluations predate these requirements and must be recalculated.
    op.execute(
        """
        UPDATE certificate_eligibility
        SET
            is_eligible = FALSE,
            missing_requirements_json =
                missing_requirements_json
                || '["module_checks", "final_project"]'::jsonb
        """
    )

    op.create_check_constraint(
        "ck_certificate_eligibility_result",
        "certificate_eligibility",
        """
        is_eligible = (
            attendance_met
            AND assignment_met
            AND lab_met
            AND mock_score_met
            AND blockers_cleared
            AND module_checks_met
            AND final_project_met
        )
        """,
    )


def downgrade() -> None:
    """Remove the module-test and final-project certificate requirements."""
    op.drop_constraint(
        "ck_certificate_eligibility_result",
        "certificate_eligibility",
        type_="check",
    )
    op.execute(
        """
        UPDATE certificate_eligibility
        SET is_eligible = (
            attendance_met
            AND assignment_met
            AND lab_met
            AND mock_score_met
            AND blockers_cleared
        )
        """
    )
    op.drop_column("certificate_eligibility", "final_project_met")
    op.drop_column("certificate_eligibility", "module_checks_met")
    op.create_check_constraint(
        "ck_certificate_eligibility_result",
        "certificate_eligibility",
        """
        is_eligible = (
            attendance_met
            AND assignment_met
            AND lab_met
            AND mock_score_met
            AND blockers_cleared
        )
        """,
    )

    op.drop_constraint(
        "ck_final_project_passing_percentage",
        "course_final_projects",
        type_="check",
    )
    op.drop_column("course_final_projects", "minimum_passing_percentage")
