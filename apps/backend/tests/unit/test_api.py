import pytest
from fastapi.testclient import TestClient

from supplylens.api import app
from supplylens.routes.v1 import routes

client = TestClient(app)


def test_liveness_succeeds_without_database_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_succeeds_when_database_is_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(routes, "health_check", lambda: True)

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_readiness_returns_503_without_database_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database configuration error"}


def test_readiness_returns_503_when_database_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_health_check() -> None:
        raise RuntimeError("connection refused with private details")

    monkeypatch.setattr(routes, "health_check", fail_health_check)

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert "private details" not in response.text
