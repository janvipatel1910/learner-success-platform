import os

import pytest

from skillpulse.db.connection import database_is_ready

pytestmark = pytest.mark.integration

requires_database = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "true",
    reason="Set RUN_DATABASE_TESTS=true to run PostgreSQL integration tests",
)


@requires_database
def test_database_connection_is_ready() -> None:
    assert database_is_ready() is True
