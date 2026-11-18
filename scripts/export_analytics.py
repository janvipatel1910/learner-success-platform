"""Export the SkillPulse analytics views to CSV files.

Reads each PostgreSQL analytics view into a pandas DataFrame and saves it
as a CSV in data/processed/analytics/ (ignored by Git). These files are the
starting point for analysis and the Power BI dashboard.

Connection settings come from environment variables and default to the
local Docker Compose database.

Usage:
    python scripts/export_analytics.py
"""

import os
from pathlib import Path

import pandas as pd
import psycopg
from psycopg import sql

ANALYTICS_VIEWS = [
    "learner_latest_readiness",
    "open_blocker_aging",
    "attendance_risk_summary",
    "confidence_competence_gap",
    "cohort_weak_topics",
    "intervention_outcomes",
    "certificate_eligibility_summary",
]

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data" / "processed" / "analytics"


def connect() -> psycopg.Connection:
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "55432")),
        dbname=os.getenv("POSTGRES_DB", "skillpulse"),
        user=os.getenv("POSTGRES_USER", "skillpulse"),
        password=os.getenv("POSTGRES_PASSWORD", "skillpulse_local_only"),
    )


def read_view(connection: psycopg.Connection, view_name: str) -> pd.DataFrame:
    # sql.Identifier quotes the name safely instead of pasting text into SQL.
    query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(view_name))
    with connection.cursor() as cursor:
        cursor.execute(query)
        columns = [column.name for column in cursor.description]
        return pd.DataFrame(cursor.fetchall(), columns=columns)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with connect() as connection:
        for view_name in ANALYTICS_VIEWS:
            df = read_view(connection, view_name)
            output_file = OUTPUT_DIR / f"{view_name}.csv"
            df.to_csv(output_file, index=False)
            print(f"{view_name:<34} {len(df):>5} rows -> {output_file.name}")

    print(f"\nSaved {len(ANALYTICS_VIEWS)} files to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
