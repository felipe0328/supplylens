from dataclasses import dataclass
from datetime import UTC, datetime

from supplylens.config import get_jwt_settings
from supplylens.domain.users import UserStatus
from supplylens.port.persistence.refresh_token import (
    RefreshTokenPersistence,
    UpdateRefreshTokenRequest,
)
from supplylens.port.persistence.users import UserPersistence
from supplylens.tools.token_hash import hash_token

from .constants import INVALID_REFRESH_TOKEN, TOKEN_TYPE
from .exceptions import InvalidOrExpiredRefreshTokenError
from .refresh_token_chain import refresh_token_is_expired, revoke_refresh_token_family
from .session_tokens import create_access_token, create_refresh_token


@dataclass(frozen=True)
class RefreshAuthTokenRequest:
    refresh_token: str


@dataclass(frozen=True)
class RefreshAuthTokenResponse:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


def _keep_revocation(persistence: RefreshTokenPersistence) -> None:
    """Commit so the request transaction cannot roll the revocation back."""
    persistence.commit()
    raise InvalidOrExpiredRefreshTokenError(INVALID_REFRESH_TOKEN)


def refresh_auth_token(
    req: RefreshAuthTokenRequest,
    refresh_token_persistence: RefreshTokenPersistence,
    user_persistence: UserPersistence,
) -> RefreshAuthTokenResponse:
    existing_token = refresh_token_persistence.get_refresh_token(
        hash_token(req.refresh_token)
    )
    if existing_token is None:
        raise InvalidOrExpiredRefreshTokenError(INVALID_REFRESH_TOKEN)

    if existing_token.revoked_at is not None:
        revoke_refresh_token_family(existing_token, refresh_token_persistence)
        _keep_revocation(refresh_token_persistence)

    if refresh_token_is_expired(existing_token):
        raise InvalidOrExpiredRefreshTokenError(INVALID_REFRESH_TOKEN)

    user = user_persistence.get_user_by_id(existing_token.user_id)
    if user is None or user.status is not UserStatus.ACCEPTED:
        revoke_refresh_token_family(existing_token, refresh_token_persistence)
        _keep_revocation(refresh_token_persistence)

    settings = get_jwt_settings()
    new_token, new_token_id = create_refresh_token(
        existing_token.user_id,
        refresh_token_persistence,
        settings.refresh_ttl_seconds,
    )
    rotated = refresh_token_persistence.update_refresh_token(
        existing_token.id,
        UpdateRefreshTokenRequest(
            revoked_at=datetime.now(UTC),
            replaced_by=new_token_id,
        ),
    )
    if rotated is None:
        raise InvalidOrExpiredRefreshTokenError(INVALID_REFRESH_TOKEN)
    return RefreshAuthTokenResponse(
        access_token=create_access_token(user, settings.access_ttl_seconds),
        refresh_token=new_token,
        token_type=TOKEN_TYPE,
        expires_in=settings.access_ttl_seconds,
    )
