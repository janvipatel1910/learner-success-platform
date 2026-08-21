from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from skillpulse.core.config import Settings, get_settings
from skillpulse.db.connection import database_is_ready
from skillpulse.schemas.health import HealthResponse, ReadinessResponse

router = APIRouter(tags=["System"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check API liveness",
)
def health_check(
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthResponse:
    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        timestamp=datetime.now(UTC),
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ReadinessResponse,
            "description": "API is running but PostgreSQL is unavailable",
        }
    },
    summary="Check API and PostgreSQL readiness",
)
def readiness_check(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReadinessResponse | JSONResponse:
    ready = database_is_ready()

    response = ReadinessResponse(
        status="ready" if ready else "not_ready",
        service=settings.app_name,
        database="connected" if ready else "unavailable",
        timestamp=datetime.now(UTC),
    )

    if not ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=response.model_dump(mode="json"),
        )

    return response
