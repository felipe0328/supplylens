import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from supplylens.port.persistence.refresh_token import (
    RefreshTokenPersistence,
    StoreRefreshTokenRequest,
)
from supplylens.port.persistence.users import User as PortUser
from supplylens.tools.encode_decode import encode_jwt
from supplylens.tools.token_hash import hash_token


def create_access_token(user: PortUser, ttl_seconds: int) -> str:
    return encode_jwt(
        {
            "sub": str(user.id),
            "role": user.role.value,
            "exp": datetime.now(UTC) + timedelta(seconds=ttl_seconds),
        }
    )


def create_refresh_token(
    user_id: UUID,
    persistence: RefreshTokenPersistence,
    ttl_seconds: int,
) -> tuple[str, int]:
    refresh_token = secrets.token_urlsafe(32)
    stored = persistence.store_refresh_token(
        StoreRefreshTokenRequest(
            user_id=user_id,
            hashed_token=hash_token(refresh_token),
            expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
        )
    )
    return refresh_token, stored.id
