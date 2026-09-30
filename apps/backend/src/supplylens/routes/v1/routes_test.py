import pytest
from fastapi import HTTPException

from supplylens.routes.v1 import routes


def test_health_returns_healthy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(routes, "health_check", lambda: True)

    assert routes.health() == {"status": "healthy"}


@pytest.mark.parametrize(
    ("error", "detail"),
    [
        (ValueError("missing URL"), "Database configuration error: missing URL"),
        (
            RuntimeError("connection refused"),
            "Database unavailable: connection refused",
        ),
        (Exception("unexpected"), "Database health check failed: unexpected"),
    ],
)
def test_health_translates_database_errors(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    detail: str,
) -> None:
    def fail_health_check() -> None:
        raise error

    monkeypatch.setattr(routes, "health_check", fail_health_check)

    with pytest.raises(HTTPException) as raised:
        routes.health()

    assert raised.value.status_code == 503
    assert raised.value.detail == detail
