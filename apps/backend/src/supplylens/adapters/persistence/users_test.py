from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from supplylens.adapters.persistence.users import (
    UserPersistenceAdapter,
    _require_user,
)
from supplylens.database.database import Base
from supplylens.domain.users import DuplicateUserEmailError, UserRole, UserStatus
from supplylens.models.user import User as UserModel
from supplylens.port.persistence.users import CreateUserRequest

USER_ID = UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    try:
        Base.metadata.create_all(engine)
        with Session(engine, autoflush=False) as database_session:
            yield database_session
    finally:
        engine.dispose()


def _request(email: str = "operator@example.com") -> CreateUserRequest:
    return CreateUserRequest(email=email, password_hash="synthetic-hash")


def _accept_as_admin(session: Session, user_id: UUID) -> None:
    stored = session.get(UserModel, user_id)
    assert stored is not None
    stored.role = UserRole.ADMIN
    stored.status = UserStatus.ACCEPTED
    session.flush()


def test_create_user_stores_a_pending_account_for_48_hours(session: Session) -> None:
    created = UserPersistenceAdapter(session).create_user(_request())

    assert created.email == "operator@example.com"
    assert created.password_hash == "synthetic-hash"
    assert created.role is UserRole.OPERATOR
    assert created.status is UserStatus.PENDING
    assert created.accepted_by is None
    assert created.deleted_at is None
    assert created.pending_expires_at is not None
    expiry = created.pending_expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    remaining = expiry - datetime.now(UTC)
    assert timedelta(hours=47) < remaining < timedelta(hours=49)


def test_get_user_by_email_returns_none_when_the_email_is_missing(
    session: Session,
) -> None:
    assert (
        UserPersistenceAdapter(session).get_user_by_email("missing@example.com") is None
    )


def test_get_user_by_email_includes_the_accepting_user(session: Session) -> None:
    adapter = UserPersistenceAdapter(session)
    approver = adapter.create_user(_request("admin@example.com"))
    _accept_as_admin(session, approver.id)
    operator = adapter.create_user(_request())
    stored_operator = session.get(UserModel, operator.id)
    assert stored_operator is not None
    stored_operator.accepted_by = approver.id
    session.flush()

    loaded = adapter.get_user_by_email("operator@example.com")

    assert loaded is not None
    assert loaded.accepted_by is not None
    assert loaded.accepted_by.id == approver.id
    assert loaded.accepted_by.accepted_by is None


def test_retry_user_creation_reuses_the_same_row(session: Session) -> None:
    adapter = UserPersistenceAdapter(session)
    created = adapter.create_user(_request())
    stored = session.get(UserModel, created.id)
    assert stored is not None
    stored.status = UserStatus.EXPIRED
    stored.accepted_by = None
    session.flush()

    stored.role = UserRole.ADMIN
    session.flush()

    retried = adapter.retry_user_creation(
        created.id,
        CreateUserRequest(
            email="operator@example.com",
            password_hash="replacement-hash",
        ),
    )

    assert retried.id == created.id
    assert retried.password_hash == "replacement-hash"
    assert retried.role is UserRole.OPERATOR
    assert retried.status is UserStatus.PENDING
    assert retried.accepted_by is None
    assert retried.deleted_at is None
    assert session.scalar(select(func.count()).select_from(UserModel)) == 1


def test_retry_user_creation_reopens_a_deleted_account(session: Session) -> None:
    adapter = UserPersistenceAdapter(session)
    created = adapter.create_user(_request())
    stored = session.get(UserModel, created.id)
    assert stored is not None
    stored.status = UserStatus.DELETED
    stored.deleted_at = datetime.now(UTC)
    session.flush()

    retried = adapter.retry_user_creation(created.id, _request())

    assert retried.id == created.id
    assert retried.status is UserStatus.PENDING
    assert retried.deleted_at is None


def test_retry_user_creation_refuses_an_accepted_account(session: Session) -> None:
    adapter = UserPersistenceAdapter(session)
    created = adapter.create_user(_request())
    stored = session.get(UserModel, created.id)
    assert stored is not None
    stored.status = UserStatus.ACCEPTED
    session.flush()

    with pytest.raises(ValueError, match="already accepted"):
        adapter.retry_user_creation(created.id, _request())


def test_create_user_rejects_a_duplicate_email(session: Session) -> None:
    adapter = UserPersistenceAdapter(session)
    adapter.create_user(_request())

    with pytest.raises(DuplicateUserEmailError):
        adapter.create_user(_request())

    session.commit()
    assert adapter.get_user_by_email("operator@example.com") is not None
    assert session.scalar(select(func.count()).select_from(UserModel)) == 1
    created = adapter.create_user(_request("other@example.com"))
    assert created.role is UserRole.OPERATOR


def test_retry_user_creation_missing_id_raises(session: Session) -> None:
    with pytest.raises(ValueError, match="not found"):
        UserPersistenceAdapter(session).retry_user_creation(USER_ID, _request())


def test_retry_user_creation_refuses_an_open_pending_account(session: Session) -> None:
    adapter = UserPersistenceAdapter(session)
    created = adapter.create_user(_request())

    with pytest.raises(ValueError, match="already pending"):
        adapter.retry_user_creation(created.id, _request())


def test_get_user_by_email_rejects_a_missing_approver(session: Session) -> None:
    adapter = UserPersistenceAdapter(session)
    created = adapter.create_user(_request())
    stored = session.get(UserModel, created.id)
    assert stored is not None
    stored.accepted_by = USER_ID
    session.flush()

    with pytest.raises(ValueError, match="not found"):
        adapter.get_user_by_email("operator@example.com")


def test_update_user_email_replaces_the_address_and_keeps_the_approver(
    session: Session,
) -> None:
    adapter = UserPersistenceAdapter(session)
    approver = adapter.create_user(_request("admin@example.com"))
    created = adapter.create_user(_request())
    stored = session.get(UserModel, created.id)
    assert stored is not None
    stored.accepted_by = approver.id
    session.flush()

    updated = adapter.update_user_email(created.id, "renamed@example.com")

    assert updated.id == created.id
    assert updated.email == "renamed@example.com"
    assert updated.accepted_by is not None
    assert updated.accepted_by.id == approver.id


def test_update_user_email_missing_id_raises(session: Session) -> None:
    with pytest.raises(ValueError, match="not found"):
        UserPersistenceAdapter(session).update_user_email(
            USER_ID, "missing@example.com"
        )


def test_update_user_email_rejects_a_duplicate_and_keeps_the_original(
    session: Session,
) -> None:
    adapter = UserPersistenceAdapter(session)
    adapter.create_user(_request())
    other = adapter.create_user(_request("other@example.com"))

    with pytest.raises(DuplicateUserEmailError):
        adapter.update_user_email(other.id, "operator@example.com")

    stored = session.get(UserModel, other.id)
    assert stored is not None
    assert stored.email == "other@example.com"
    assert adapter.get_user_by_email("other@example.com") is not None


def test_update_user_password_replaces_the_hash(session: Session) -> None:
    adapter = UserPersistenceAdapter(session)
    created = adapter.create_user(_request())

    stored = session.get(UserModel, created.id)
    assert stored is not None
    approver = adapter.create_user(_request("admin@example.com"))
    stored.accepted_by = approver.id
    session.flush()

    updated = adapter.update_user_password(created.id, "replacement-hash")

    assert updated.password_hash == "replacement-hash"
    assert updated.id == created.id
    assert updated.accepted_by is not None
    assert updated.accepted_by.id == approver.id


def test_update_user_password_missing_id_raises(session: Session) -> None:
    with pytest.raises(ValueError, match="not found"):
        UserPersistenceAdapter(session).update_user_password(
            USER_ID,
            "replacement-hash",
        )


def test_change_user_approval_status_records_the_admin(session: Session) -> None:
    adapter = UserPersistenceAdapter(session)
    admin = adapter.create_user(_request("admin@example.com"))
    _accept_as_admin(session, admin.id)
    operator = adapter.create_user(_request())

    changed = adapter.change_user_approval_status(
        operator.id,
        admin.id,
        UserStatus.ACCEPTED,
    )

    assert changed.status is UserStatus.ACCEPTED
    assert changed.accepted_by is not None
    assert changed.accepted_by.id == admin.id
    assert changed.accepted_by.role is UserRole.ADMIN
    stored = session.get(UserModel, operator.id)
    assert stored is not None
    assert stored.accepted_by == admin.id
    assert stored.pending_expires_at is None


def test_change_user_approval_status_reopens_a_pending_window(session: Session) -> None:
    adapter = UserPersistenceAdapter(session)
    admin = adapter.create_user(_request("admin@example.com"))
    _accept_as_admin(session, admin.id)
    operator = adapter.create_user(_request())
    stored_operator = session.get(UserModel, operator.id)
    assert stored_operator is not None
    stored_operator.status = UserStatus.EXPIRED
    stored_operator.pending_expires_at = None
    session.flush()

    changed = adapter.change_user_approval_status(
        operator.id,
        admin.id,
        UserStatus.PENDING,
    )

    assert changed.status is UserStatus.PENDING
    assert changed.accepted_by is not None
    assert changed.accepted_by.id == admin.id
    assert changed.pending_expires_at is not None
    expiry = changed.pending_expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    remaining = expiry - datetime.now(UTC)
    assert timedelta(hours=47) < remaining < timedelta(hours=49)


def test_change_user_approval_status_missing_user_raises(session: Session) -> None:
    with pytest.raises(ValueError, match="not found"):
        UserPersistenceAdapter(session).change_user_approval_status(
            USER_ID,
            USER_ID,
            UserStatus.ACCEPTED,
        )


def test_change_user_approval_status_missing_admin_raises(session: Session) -> None:
    adapter = UserPersistenceAdapter(session)
    operator = adapter.create_user(_request())

    with pytest.raises(ValueError, match=str(USER_ID)):
        adapter.change_user_approval_status(
            operator.id,
            USER_ID,
            UserStatus.ACCEPTED,
        )


def test_change_user_approval_status_rejects_a_non_admin(session: Session) -> None:
    adapter = UserPersistenceAdapter(session)
    operator = adapter.create_user(_request())
    other = adapter.create_user(_request("other@example.com"))

    with pytest.raises(ValueError, match="not an accepted admin"):
        adapter.change_user_approval_status(
            operator.id,
            other.id,
            UserStatus.ACCEPTED,
        )
    stored = session.get(UserModel, operator.id)
    assert stored is not None
    assert stored.status is UserStatus.PENDING
    assert stored.accepted_by is None


def test_change_user_approval_status_rejects_an_unaccepted_admin(
    session: Session,
) -> None:
    adapter = UserPersistenceAdapter(session)
    admin = adapter.create_user(_request("admin@example.com"))
    operator = adapter.create_user(_request())
    stored_admin = session.get(UserModel, admin.id)
    assert stored_admin is not None
    stored_admin.role = UserRole.ADMIN
    session.flush()

    with pytest.raises(ValueError, match="not an accepted admin"):
        adapter.change_user_approval_status(
            operator.id,
            admin.id,
            UserStatus.ACCEPTED,
        )

    stored = session.get(UserModel, operator.id)
    assert stored is not None
    assert stored.status is UserStatus.PENDING


def test_change_user_role_promotes_an_accepted_operator(session: Session) -> None:
    adapter = UserPersistenceAdapter(session)
    admin = adapter.create_user(_request("admin@example.com"))
    _accept_as_admin(session, admin.id)
    operator = adapter.create_user(_request())
    stored_operator = session.get(UserModel, operator.id)
    assert stored_operator is not None
    stored_operator.status = UserStatus.ACCEPTED
    stored_operator.accepted_by = admin.id
    session.flush()

    changed = adapter.change_user_role(operator.id, admin.id, UserRole.ADMIN)

    assert changed.role is UserRole.ADMIN
    assert changed.status is UserStatus.ACCEPTED
    assert changed.accepted_by is not None
    assert changed.accepted_by.id == admin.id


def test_change_user_role_missing_user_raises(session: Session) -> None:
    with pytest.raises(ValueError, match="not found"):
        UserPersistenceAdapter(session).change_user_role(
            USER_ID,
            USER_ID,
            UserRole.ADMIN,
        )


def test_change_user_role_rejects_a_user_who_is_not_accepted(session: Session) -> None:
    adapter = UserPersistenceAdapter(session)
    admin = adapter.create_user(_request("admin@example.com"))
    _accept_as_admin(session, admin.id)
    operator = adapter.create_user(_request())

    with pytest.raises(ValueError, match="not accepted"):
        adapter.change_user_role(operator.id, admin.id, UserRole.ADMIN)

    stored = session.get(UserModel, operator.id)
    assert stored is not None
    assert stored.role is UserRole.OPERATOR


def test_change_user_role_missing_admin_raises(session: Session) -> None:
    adapter = UserPersistenceAdapter(session)
    operator = adapter.create_user(_request())
    stored = session.get(UserModel, operator.id)
    assert stored is not None
    stored.status = UserStatus.ACCEPTED
    session.flush()

    with pytest.raises(ValueError, match="not found"):
        adapter.change_user_role(operator.id, USER_ID, UserRole.ADMIN)


def test_change_user_role_rejects_a_non_admin(session: Session) -> None:
    adapter = UserPersistenceAdapter(session)
    operator = adapter.create_user(_request())
    other = adapter.create_user(_request("other@example.com"))
    for user_id in (operator.id, other.id):
        stored = session.get(UserModel, user_id)
        assert stored is not None
        stored.status = UserStatus.ACCEPTED
    session.flush()

    with pytest.raises(ValueError, match="not an accepted admin"):
        adapter.change_user_role(operator.id, other.id, UserRole.ADMIN)


def test_change_user_role_rejects_an_unaccepted_admin(session: Session) -> None:
    adapter = UserPersistenceAdapter(session)
    admin = adapter.create_user(_request("admin@example.com"))
    operator = adapter.create_user(_request())
    stored_admin = session.get(UserModel, admin.id)
    stored_operator = session.get(UserModel, operator.id)
    assert stored_admin is not None
    assert stored_operator is not None
    stored_admin.role = UserRole.ADMIN
    stored_operator.status = UserStatus.ACCEPTED
    session.flush()

    with pytest.raises(ValueError, match="not an accepted admin"):
        adapter.change_user_role(operator.id, admin.id, UserRole.ADMIN)


def test_retry_user_creation_rejects_a_duplicate_email(session: Session) -> None:
    adapter = UserPersistenceAdapter(session)
    adapter.create_user(_request())
    other = adapter.create_user(_request("other@example.com"))
    stored = session.get(UserModel, other.id)
    assert stored is not None
    stored.status = UserStatus.EXPIRED
    session.flush()

    with pytest.raises(DuplicateUserEmailError):
        adapter.retry_user_creation(other.id, _request())

    stored = session.get(UserModel, other.id)
    assert stored is not None
    assert stored.email == "other@example.com"
    assert stored.status is UserStatus.EXPIRED
    assert adapter.get_user_by_email("operator@example.com") is not None


def test_delete_user_marks_the_account_deleted(session: Session) -> None:
    adapter = UserPersistenceAdapter(session)
    admin = adapter.create_user(_request("admin@example.com"))
    _accept_as_admin(session, admin.id)
    created = adapter.create_user(_request())

    adapter.delete_user(created.id, admin.id)

    stored = session.get(UserModel, created.id)
    assert stored is not None
    assert stored.status is UserStatus.DELETED
    assert stored.deleted_at is not None
    assert stored.pending_expires_at is None


def test_delete_user_missing_id_raises(session: Session) -> None:
    with pytest.raises(ValueError, match="not found"):
        UserPersistenceAdapter(session).delete_user(USER_ID, USER_ID)


def test_delete_user_rejects_a_non_admin(session: Session) -> None:
    adapter = UserPersistenceAdapter(session)
    operator = adapter.create_user(_request())
    other = adapter.create_user(_request("other@example.com"))

    with pytest.raises(ValueError, match="not an accepted admin"):
        adapter.delete_user(operator.id, other.id)

    stored = session.get(UserModel, operator.id)
    assert stored is not None
    assert stored.status is UserStatus.PENDING
    assert stored.deleted_at is None


def test_require_user_rejects_an_unmapped_row() -> None:
    with pytest.raises(RuntimeError, match="could not be mapped"):
        _require_user(None)


def test_create_super_admin_user_stores_an_accepted_admin(session: Session) -> None:
    created = UserPersistenceAdapter(session).create_super_admin_user(
        _request("admin@example.com")
    )

    assert created.email == "admin@example.com"
    assert created.password_hash == "synthetic-hash"
    assert created.role is UserRole.ADMIN
    assert created.status is UserStatus.ACCEPTED
    assert created.accepted_by is None
    assert created.pending_expires_at is None
    assert created.deleted_at is None
    assert session.scalar(select(func.count()).select_from(UserModel)) == 1


def test_create_super_admin_user_rejects_a_duplicate_email(session: Session) -> None:
    adapter = UserPersistenceAdapter(session)
    adapter.create_super_admin_user(_request("admin@example.com"))

    with pytest.raises(DuplicateUserEmailError):
        adapter.create_super_admin_user(_request("admin@example.com"))

    assert session.scalar(select(func.count()).select_from(UserModel)) == 1


def test_retry_super_admin_creation_promotes_the_existing_row(session: Session) -> None:
    adapter = UserPersistenceAdapter(session)
    created = adapter.create_user(_request("admin@example.com"))
    stored = session.get(UserModel, created.id)
    assert stored is not None
    stored.role = UserRole.OPERATOR
    stored.status = UserStatus.DELETED
    stored.deleted_at = datetime.now(UTC)
    stored.accepted_by = created.id
    session.flush()

    retried = adapter.retry_super_admin_creation(
        created.id,
        CreateUserRequest(email="admin@example.com", password_hash="replacement-hash"),
    )

    assert retried.id == created.id
    assert retried.password_hash == "replacement-hash"
    assert retried.role is UserRole.ADMIN
    assert retried.status is UserStatus.ACCEPTED
    assert retried.accepted_by is None
    assert retried.pending_expires_at is None
    assert retried.deleted_at is None
    assert session.scalar(select(func.count()).select_from(UserModel)) == 1


def test_retry_super_admin_creation_missing_id_raises(session: Session) -> None:
    with pytest.raises(ValueError, match="not found"):
        UserPersistenceAdapter(session).retry_super_admin_creation(USER_ID, _request())


def test_retry_super_admin_creation_rejects_a_duplicate_email(session: Session) -> None:
    adapter = UserPersistenceAdapter(session)
    adapter.create_user(_request())
    other = adapter.create_user(_request("other@example.com"))
    stored = session.get(UserModel, other.id)
    assert stored is not None
    stored.status = UserStatus.EXPIRED
    session.flush()

    with pytest.raises(DuplicateUserEmailError):
        adapter.retry_super_admin_creation(other.id, _request())

    stored = session.get(UserModel, other.id)
    assert stored is not None
    assert stored.email == "other@example.com"
    assert stored.status is UserStatus.EXPIRED
    assert adapter.get_user_by_email("operator@example.com") is not None
