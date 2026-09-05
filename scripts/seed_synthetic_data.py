"""Load deterministic synthetic data into a non-production SkillPulse database."""

from pathlib import Path

import psycopg

from skillpulse.core.config import get_settings

SEED_FILE = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "sample"
    / "skillpulse_seed.sql"
)


def load_synthetic_data() -> None:
    """Load the versioned synthetic demonstration dataset."""
    settings = get_settings()

    if settings.environment == "production":
        raise RuntimeError("Synthetic seed data is blocked in production.")

    seed_sql = SEED_FILE.read_text(encoding="utf-8")

    with psycopg.connect(
        dbname=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password.get_secret_value(),
        host=settings.postgres_host,
        port=settings.postgres_port,
        connect_timeout=settings.database_connect_timeout_seconds,
    ) as connection, connection.cursor() as cursor:
        cursor.execute(seed_sql)



def main() -> None:
    """Load synthetic data and report success."""
    load_synthetic_data()
    print("Synthetic SkillPulse seed data loaded successfully.")


if __name__ == "__main__":
    main()
