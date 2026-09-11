from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from skillpulse.api.routes.auth import router as auth_router
from skillpulse.api.routes.catalog import router as catalog_router
from skillpulse.api.routes.health import router as health_router
from skillpulse.core.config import Settings, get_settings
from skillpulse.db.connection import close_database_connections


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    close_database_connections()


def create_application(settings: Settings | None = None) -> FastAPI:
    application_settings = settings or get_settings()

    application = FastAPI(
        title=application_settings.app_name,
        version=application_settings.app_version,
        description=(
            "Learner-success API for assessments, labs, blockers, "
            "interventions and explainable exam readiness."
        ),
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=application_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health_router)
    application.include_router(auth_router, prefix=application_settings.api_prefix)
    application.include_router(
    catalog_router,
    prefix=application_settings.api_prefix,
)
    @application.get("/", include_in_schema=False)
    def service_information() -> dict[str, str]:
        return {
            "service": application_settings.app_name,
            "version": application_settings.app_version,
            "documentation": "/docs",
            "health": "/health",
            "readiness": "/ready",
            "authentication": f"{application_settings.api_prefix}/auth/me",
        }

    return application


app = create_application()
