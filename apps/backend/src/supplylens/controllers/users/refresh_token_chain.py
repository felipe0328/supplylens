from datetime import UTC, datetime

from supplylens.port.persistence.refresh_token import (
    RefreshToken,
    RefreshTokenPersistence,
    UpdateRefreshTokenRequest,
)


def refresh_token_is_expired(token: RefreshToken) -> bool:
    expires_at = token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= datetime.now(UTC)


def revoke_refresh_token_family(
    token: RefreshToken, persistence: RefreshTokenPersistence
) -> None:
    revoked_at = datetime.now(UTC)
    if token.revoked_at is None:
        persistence.update_refresh_token(
            token.id,
            UpdateRefreshTokenRequest(
                revoked_at=revoked_at,
                replaced_by=token.replaced_by,
            ),
        )

    current = token
    while current.replaced_by is not None:
        successor = persistence.get_refresh_token_by_id(current.replaced_by)
        if successor is None:
            return
        if successor.revoked_at is None:
            persistence.update_refresh_token(
                successor.id,
                UpdateRefreshTokenRequest(
                    revoked_at=revoked_at,
                    replaced_by=successor.replaced_by,
                ),
            )
        current = successor
