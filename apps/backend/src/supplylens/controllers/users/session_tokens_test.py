from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
import pytest

from supplylens.config import JWTSettings
from supplylens.controllers.users.session_tokens import (
    create_access_token,
    create_refresh_token,
)
from supplylens.domain.users import UserRole, UserStatus
from supplylens.port.persistence.refresh_token import (
    RefreshToken,
    StoreRefreshTokenRequest,
)
from supplylens.port.persistence.users import User as PortUser
from supplylens.tools.token_hash import hash_token

USER_ID = UUID("12345678-1234-5678-1234-567812345678")
JWT_SECRET = "synthetic-jwt-secret-with-32-characters"
ACCESS_TTL_SECONDS = 900
REFRESH_TTL_SECONDS = 604800


class FakeRefreshTokenPersistence:
    def __init__(self) -> None:
        self.stored: list[StoreRefreshTokenRequest] = []

    def store_refresh_token(self, request: StoreRefreshTokenRequest) -> RefreshToken:
        self.stored.append(request)
        return RefreshToken(
            id=1,
            user_id=request.user_id,
            hashed_token=request.hashed_token,
            expires_at=request.expires_at,
            revoked_at=None,
            replaced_by=None,
        )


def _user() -> PortUser:
    created_at = datetime(2026, 10, 7, tzinfo=UTC)
    return PortUser(
        id=USER_ID,
        email="operator@example.com",
        password_hash="synthetic-hash",
        role=UserRole.OPERATOR,
        status=UserStatus.ACCEPTED,
        accepted_by=None,
        pending_expires_at=None,
        created_at=created_at,
        updated_at=created_at,
        deleted_at=None,
    )


@pytest.fixture
def jwt_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = JWTSettings(
        secret=JWT_SECRET,
        access_ttl_seconds=ACCESS_TTL_SECONDS,
        refresh_ttl_seconds=REFRESH_TTL_SECONDS,
    )
    monkeypatch.setattr(
        "supplylens.tools.encode_decode.get_jwt_settings",
        lambda: settings,
    )


def test_create_access_token_embeds_the_user_and_ttl(jwt_settings: None) -> None:
    before = datetime.now(UTC)

    token = create_access_token(_user(), ACCESS_TTL_SECONDS)

    payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    assert payload["sub"] == str(USER_ID)
    assert payload["role"] == "OPERATOR"
    expires_at = datetime.fromtimestamp(payload["exp"], UTC)
    assert expires_at >= before + timedelta(seconds=ACCESS_TTL_SECONDS - 1)


def test_create_refresh_token_stores_the_hash_and_returns_the_raw_token() -> None:
    persistence = FakeRefreshTokenPersistence()
    before = datetime.now(UTC)

    raw_token, token_id = create_refresh_token(
        USER_ID, persistence, REFRESH_TTL_SECONDS
    )

    assert token_id == 1
    assert persistence.stored[0].hashed_token == hash_token(raw_token)
    assert persistence.stored[0].hashed_token != raw_token
    assert persistence.stored[0].user_id == USER_ID
    expires_at = persistence.stored[0].expires_at
    assert expires_at >= before + timedelta(seconds=REFRESH_TTL_SECONDS - 1)
