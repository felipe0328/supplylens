from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from supplylens.controllers.users.refresh_token_chain import revoke_refresh_token_family
from supplylens.port.persistence.refresh_token import (
    RefreshToken,
    UpdateRefreshTokenRequest,
)

USER_ID = UUID("12345678-1234-5678-1234-567812345678")
EXPIRES_AT = datetime(2099, 1, 1, tzinfo=UTC)


class FakeRefreshTokenPersistence:
    def __init__(self, tokens: list[RefreshToken]) -> None:
        self.by_id = {token.id: token for token in tokens}

    def get_refresh_token_by_id(self, id: int) -> RefreshToken | None:
        return self.by_id.get(id)

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


def _token(
    token_id: int,
    *,
    replaced_by: int | None = None,
    revoked_at: datetime | None = None,
) -> RefreshToken:
    return RefreshToken(
        id=token_id,
        user_id=USER_ID,
        hashed_token=f"synthetic-hash-{token_id}",
        expires_at=EXPIRES_AT,
        revoked_at=revoked_at,
        replaced_by=replaced_by,
    )


def test_revoke_refresh_token_family_revokes_the_current_token() -> None:
    current = _token(1)
    persistence = FakeRefreshTokenPersistence([current])

    revoke_refresh_token_family(current, persistence)

    stored = persistence.by_id[1]
    assert stored.revoked_at is not None
    assert stored.replaced_by is None


def test_revoke_refresh_token_family_revokes_each_newer_token() -> None:
    revoked_at = datetime(2026, 10, 10, tzinfo=UTC)
    oldest = _token(1, replaced_by=2, revoked_at=revoked_at)
    middle = _token(2, replaced_by=3, revoked_at=revoked_at)
    newest = _token(3)
    persistence = FakeRefreshTokenPersistence([oldest, middle, newest])

    revoke_refresh_token_family(oldest, persistence)

    assert persistence.by_id[1] is oldest
    assert persistence.by_id[2] is middle
    assert persistence.by_id[3].revoked_at is not None
    assert persistence.by_id[3].replaced_by is None


def test_revoke_refresh_token_family_stops_when_the_successor_is_missing() -> None:
    revoked_at = datetime(2026, 10, 10, tzinfo=UTC)
    current = _token(1, replaced_by=99, revoked_at=revoked_at)
    persistence = FakeRefreshTokenPersistence([current])

    revoke_refresh_token_family(current, persistence)

    assert persistence.by_id[1] is current
