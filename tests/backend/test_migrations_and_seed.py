import os
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from scripts.seed_synthetic_data import load_synthetic_data
from sqlalchemy import text

from skillpulse.db.connection import get_engine

pytestmark = pytest.mark.integration

requires_database = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "true",
    reason="Set RUN_DATABASE_TESTS=true to run PostgreSQL integration tests",
)

requires_seed_tests = pytest.mark.skipif(
    os.getenv("RUN_SEED_TESTS") != "true",
    reason="Set RUN_SEED_TESTS=true to run synthetic seed tests",
)


@requires_database
def test_database_revision_is_head() -> None:
    with get_engine().connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()

    alembic_config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    expected_head = ScriptDirectory.from_config(alembic_config).get_current_head()

    assert revision == expected_head


@requires_database
@requires_seed_tests
def test_synthetic_seed_is_idempotent_and_populates_analytics() -> None:
    load_synthetic_data()
    load_synthetic_data()

    with get_engine().connect() as connection:
        core_counts = connection.execute(
            text(
                """
                SELECT
                    (SELECT COUNT(*) FROM users),
                    (
                        SELECT COUNT(*)
                        FROM cohort_memberships
                        WHERE cohort_role = 'learner'
                    ),
                    (SELECT COUNT(*) FROM class_sessions),
                    (SELECT COUNT(*) FROM assessment_attempts),
                    (SELECT COUNT(*) FROM blockers),
                    (SELECT COUNT(*) FROM readiness_snapshots)
                """
            )
        ).one()

        analytics_counts = connection.execute(
            text(
                """
                SELECT
                    (SELECT COUNT(*) FROM learner_latest_readiness),
                    (SELECT COUNT(*) FROM open_blocker_aging),
                    (SELECT COUNT(*) FROM attendance_risk_summary),
                    (SELECT COUNT(*) FROM confidence_competence_gap),
                    (SELECT COUNT(*) FROM cohort_weak_topics),
                    (SELECT COUNT(*) FROM intervention_outcomes),
                    (SELECT COUNT(*) FROM certificate_eligibility_summary)
                """
            )
        ).one()

    assert tuple(core_counts) == (4, 2, 2, 2, 2, 2)
    assert tuple(analytics_counts) == (2, 1, 2, 4, 2, 2, 2)
