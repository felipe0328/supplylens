from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from supplylens.adapters.persistence.refresh_tokens import (
    RefreshTokenPersistenceAdapter,
)
from supplylens.database.database import Base
from supplylens.models.refresh_token import RefreshToken as RefreshTokenModel
from supplylens.models.user import User
from supplylens.port.persistence.refresh_token import (
    StoreRefreshTokenRequest,
    UpdateRefreshTokenRequest,
)

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
FUTURE = datetime(2099, 1, 1, tzinfo=UTC)
PAST = datetime(2020, 1, 1, tzinfo=UTC)
REVOKED_AT = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(engine)
        with Session(engine, autoflush=False) as database_session:
            database_session.add(
                User(
                    id=USER_ID,
                    email="operator@example.com",
                    password_hash="synthetic-hash",
                )
            )
            database_session.commit()
            yield database_session
    finally:
        engine.dispose()


def _store(
    adapter: RefreshTokenPersistenceAdapter,
    hashed_token: str,
    expires_at: datetime,
) -> int:
    stored = adapter.store_refresh_token(
        StoreRefreshTokenRequest(
            user_id=USER_ID,
            hashed_token=hashed_token,
            expires_at=expires_at,
        )
    )
    assert stored is not None
    return stored.id


def test_store_refresh_token_returns_the_new_row(session: Session) -> None:
    adapter = RefreshTokenPersistenceAdapter(session)

    stored = adapter.store_refresh_token(
        StoreRefreshTokenRequest(
            user_id=USER_ID,
            hashed_token="synthetic-hash-current",
            expires_at=FUTURE,
        )
    )

    assert stored is not None
    assert isinstance(stored.id, int)
    assert stored.user_id == USER_ID
    assert stored.hashed_token == "synthetic-hash-current"
    assert stored.revoked_at is None
    assert stored.replaced_by is None
    assert session.get(RefreshTokenModel, stored.id) is not None


def test_get_refresh_token_by_id_returns_none_when_missing(session: Session) -> None:
    assert RefreshTokenPersistenceAdapter(session).get_refresh_token_by_id(999) is None


def test_get_refresh_token_returns_a_revoked_unexpired_token(session: Session) -> None:
    adapter = RefreshTokenPersistenceAdapter(session)
    token_id = _store(adapter, "synthetic-hash-current", FUTURE)
    adapter.update_refresh_token(
        token_id,
        UpdateRefreshTokenRequest(revoked_at=REVOKED_AT, replaced_by=None),
    )

    loaded = adapter.get_refresh_token("synthetic-hash-current")

    assert loaded is not None
    assert loaded.id == token_id
    assert loaded.revoked_at is not None


def test_get_refresh_token_returns_an_expired_token(session: Session) -> None:
    adapter = RefreshTokenPersistenceAdapter(session)
    token_id = _store(adapter, "synthetic-hash-expired", PAST)

    loaded = adapter.get_refresh_token("synthetic-hash-expired")

    assert loaded is not None
    assert loaded.id == token_id


def test_get_refresh_token_returns_none_when_unknown(session: Session) -> None:
    assert (
        RefreshTokenPersistenceAdapter(session).get_refresh_token(
            "synthetic-hash-missing"
        )
        is None
    )


def test_get_refresh_token_by_id_returns_an_expired_token(session: Session) -> None:
    adapter = RefreshTokenPersistenceAdapter(session)
    token_id = _store(adapter, "synthetic-hash-expired", PAST)

    loaded = adapter.get_refresh_token_by_id(token_id)

    assert loaded is not None
    assert loaded.id == token_id


def test_update_refresh_token_sets_revoked_at_and_replaced_by(
    session: Session,
) -> None:
    adapter = RefreshTokenPersistenceAdapter(session)
    current_id = _store(adapter, "synthetic-hash-current", FUTURE)
    previous_id = _store(adapter, "synthetic-hash-previous", FUTURE)

    updated = adapter.update_refresh_token(
        previous_id,
        UpdateRefreshTokenRequest(revoked_at=REVOKED_AT, replaced_by=current_id),
    )

    assert updated is not None
    assert updated.replaced_by == current_id
    assert updated.revoked_at is not None


def test_commit_keeps_a_revocation(session: Session) -> None:
    adapter = RefreshTokenPersistenceAdapter(session)
    token_id = _store(adapter, "synthetic-hash-commit", FUTURE)
    adapter.update_refresh_token(
        token_id,
        UpdateRefreshTokenRequest(revoked_at=REVOKED_AT, replaced_by=None),
    )

    adapter.commit()
    session.expire_all()

    loaded = adapter.get_refresh_token_by_id(token_id)
    assert loaded is not None
    assert loaded.revoked_at is not None


def test_update_refresh_token_keeps_the_recorded_successor(session: Session) -> None:
    adapter = RefreshTokenPersistenceAdapter(session)
    current_id = _store(adapter, "synthetic-hash-current", FUTURE)
    previous_id = _store(adapter, "synthetic-hash-previous", FUTURE)
    other_id = _store(adapter, "synthetic-hash-other", FUTURE)
    adapter.update_refresh_token(
        previous_id,
        UpdateRefreshTokenRequest(revoked_at=REVOKED_AT, replaced_by=current_id),
    )

    second_write = adapter.update_refresh_token(
        previous_id,
        UpdateRefreshTokenRequest(revoked_at=REVOKED_AT, replaced_by=other_id),
    )

    assert second_write is None
    loaded = adapter.get_refresh_token_by_id(previous_id)
    assert loaded is not None
    assert loaded.replaced_by == current_id
    assert loaded.revoked_at is not None


def test_update_refresh_token_missing_id_raises(session: Session) -> None:
    with pytest.raises(ValueError, match="not found"):
        RefreshTokenPersistenceAdapter(session).update_refresh_token(
            999,
            UpdateRefreshTokenRequest(revoked_at=REVOKED_AT, replaced_by=None),
        )


def test_get_expired_refresh_tokens_ids_returns_smaller_ids_first(
    session: Session,
) -> None:
    adapter = RefreshTokenPersistenceAdapter(session)
    first_id = _store(adapter, "synthetic-hash-first", FUTURE)
    second_id = _store(adapter, "synthetic-hash-second", FUTURE)
    third_id = _store(adapter, "synthetic-hash-third", FUTURE)
    current_id = _store(adapter, "synthetic-hash-current", FUTURE)
    for token_id in (third_id, first_id):
        stored = session.get(RefreshTokenModel, token_id)
        assert stored is not None
        stored.expires_at = PAST
    session.flush()

    expired_ids = adapter.get_expired_refresh_tokens_ids()

    assert expired_ids == [first_id, third_id]
    assert second_id not in expired_ids
    assert current_id not in expired_ids


def test_get_expired_refresh_tokens_ids_keeps_ancestors_of_a_live_token(
    session: Session,
) -> None:
    adapter = RefreshTokenPersistenceAdapter(session)
    oldest_id = _store(adapter, "synthetic-hash-oldest", PAST)
    middle_id = _store(adapter, "synthetic-hash-middle", PAST)
    current_id = _store(adapter, "synthetic-hash-current", FUTURE)
    unrelated_id = _store(adapter, "synthetic-hash-unrelated", PAST)
    adapter.update_refresh_token(
        middle_id,
        UpdateRefreshTokenRequest(revoked_at=REVOKED_AT, replaced_by=current_id),
    )
    adapter.update_refresh_token(
        oldest_id,
        UpdateRefreshTokenRequest(revoked_at=REVOKED_AT, replaced_by=middle_id),
    )

    expired_ids = adapter.get_expired_refresh_tokens_ids()

    assert expired_ids == [unrelated_id]
    assert oldest_id not in expired_ids
    assert middle_id not in expired_ids


def test_remove_refresh_token_deletes_the_row(session: Session) -> None:
    adapter = RefreshTokenPersistenceAdapter(session)
    token_id = _store(adapter, "synthetic-hash-current", FUTURE)

    adapter.remove_refresh_token(token_id)
    session.flush()

    assert session.get(RefreshTokenModel, token_id) is None
    assert adapter.get_refresh_token_by_id(token_id) is None


def test_remove_refresh_token_missing_id_raises(session: Session) -> None:
    with pytest.raises(ValueError, match="not found"):
        RefreshTokenPersistenceAdapter(session).remove_refresh_token(999)


def test_removing_expired_tokens_in_returned_order_preserves_replaced_by(
    session: Session,
) -> None:
    adapter = RefreshTokenPersistenceAdapter(session)
    previous_id = _store(adapter, "synthetic-hash-previous", PAST)
    current_id = _store(adapter, "synthetic-hash-current", PAST)
    adapter.update_refresh_token(
        previous_id,
        UpdateRefreshTokenRequest(revoked_at=REVOKED_AT, replaced_by=current_id),
    )

    for token_id in adapter.get_expired_refresh_tokens_ids():
        adapter.remove_refresh_token(token_id)
        session.flush()

    assert session.scalars(select(RefreshTokenModel.id)).all() == []


def test_removing_the_newer_expired_token_first_hits_the_foreign_key(
    session: Session,
) -> None:
    adapter = RefreshTokenPersistenceAdapter(session)
    previous_id = _store(adapter, "synthetic-hash-previous", PAST)
    current_id = _store(adapter, "synthetic-hash-current", PAST)
    adapter.update_refresh_token(
        previous_id,
        UpdateRefreshTokenRequest(revoked_at=REVOKED_AT, replaced_by=current_id),
    )

    adapter.remove_refresh_token(current_id)

    with pytest.raises(IntegrityError):
        session.flush()
