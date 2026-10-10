from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from supplylens.database.database import Base
from supplylens.models.refresh_token import RefreshToken
from supplylens.models.user import User


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(engine)

        with Session(engine) as database_session:
            yield database_session
    finally:
        engine.dispose()


@pytest.fixture
def user_id(session: Session) -> UUID:
    user = User(email="operator@example.com", password_hash="synthetic-hash")
    session.add(user)
    session.flush()
    return user.id


def test_refresh_token_defaults_and_nullable_fields(
    session: Session, user_id: UUID
) -> None:
    token = RefreshToken(
        user_id=user_id,
        hashed_token="synthetic-hash-current",
        expires_at=datetime(2026, 10, 17, 12, 0, tzinfo=UTC),
    )
    session.add(token)
    session.flush()

    assert isinstance(token.id, int)
    assert token.user_id == user_id
    assert token.hashed_token == "synthetic-hash-current"
    assert token.revoked_at is None
    assert token.replaced_by is None


def test_refresh_token_persists_optional_values(
    session: Session, user_id: UUID
) -> None:
    expires_at = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
    revoked_at = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
    current = RefreshToken(
        user_id=user_id,
        hashed_token="synthetic-hash-current",
        expires_at=expires_at,
    )
    session.add(current)
    session.flush()
    previous = RefreshToken(
        user_id=user_id,
        hashed_token="synthetic-hash-previous",
        expires_at=expires_at,
        revoked_at=revoked_at,
        replaced_by=current.id,
    )
    session.add(previous)
    session.flush()
    previous_id = previous.id
    current_id = current.id
    session.commit()
    session.expunge_all()

    persisted_previous = session.get(RefreshToken, previous_id)
    persisted_current = session.get(RefreshToken, current_id)

    assert persisted_previous is not None
    assert persisted_current is not None
    assert persisted_previous.user_id == user_id
    assert persisted_previous.replaced_by == current_id
    assert persisted_current.replaced_by is None
    # SQLite does not preserve timezone information; PostgreSQL needs separate coverage.
    assert persisted_previous.expires_at == expires_at.replace(tzinfo=None)
    assert persisted_previous.revoked_at == revoked_at.replace(tzinfo=None)


def test_refresh_token_allows_multiple_rows_for_one_user(
    session: Session, user_id: UUID
) -> None:
    expires_at = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
    session.add_all(
        [
            RefreshToken(
                user_id=user_id,
                hashed_token="synthetic-hash-a",
                expires_at=expires_at,
            ),
            RefreshToken(
                user_id=user_id,
                hashed_token="synthetic-hash-b",
                expires_at=expires_at,
            ),
        ]
    )
    session.flush()

    stored_count = session.scalar(
        select(func.count())
        .select_from(RefreshToken)
        .where(RefreshToken.user_id == user_id)
    )

    assert stored_count == 2


def test_refresh_token_rejects_duplicate_hashed_token(
    session: Session, user_id: UUID
) -> None:
    expires_at = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
    session.add(
        RefreshToken(
            user_id=user_id,
            hashed_token="synthetic-hash",
            expires_at=expires_at,
        )
    )
    session.flush()
    session.add(
        RefreshToken(
            user_id=user_id,
            hashed_token="synthetic-hash",
            expires_at=expires_at,
        )
    )

    with pytest.raises(IntegrityError):
        session.flush()


def test_refresh_token_rejects_unknown_user(session: Session) -> None:
    session.add(
        RefreshToken(
            user_id=UUID("00000000-0000-0000-0000-000000000099"),
            hashed_token="synthetic-hash",
            expires_at=datetime(2026, 10, 17, 12, 0, tzinfo=UTC),
        )
    )

    with pytest.raises(IntegrityError):
        session.flush()


def test_refresh_token_rejects_unknown_replaced_by(
    session: Session, user_id: UUID
) -> None:
    session.add(
        RefreshToken(
            user_id=user_id,
            hashed_token="synthetic-hash",
            expires_at=datetime(2026, 10, 17, 12, 0, tzinfo=UTC),
            replaced_by=999,
        )
    )

    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize("field_name", ["user_id", "hashed_token", "expires_at"])
def test_refresh_token_rejects_null_required_values(
    session: Session, user_id: UUID, field_name: str
) -> None:
    token_values: dict[str, object] = {
        "user_id": user_id,
        "hashed_token": "synthetic-hash",
        "expires_at": datetime(2026, 10, 17, 12, 0, tzinfo=UTC),
    }
    token_values[field_name] = None
    session.add(RefreshToken(**token_values))

    with pytest.raises(IntegrityError):
        session.flush()


def test_refresh_token_has_lookup_indexes(session: Session) -> None:
    bind = session.get_bind()
    indexes = inspect(bind).get_indexes("refresh_tokens")
    unique_constraints = inspect(bind).get_unique_constraints("refresh_tokens")

    assert any(
        index["column_names"] == ["user_id"] and not index["unique"]
        for index in indexes
    )
    assert any(
        index["column_names"] == ["expires_at"] and not index["unique"]
        for index in indexes
    )
    assert any(
        constraint["column_names"] == ["hashed_token"]
        for constraint in unique_constraints
    )
