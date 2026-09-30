from supplylens.api import app, health


def test_health_returns_process_status() -> None:
    assert health() == {"status": "ok"}


def test_app_exposes_health_routes() -> None:
    paths = set(app.openapi()["paths"])

    assert "/health" in paths
    assert "/api/v1/health/ready" in paths
