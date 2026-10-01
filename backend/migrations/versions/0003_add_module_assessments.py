"""Link modules to assessments and scoped attempts.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add module assessment configuration and attempt context."""
    # Composite foreign keys enforce that module and assessment
    # belong to the same course.
    op.create_unique_constraint(
        "uq_topics_id_course",
        "topics",
        ["id", "course_id"],
    )
    op.create_unique_constraint(
        "uq_assessments_id_course",
        "assessments",
        ["id", "course_id"],
    )

    op.create_table(
        "module_assessments",
        sa.Column(
            "topic_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "course_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "assessment_id",
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
            ["topic_id", "course_id"],
            ["topics.id", "topics.course_id"],
            name="fk_module_assessment_topic_course",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id", "course_id"],
            ["assessments.id", "assessments.course_id"],
            name="fk_module_assessment_assessment_course",
        ),
        sa.UniqueConstraint(
            "assessment_id",
            name="uq_module_assessment_assessment",
        ),
    )

    # Include learner_id in both foreign keys so an attempt
    # cannot be attached to another learner's module progress.
    op.create_unique_constraint(
        "uq_module_progress_id_learner",
        "module_progress",
        ["id", "learner_id"],
    )
    op.create_unique_constraint(
        "uq_assessment_attempt_id_learner",
        "assessment_attempts",
        ["id", "learner_id"],
    )

    op.create_table(
        "module_assessment_attempts",
        sa.Column(
            "attempt_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "module_progress_id",
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
            ["attempt_id", "learner_id"],
            ["assessment_attempts.id", "assessment_attempts.learner_id"],
            name="fk_module_attempt_learner_attempt",
        ),
        sa.ForeignKeyConstraint(
            ["module_progress_id", "learner_id"],
            ["module_progress.id", "module_progress.learner_id"],
            name="fk_module_attempt_learner_progress",
        ),
    )

    op.create_index(
        "ix_module_attempt_progress",
        "module_assessment_attempts",
        ["module_progress_id"],
    )


def downgrade() -> None:
    """Remove module assessment links."""
    op.drop_index(
        "ix_module_attempt_progress",
        table_name="module_assessment_attempts",
    )
    op.drop_table("module_assessment_attempts")
    op.drop_constraint(
        "uq_assessment_attempt_id_learner",
        "assessment_attempts",
        type_="unique",
    )
    op.drop_constraint(
        "uq_module_progress_id_learner",
        "module_progress",
        type_="unique",
    )
    op.drop_table("module_assessments")
    op.drop_constraint(
        "uq_assessments_id_course",
        "assessments",
        type_="unique",
    )
    op.drop_constraint(
        "uq_topics_id_course",
        "topics",
        type_="unique",
    )
