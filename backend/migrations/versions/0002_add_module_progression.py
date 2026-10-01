"""Add learner module progress.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Store module progress within a learner's cohort."""
    op.create_table(
        "module_progress",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "cohort_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "learner_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "topic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("topics.id"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'in_progress'"),
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["cohort_id", "learner_id"],
            [
                "cohort_memberships.cohort_id",
                "cohort_memberships.user_id",
            ],
            name="fk_module_progress_membership",
        ),
        sa.UniqueConstraint(
            "cohort_id",
            "learner_id",
            "topic_id",
            name="uq_module_progress_learner_topic",
        ),
        sa.CheckConstraint(
            "status IN ('in_progress', 'completed')",
            name="ck_module_progress_status",
        ),
        sa.CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL)"
            " OR "
            "(status = 'in_progress' AND completed_at IS NULL)",
            name="ck_module_progress_completion",
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at",
            name="ck_module_progress_dates",
        ),
    )

    op.execute(
        """
        CREATE TRIGGER trg_module_progress_updated_at
        BEFORE UPDATE ON module_progress
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
        """
    )


def downgrade() -> None:
    """Remove module progress records and their table."""
    op.drop_table("module_progress")
