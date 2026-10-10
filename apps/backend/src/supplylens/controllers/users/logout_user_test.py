from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest

from supplylens.controllers.users.constants import INVALID_REFRESH_TOKEN
from supplylens.controllers.users.exceptions import InvalidOrExpiredRefreshTokenError
from supplylens.controllers.users.logout_user import LogoutUserRequest, logout_user
from supplylens.port.persistence.refresh_token import (
    RefreshToken,
    UpdateRefreshTokenRequest,
)
from supplylens.tools.token_hash import hash_token

USER_ID = UUID("12345678-1234-5678-1234-567812345678")
EXPIRES_AT = datetime(2099, 1, 1, tzinfo=UTC)
RAW_TOKEN = "synthetic-refresh-token"


class FakeRefreshTokenPersistence:
    def __init__(self, tokens: list[RefreshToken] | None = None) -> None:
        self.by_id = {token.id: token for token in tokens or []}
        self.commits = 0

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

    def update_refresh_token(
        self, id: int, request: UpdateRefreshTokenRequest
    ) -> RefreshToken | None:
        current = self.by_id[id]
        if current.revoked_at is not None:
            return None
        updated = replace(
            current,
            revoked_at=request.revoked_at,
            replaced_by=request.replaced_by,
        )
        self.by_id[id] = updated
        return updated

    def commit(self) -> None:
        self.commits += 1


def _token(
    token_id: int = 1,
    *,
    raw_token: str = RAW_TOKEN,
    replaced_by: int | None = None,
    revoked_at: datetime | None = None,
    expires_at: datetime = EXPIRES_AT,
) -> RefreshToken:
    return RefreshToken(
        id=token_id,
        user_id=USER_ID,
        hashed_token=hash_token(raw_token),
        expires_at=expires_at,
        revoked_at=revoked_at,
        replaced_by=replaced_by,
    )


def test_logout_user_revokes_the_current_token() -> None:
    current = _token()
    tokens = FakeRefreshTokenPersistence([current])

    logout_user(LogoutUserRequest(refresh_token=RAW_TOKEN), tokens)

    stored = tokens.by_id[current.id]
    assert stored.revoked_at is not None
    assert stored.replaced_by is None
    assert tokens.commits == 0
    assert tokens.get_refresh_token(hash_token(RAW_TOKEN)) is stored


def test_logout_user_rejects_an_expired_token() -> None:
    current = _token(expires_at=datetime(2020, 1, 1, tzinfo=UTC))
    tokens = FakeRefreshTokenPersistence([current])

    with pytest.raises(InvalidOrExpiredRefreshTokenError, match=INVALID_REFRESH_TOKEN):
        logout_user(LogoutUserRequest(refresh_token=RAW_TOKEN), tokens)

    assert tokens.commits == 0
    assert tokens.by_id[current.id].revoked_at is None


def test_logout_user_revokes_the_newer_token_when_an_expired_ancestor_is_reused() -> (
    None
):
    revoked_at = datetime(2026, 10, 10, tzinfo=UTC)
    old = _token(
        1,
        revoked_at=revoked_at,
        replaced_by=2,
        expires_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    current = _token(2, raw_token="synthetic-refresh-token-current")
    tokens = FakeRefreshTokenPersistence([old, current])

    with pytest.raises(InvalidOrExpiredRefreshTokenError, match=INVALID_REFRESH_TOKEN):
        logout_user(LogoutUserRequest(refresh_token=RAW_TOKEN), tokens)

    assert tokens.commits == 1
    assert tokens.by_id[2].revoked_at is not None
    assert tokens.by_id[2].replaced_by is None


def test_logout_user_rejects_an_unknown_token() -> None:
    tokens = FakeRefreshTokenPersistence()

    with pytest.raises(InvalidOrExpiredRefreshTokenError, match=INVALID_REFRESH_TOKEN):
        logout_user(LogoutUserRequest(refresh_token=RAW_TOKEN), tokens)


def test_logout_user_revokes_the_newer_token_when_the_old_one_is_reused() -> None:
    revoked_at = datetime(2026, 10, 10, tzinfo=UTC)
    old = _token(1, revoked_at=revoked_at, replaced_by=2)
    current = _token(2, raw_token="synthetic-refresh-token-current")
    tokens = FakeRefreshTokenPersistence([old, current])

    with pytest.raises(InvalidOrExpiredRefreshTokenError, match=INVALID_REFRESH_TOKEN):
        logout_user(LogoutUserRequest(refresh_token=RAW_TOKEN), tokens)

    assert tokens.commits == 1
    assert tokens.by_id[2].revoked_at is not None
    assert tokens.by_id[2].replaced_by is None
