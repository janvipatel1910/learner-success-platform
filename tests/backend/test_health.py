from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from skillpulse.api.routes import health as health_routes


def test_service_information(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "SkillPulse API",
        "version": "0.1.0",
        "documentation": "/docs",
        "health": "/health",
        "readiness": "/ready",
        "authentication": "/api/v1/auth/me",
    }


def test_health_check_returns_service_metadata(
    client: TestClient,
) -> None:
    response = client.get("/health")
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "healthy"
    assert payload["service"] == "SkillPulse API"
    assert payload["version"] == "0.1.0"
    assert payload["environment"] == "local"
    assert datetime.fromisoformat(payload["timestamp"]).tzinfo is not None


def test_readiness_returns_200_when_database_is_available(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        health_routes,
        "database_is_ready",
        lambda: True,
    )

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["database"] == "connected"


def test_readiness_returns_503_when_database_is_unavailable(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        health_routes,
        "database_is_ready",
        lambda: False,
    )

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["database"] == "unavailable"


def test_openapi_schema_contains_system_endpoints(
    client: TestClient,
) -> None:
    response = client.get("/openapi.json")
    paths = response.json()["paths"]

    assert response.status_code == 200
    assert "/health" in paths
    assert "/ready" in paths
