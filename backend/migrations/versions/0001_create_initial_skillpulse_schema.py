
"""Create the initial SkillPulse PostgreSQL schema.

Revision ID: 0001
Revises:
Create Date: 2026-08-31
"""

from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SQL_DIRECTORY = Path(__file__).resolve().parents[1] / "sql"


def _execute_sql_file(file_name: str) -> None:
    sql = (SQL_DIRECTORY / file_name).read_text(encoding="utf-8")
    connection = op.get_bind()
    driver_connection = connection.connection.driver_connection
    with driver_connection.cursor() as cursor:
        cursor.execute(sql)


def upgrade() -> None:
    """Create the complete SkillPulse schema."""
    _execute_sql_file("0001_initial_schema.up.sql")


def downgrade() -> None:
    """Remove SkillPulse-owned database objects."""
    _execute_sql_file("0001_initial_schema.down.sql")
