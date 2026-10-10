from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from supplylens.domain.auth import AccessPrincipal
from supplylens.routes.v1.dependencies import require_access_token, required_admin

JWT_SECRET = "synthetic-jwt-secret-with-32-characters"
USER_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


@pytest.fixture
def jwt_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("JWT_ACCESS_TTL_SECONDS", "900")
    monkeypatch.setenv("JWT_REFRESH_TTL_SECONDS", "604800")
    monkeypatch.setattr("supplylens.config.__jwt_settings", None)


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/session")
    def session_route(
        principal: Annotated[AccessPrincipal, Depends(require_access_token)],
    ) -> dict[str, str]:
        return {"user_id": str(principal.user_id), "role": principal.role.value}

    @app.get("/admin")
    def admin_route(
        principal: Annotated[AccessPrincipal, Depends(required_admin)],
    ) -> dict[str, str]:
        return {"user_id": str(principal.user_id), "role": principal.role.value}

    return app


@pytest.fixture
def client(jwt_environment: None) -> TestClient:
    return TestClient(_app())


def _token(**overrides: object) -> str:
    payload: dict[str, object] = {
        "sub": str(USER_ID),
        "role": "OPERATOR",
        "exp": datetime.now(UTC) + timedelta(minutes=15),
    }
    payload.update(overrides)
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_require_access_token_returns_the_caller(client: TestClient) -> None:
    response = client.get("/session", headers=_bearer(_token()))

    assert response.status_code == 200
    assert response.json() == {"user_id": str(USER_ID), "role": "OPERATOR"}


def test_require_access_token_accepts_an_admin(client: TestClient) -> None:
    response = client.get("/session", headers=_bearer(_token(role="ADMIN")))

    assert response.status_code == 200
    assert response.json() == {"user_id": str(USER_ID), "role": "ADMIN"}


def test_require_access_token_rejects_a_missing_header(client: TestClient) -> None:
    response = client.get("/session")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
    assert response.headers["www-authenticate"] == "Bearer"


def test_require_access_token_rejects_a_non_bearer_scheme(client: TestClient) -> None:
    response = client.get("/session", headers={"Authorization": "Basic abc"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_require_access_token_rejects_an_invalid_token(client: TestClient) -> None:
    response = client.get("/session", headers=_bearer("not-a-token"))

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}
    assert response.headers["www-authenticate"] == "Bearer"


def test_require_access_token_rejects_an_expired_token(client: TestClient) -> None:
    token = _token(exp=datetime.now(UTC) - timedelta(seconds=5))

    response = client.get("/session", headers=_bearer(token))

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("JWT_SECRET", ""),
        ("JWT_SECRET", "too-short"),
        ("JWT_ACCESS_TTL_SECONDS", "0"),
        ("JWT_REFRESH_TTL_SECONDS", "nope"),
    ],
)
def test_require_access_token_reports_invalid_jwt_configuration_as_a_server_error(
    monkeypatch: pytest.MonkeyPatch,
    setting: str,
    value: str,
) -> None:
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("JWT_ACCESS_TTL_SECONDS", "900")
    monkeypatch.setenv("JWT_REFRESH_TTL_SECONDS", "604800")
    monkeypatch.setenv(setting, value)
    monkeypatch.setattr("supplylens.config.__jwt_settings", None)
    failing_client = TestClient(_app(), raise_server_exceptions=False)

    response = failing_client.get("/session", headers=_bearer(_token()))

    assert response.status_code == 500


def test_require_access_token_rejects_a_different_secret(client: TestClient) -> None:
    token = jwt.encode(
        _token_payload(),
        "another-synthetic-secret-32-characters",
        algorithm="HS256",
    )

    response = client.get("/session", headers=_bearer(token))

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


@pytest.mark.parametrize("claim", ["sub", "role", "exp"])
def test_require_access_token_rejects_a_missing_claim(
    client: TestClient, claim: str
) -> None:
    payload = _token_payload()
    del payload[claim]
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    response = client.get("/session", headers=_bearer(token))

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


@pytest.mark.parametrize(
    "overrides",
    [
        {"sub": "not-a-uuid"},
        {"sub": None},
        {"sub": 1},
        {"role": "MEMBER"},
        {"role": None},
        {"role": 1},
    ],
)
def test_require_access_token_rejects_unusable_claims(
    client: TestClient, overrides: dict[str, object]
) -> None:
    response = client.get("/session", headers=_bearer(_token(**overrides)))

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_required_admin_allows_an_admin(client: TestClient) -> None:
    response = client.get("/admin", headers=_bearer(_token(role="ADMIN")))

    assert response.status_code == 200
    assert response.json() == {"user_id": str(USER_ID), "role": "ADMIN"}


def test_required_admin_rejects_an_operator(client: TestClient) -> None:
    response = client.get("/admin", headers=_bearer(_token()))

    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}


def test_required_admin_rejects_a_missing_token(client: TestClient) -> None:
    response = client.get("/admin")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def _token_payload() -> dict[str, object]:
    return {
        "sub": str(USER_ID),
        "role": "OPERATOR",
        "exp": datetime.now(UTC) + timedelta(minutes=15),
    }
