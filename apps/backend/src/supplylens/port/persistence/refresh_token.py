from dataclasses import dataclass
from datetime import datetime
from typing import List, Protocol
from uuid import UUID


@dataclass(frozen=True)
class StoreRefreshTokenRequest:
    user_id: UUID
    hashed_token: str
    expires_at: datetime


@dataclass(frozen=True)
class UpdateRefreshTokenRequest:
    revoked_at: datetime | None
    replaced_by: int | None


@dataclass(frozen=True)
class RefreshToken:
    id: int
    user_id: UUID
    hashed_token: str
    expires_at: datetime
    revoked_at: datetime | None
    replaced_by: int | None


class RefreshTokenPersistence(Protocol):
    def store_refresh_token(
        self, request: StoreRefreshTokenRequest
    ) -> RefreshToken: ...

    def get_refresh_token_by_id(self, id: int) -> RefreshToken | None: ...
    def get_refresh_token(self, hashed_token: str) -> RefreshToken | None: ...
    def update_refresh_token(
        self, id: int, request: UpdateRefreshTokenRequest
    ) -> RefreshToken: ...
    def get_expired_refresh_tokens_ids(self) -> List[int]: ...
    def remove_refresh_token(self, id: int) -> None: ...
