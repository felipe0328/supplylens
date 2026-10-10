from dataclasses import dataclass

from supplylens.port.persistence.refresh_token import RefreshTokenPersistence
from supplylens.tools.token_hash import hash_token

from .constants import INVALID_REFRESH_TOKEN
from .exceptions import InvalidOrExpiredRefreshTokenError
from .refresh_token_chain import revoke_refresh_token_family


@dataclass(frozen=True)
class LogoutUserRequest:
    refresh_token: str


def logout_user(
    req: LogoutUserRequest, refresh_token_persistence: RefreshTokenPersistence
) -> None:
    existing_token = refresh_token_persistence.get_refresh_token(
        hash_token(req.refresh_token)
    )
    if existing_token is None:
        raise InvalidOrExpiredRefreshTokenError(INVALID_REFRESH_TOKEN)

    revoke_refresh_token_family(existing_token, refresh_token_persistence)
    if existing_token.revoked_at is not None:
        raise InvalidOrExpiredRefreshTokenError(INVALID_REFRESH_TOKEN)
