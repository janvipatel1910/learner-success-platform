"""Add final project configuration and cohort-scoped submissions.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Link final projects and submissions to their course and cohort."""
    op.create_unique_constraint(
        "uq_lab_tasks_id_course",
        "lab_tasks",
        ["id", "course_id"],
    )
    op.create_unique_constraint(
        "uq_cohorts_id_course",
        "cohorts",
        ["id", "course_id"],
    )
    op.create_unique_constraint(
        "uq_lab_submissions_id_task_learner",
        "lab_submissions",
        ["id", "lab_task_id", "learner_id"],
    )

    op.create_table(
        "course_final_projects",
        sa.Column(
            "course_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "lab_task_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["lab_task_id", "course_id"],
            ["lab_tasks.id", "lab_tasks.course_id"],
            name="fk_final_project_lab_course",
        ),
        sa.UniqueConstraint(
            "course_id",
            "lab_task_id",
            name="uq_final_project_course_lab",
        ),
    )

    op.create_table(
        "final_project_submissions",
        sa.Column(
            "submission_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "course_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "cohort_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "lab_task_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "learner_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["course_id", "lab_task_id"],
            [
                "course_final_projects.course_id",
                "course_final_projects.lab_task_id",
            ],
            name="fk_final_submission_project",
        ),
        sa.ForeignKeyConstraint(
            ["cohort_id", "course_id"],
            ["cohorts.id", "cohorts.course_id"],
            name="fk_final_submission_cohort_course",
        ),
        sa.ForeignKeyConstraint(
            ["cohort_id", "learner_id"],
            [
                "cohort_memberships.cohort_id",
                "cohort_memberships.user_id",
            ],
            name="fk_final_submission_membership",
        ),
        sa.ForeignKeyConstraint(
            ["submission_id", "lab_task_id", "learner_id"],
            [
                "lab_submissions.id",
                "lab_submissions.lab_task_id",
                "lab_submissions.learner_id",
            ],
            name="fk_final_submission_lab_learner",
        ),
    )

    op.create_index(
        "ix_final_submissions_cohort_learner",
        "final_project_submissions",
        ["cohort_id", "learner_id"],
    )


def downgrade() -> None:
    """Remove final project configuration and submission links."""
    op.drop_index(
        "ix_final_submissions_cohort_learner",
        table_name="final_project_submissions",
    )
    op.drop_table("final_project_submissions")
    op.drop_table("course_final_projects")
    op.drop_constraint(
        "uq_lab_submissions_id_task_learner",
        "lab_submissions",
        type_="unique",
    )
    op.drop_constraint(
        "uq_cohorts_id_course",
        "cohorts",
        type_="unique",
    )
    op.drop_constraint(
        "uq_lab_tasks_id_course",
        "lab_tasks",
        type_="unique",
    )
