import logging
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from skillpulse.core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    settings = get_settings()

    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=5,
        max_overflow=10,
        connect_args={
            "connect_timeout": settings.database_connect_timeout_seconds
        },
    )


def database_is_ready() -> bool:
    try:
        with get_engine().connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar_one()
            return result == 1
    except SQLAlchemyError as exc:
        logger.warning(
            "Database readiness check failed: %s",
            exc.__class__.__name__,
        )
        return False


def close_database_connections() -> None:
    if get_engine.cache_info().currsize:
        get_engine().dispose()
        get_engine.cache_clear()
