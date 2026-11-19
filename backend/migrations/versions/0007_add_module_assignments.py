"""Add module assignments and learner submissions.

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """One written assignment per module, reviewed by a cohort tutor."""
    op.create_table(
        "module_assignments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "course_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "topic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("topics.id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="assessment_status", create_type=False),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        # One assignment per module.
        sa.UniqueConstraint("topic_id", name="uq_module_assignment_topic"),
        sa.UniqueConstraint(
            "id", "course_id", name="uq_module_assignment_id_course"
        ),
        sa.CheckConstraint(
            "length(btrim(title)) > 0", name="ck_module_assignment_title"
        ),
        sa.CheckConstraint(
            "length(btrim(instructions)) > 0",
            name="ck_module_assignment_instructions",
        ),
    )

    op.create_table(
        "assignment_submissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "assignment_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cohort_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submission_number", sa.Integer(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("link_url", sa.Text(), nullable=True),
        sa.Column(
            "review_status",
            postgresql.ENUM(name="lab_review_status", create_type=False),
            nullable=False,
            server_default=sa.text("'submitted'"),
        ),
        sa.Column("tutor_feedback", sa.Text(), nullable=True),
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id", "course_id"],
            ["module_assignments.id", "module_assignments.course_id"],
            name="fk_assignment_submission_assignment",
        ),
        sa.ForeignKeyConstraint(
            ["cohort_id", "course_id"],
            ["cohorts.id", "cohorts.course_id"],
            name="fk_assignment_submission_cohort_course",
        ),
        sa.ForeignKeyConstraint(
            ["cohort_id", "learner_id"],
            ["cohort_memberships.cohort_id", "cohort_memberships.user_id"],
            name="fk_assignment_submission_membership",
        ),
        sa.UniqueConstraint(
            "assignment_id",
            "cohort_id",
            "learner_id",
            "submission_number",
            name="uq_assignment_submission_number",
        ),
        sa.CheckConstraint(
            "submission_number > 0", name="ck_assignment_submission_number"
        ),
        sa.CheckConstraint(
            "length(btrim(answer_text)) BETWEEN 50 AND 5000",
            name="ck_assignment_answer_length",
        ),
        sa.CheckConstraint(
            "link_url IS NULL OR link_url LIKE 'https://%'",
            name="ck_assignment_link_https",
        ),
        # Assignments are approved or sent back; there is no score.
        sa.CheckConstraint(
            "review_status IN ('submitted', 'changes_requested', 'approved')",
            name="ck_assignment_review_status",
        ),
        sa.CheckConstraint(
            "(review_status = 'submitted') = (reviewed_at IS NULL)"
            " AND (reviewed_at IS NULL) = (reviewed_by IS NULL)"
            " AND (reviewed_at IS NULL OR tutor_feedback IS NOT NULL)",
            name="ck_assignment_review_fields",
        ),
    )
    op.create_index(
        "ix_assignment_submissions_cohort_status",
        "assignment_submissions",
        ["cohort_id", "review_status", "submitted_at"],
    )


def downgrade() -> None:
    """Remove assignments and their submissions."""
    op.drop_index(
        "ix_assignment_submissions_cohort_status",
        table_name="assignment_submissions",
    )
    op.drop_table("assignment_submissions")
    op.drop_table("module_assignments")
