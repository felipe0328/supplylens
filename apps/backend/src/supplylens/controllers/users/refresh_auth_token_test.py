from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
import pytest

from supplylens.config import JWTSettings
from supplylens.controllers.users.constants import INVALID_REFRESH_TOKEN, TOKEN_TYPE
from supplylens.controllers.users.exceptions import InvalidOrExpiredRefreshTokenError
from supplylens.controllers.users.refresh_auth_token import (
    RefreshAuthTokenRequest,
    refresh_auth_token,
)
from supplylens.domain.users import UserRole, UserStatus
from supplylens.port.persistence.refresh_token import (
    RefreshToken,
    StoreRefreshTokenRequest,
    UpdateRefreshTokenRequest,
)
from supplylens.port.persistence.users import User as PortUser
from supplylens.tools.token_hash import hash_token

USER_ID = UUID("12345678-1234-5678-1234-567812345678")
CREATED_AT = datetime(2026, 10, 7, tzinfo=UTC)
EXPIRES_AT = datetime(2099, 1, 1, tzinfo=UTC)
RAW_TOKEN = "synthetic-refresh-token"
JWT_SECRET = "synthetic-jwt-secret-with-32-characters"
ACCESS_TTL_SECONDS = 900
REFRESH_TTL_SECONDS = 604800


class FakeUserPersistence:
    def __init__(self, user: PortUser | None) -> None:
        self._user = user

    def get_user_by_id(self, id: UUID) -> PortUser | None:
        if self._user is None or self._user.id != id:
            return None
        return self._user


class FakeRefreshTokenPersistence:
    def __init__(self, tokens: list[RefreshToken] | None = None) -> None:
        self.by_id = {token.id: token for token in tokens or []}
        self.stored: list[StoreRefreshTokenRequest] = []
        self._next_id = max(self.by_id, default=0) + 1

    def get_refresh_token(self, hashed_token: str) -> RefreshToken | None:
        return next(
            (
                token
                for token in self.by_id.values()
                if token.hashed_token == hashed_token
            ),
            None,
        )

    def get_refresh_token_by_id(self, id: int) -> RefreshToken | None:
        return self.by_id.get(id)

    def store_refresh_token(self, request: StoreRefreshTokenRequest) -> RefreshToken:
        token = RefreshToken(
            id=self._next_id,
            user_id=request.user_id,
            hashed_token=request.hashed_token,
            expires_at=request.expires_at,
            revoked_at=None,
            replaced_by=None,
        )
        self._next_id += 1
        self.by_id[token.id] = token
        self.stored.append(request)
        return token

    def update_refresh_token(
        self, id: int, request: UpdateRefreshTokenRequest
    ) -> RefreshToken:
        updated = replace(
            self.by_id[id],
            revoked_at=request.revoked_at,
            replaced_by=request.replaced_by,
        )
        self.by_id[id] = updated
        return updated


def _user(**overrides: object) -> PortUser:
    values: dict[str, object] = {
        "id": USER_ID,
        "email": "operator@example.com",
        "password_hash": "synthetic-hash",
        "role": UserRole.OPERATOR,
        "status": UserStatus.ACCEPTED,
        "accepted_by": None,
        "pending_expires_at": None,
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
        "deleted_at": None,
    }
    values.update(overrides)
    return PortUser(**values)  # type: ignore[arg-type]


def _token(
    token_id: int = 1,
    *,
    raw_token: str = RAW_TOKEN,
    replaced_by: int | None = None,
    revoked_at: datetime | None = None,
) -> RefreshToken:
    return RefreshToken(
        id=token_id,
        user_id=USER_ID,
        hashed_token=hash_token(raw_token),
        expires_at=EXPIRES_AT,
        revoked_at=revoked_at,
        replaced_by=replaced_by,
    )


@pytest.fixture
def jwt_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = JWTSettings(
        secret=JWT_SECRET,
        access_ttl_seconds=ACCESS_TTL_SECONDS,
        refresh_ttl_seconds=REFRESH_TTL_SECONDS,
    )
    monkeypatch.setattr(
        "supplylens.controllers.users.refresh_auth_token.get_jwt_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        "supplylens.tools.encode_decode.get_jwt_settings",
        lambda: settings,
    )


def test_refresh_auth_token_issues_a_new_pair(jwt_settings: None) -> None:
    current = _token()
    tokens = FakeRefreshTokenPersistence([current])
    before = datetime.now(UTC)

    result = refresh_auth_token(
        RefreshAuthTokenRequest(refresh_token=RAW_TOKEN),
        tokens,
        FakeUserPersistence(_user(role=UserRole.ADMIN)),
    )

    assert result.token_type == TOKEN_TYPE
    assert result.expires_in == ACCESS_TTL_SECONDS
    assert result.refresh_token != RAW_TOKEN
    payload = jwt.decode(result.access_token, JWT_SECRET, algorithms=["HS256"])
    assert payload["sub"] == str(USER_ID)
    assert payload["role"] == "ADMIN"
    expires_at = datetime.fromtimestamp(payload["exp"], UTC)
    assert expires_at >= before + timedelta(seconds=ACCESS_TTL_SECONDS - 1)
    assert tokens.stored[0].hashed_token == hash_token(result.refresh_token)
    stored_refresh_expiry = tokens.stored[0].expires_at
    assert stored_refresh_expiry >= before + timedelta(seconds=REFRESH_TTL_SECONDS - 1)
    revoked = tokens.by_id[current.id]
    assert revoked.revoked_at is not None
    assert revoked.replaced_by == current.id + 1


def test_refresh_auth_token_rejects_an_unknown_token(jwt_settings: None) -> None:
    tokens = FakeRefreshTokenPersistence()

    with pytest.raises(InvalidOrExpiredRefreshTokenError, match=INVALID_REFRESH_TOKEN):
        refresh_auth_token(
            RefreshAuthTokenRequest(refresh_token=RAW_TOKEN),
            tokens,
            FakeUserPersistence(_user()),
        )

    assert tokens.stored == []


def test_refresh_auth_token_revokes_the_newer_token_when_the_old_one_is_reused(
    jwt_settings: None,
) -> None:
    revoked_at = datetime(2026, 10, 10, tzinfo=UTC)
    old = _token(1, revoked_at=revoked_at, replaced_by=2)
    current = _token(2, raw_token="synthetic-refresh-token-current")
    tokens = FakeRefreshTokenPersistence([old, current])

    with pytest.raises(InvalidOrExpiredRefreshTokenError, match=INVALID_REFRESH_TOKEN):
        refresh_auth_token(
            RefreshAuthTokenRequest(refresh_token=RAW_TOKEN),
            tokens,
            FakeUserPersistence(_user()),
        )

    assert tokens.stored == []
    assert tokens.by_id[2].revoked_at is not None
    assert tokens.by_id[2].replaced_by is None


@pytest.mark.parametrize(
    "user",
    [
        None,
        _user(status=UserStatus.DELETED),
        _user(status=UserStatus.PENDING),
    ],
)
def test_refresh_auth_token_revokes_when_the_account_cannot_continue(
    jwt_settings: None, user: PortUser | None
) -> None:
    current = _token()
    tokens = FakeRefreshTokenPersistence([current])

    with pytest.raises(InvalidOrExpiredRefreshTokenError, match=INVALID_REFRESH_TOKEN):
        refresh_auth_token(
            RefreshAuthTokenRequest(refresh_token=RAW_TOKEN),
            tokens,
            FakeUserPersistence(user),
        )

    assert tokens.stored == []
    assert tokens.by_id[current.id].revoked_at is not None
