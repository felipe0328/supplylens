from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from supplylens.database.database import Base
from supplylens.domain.users import UserRole, UserStatus
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


def test_user_defaults_and_nullable_fields(session: Session) -> None:
    user = User(email="operator@example.com", password_hash="synthetic-hash")
    session.add(user)
    session.flush()

    assert isinstance(user.id, UUID)
    assert user.role is UserRole.OPERATOR
    assert user.status is UserStatus.PENDING
    assert user.created_at is not None
    assert user.updated_at is not None
    assert user.accepted_by is None
    assert user.pending_expires_at is None
    assert user.deleted_at is None


def test_user_defaults_apply_when_defaulted_fields_are_none(session: Session) -> None:
    user = User(
        email="operator@example.com",
        password_hash="synthetic-hash",
        role=None,
        status=None,
        created_at=None,
        updated_at=None,
    )
    session.add(user)
    session.flush()

    assert user.role is UserRole.OPERATOR
    assert user.status is UserStatus.PENDING
    assert user.created_at is not None
    assert user.updated_at is not None


@pytest.mark.parametrize("role", list(UserRole))
@pytest.mark.parametrize("status", list(UserStatus))
def test_user_persists_roles_and_statuses(
    session: Session, role: UserRole, status: UserStatus
) -> None:
    user = User(
        email="operator@example.com",
        password_hash="synthetic-hash",
        role=role,
        status=status,
    )
    session.add(user)
    session.flush()
    user_id = user.id
    session.commit()
    session.expunge_all()

    persisted_user = session.get(User, user_id)

    assert persisted_user is not None
    assert persisted_user.role is role
    assert persisted_user.status is status


def test_user_persists_optional_values(session: Session) -> None:
    approver = User(
        email="admin@example.com",
        password_hash="synthetic-hash",
        role=UserRole.ADMIN,
        status=UserStatus.ACCEPTED,
    )
    session.add(approver)
    session.flush()
    approver_id = approver.id
    pending_expires_at = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
    deleted_at = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
    user = User(
        email="operator@example.com",
        password_hash="synthetic-hash",
        accepted_by=approver_id,
        pending_expires_at=pending_expires_at,
        deleted_at=deleted_at,
    )
    session.add(user)
    session.flush()
    user_id = user.id
    session.commit()
    session.expunge_all()

    persisted_user = session.get(User, user_id)

    assert persisted_user is not None
    assert persisted_user.accepted_by == approver_id
    # SQLite does not preserve timezone information; PostgreSQL needs separate coverage.
    assert persisted_user.pending_expires_at == pending_expires_at.replace(tzinfo=None)
    assert persisted_user.deleted_at == deleted_at.replace(tzinfo=None)


def test_user_refreshes_updated_at_when_another_field_changes(session: Session) -> None:
    user = User(email="operator@example.com", password_hash="synthetic-hash")
    session.add(user)
    session.flush()
    user.updated_at = datetime(2020, 1, 1)
    session.flush()

    user.email = "renamed@example.com"
    session.flush()
    session.refresh(user)

    assert user.updated_at != datetime(2020, 1, 1)


def test_user_rejects_duplicate_email(session: Session) -> None:
    session.add(User(email="operator@example.com", password_hash="synthetic-hash"))
    session.flush()
    session.add(User(email="operator@example.com", password_hash="other-hash"))

    with pytest.raises(IntegrityError):
        session.flush()


def test_user_rejects_unknown_accepted_by(session: Session) -> None:
    session.add(
        User(
            email="operator@example.com",
            password_hash="synthetic-hash",
            accepted_by=UUID("00000000-0000-0000-0000-000000000099"),
        )
    )

    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize("field_name", ["email", "password_hash"])
def test_user_rejects_null_required_values(session: Session, field_name: str) -> None:
    user_values: dict[str, object] = {
        "email": "operator@example.com",
        "password_hash": "synthetic-hash",
    }
    user_values[field_name] = None
    session.add(User(**user_values))

    with pytest.raises(IntegrityError):
        session.flush()
