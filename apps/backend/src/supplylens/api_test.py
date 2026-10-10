from importlib.metadata import version

import pytest
from fastapi.testclient import TestClient

from supplylens.api import app, create_app
from supplylens.config import AppEnvironment
from supplylens.routes.v1 import health

client = TestClient(app)


@pytest.mark.parametrize(
    ("environment", "expected_debug"),
    [
        ("development", True),
        ("test", False),
        ("production", False),
    ],
)
def test_app_debug_mode_uses_app_environment(
    monkeypatch: pytest.MonkeyPatch,
    environment: str,
    expected_debug: bool,
) -> None:
    monkeypatch.setenv("APP_ENV", environment)

    assert create_app().debug is expected_debug


def test_app_environment_rejects_unknown_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "staging")

    with pytest.raises(ValueError, match="APP_ENV must be"):
        create_app()


def test_create_app_can_be_configured_explicitly() -> None:
    assert create_app(AppEnvironment.DEVELOPMENT).debug is True
    assert create_app(AppEnvironment.PRODUCTION).debug is False


def test_app_version_matches_package_version() -> None:
    assert create_app(AppEnvironment.TESTING).version == version("supplylens")


def test_create_app_registers_health_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health, "health_check", lambda: True)
    configured_client = TestClient(create_app(AppEnvironment.TESTING))

    assert configured_client.get("/health").json() == {"status": "ok"}
    assert configured_client.get("/api/v1/health/ready").json() == {"status": "healthy"}


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
    monkeypatch.setattr(health, "health_check", lambda: True)

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

    monkeypatch.setattr(health, "health_check", fail_health_check)

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert "private details" not in response.text
