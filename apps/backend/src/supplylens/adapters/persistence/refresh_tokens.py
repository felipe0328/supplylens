from datetime import UTC, datetime
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from supplylens.models.refresh_token import RefreshToken as RefreshTokenModel
from supplylens.port.persistence.refresh_token import (
    RefreshToken,
    RefreshTokenPersistence,
    StoreRefreshTokenRequest,
    UpdateRefreshTokenRequest,
)

from .mappers import map_model_refresh_token_to_abstraction


class RefreshTokenPersistenceAdapter(RefreshTokenPersistence):
    _session: Session

    def __init__(self, session: Session) -> None:
        self._session = session

    def store_refresh_token(self, request: StoreRefreshTokenRequest) -> RefreshToken:
        new_refresh_token = RefreshTokenModel(
            user_id=request.user_id,
            hashed_token=request.hashed_token,
            expires_at=request.expires_at,
        )

        self._session.add(new_refresh_token)
        self._session.flush()
        return map_model_refresh_token_to_abstraction(new_refresh_token)

    def get_refresh_token_by_id(self, id: int) -> RefreshToken | None:
        refresh_token = self._session.get(RefreshTokenModel, id)
        return map_model_refresh_token_to_abstraction(refresh_token)

    def get_refresh_token(self, hashed_token: str) -> RefreshToken | None:
        statement = select(RefreshTokenModel).where(
            RefreshTokenModel.hashed_token == hashed_token,
            RefreshTokenModel.expires_at > datetime.now(UTC),
        )
        refresh_token = self._session.scalar(statement)
        return map_model_refresh_token_to_abstraction(refresh_token)

    def update_refresh_token(
        self, id: int, request: UpdateRefreshTokenRequest
    ) -> RefreshToken:
        existing_token = self._session.get(RefreshTokenModel, id)
        if existing_token is None:
            raise ValueError(f"Refresh token with id {id} not found")

        existing_token.revoked_at = request.revoked_at
        existing_token.replaced_by = request.replaced_by

        self._session.flush()
        return map_model_refresh_token_to_abstraction(existing_token)

    def get_expired_refresh_tokens_ids(self) -> List[int]:
        statement = (
            select(RefreshTokenModel.id)
            .where(RefreshTokenModel.expires_at < datetime.now(UTC))
            .order_by(RefreshTokenModel.id.asc())
        )
        expired_tokens = self._session.scalars(statement).all()
        return [token for token in expired_tokens]

    def remove_refresh_token(self, id: int) -> None:
        refresh_token = self._session.get(RefreshTokenModel, id)
        if refresh_token is None:
            raise ValueError(f"Refresh token with id {id} not found")

        self._session.delete(refresh_token)
