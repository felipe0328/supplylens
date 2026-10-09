from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from supplylens.controllers.users.exceptions import (
    InvalidPasswordError,
    UserAlreadyExistsError,
    UserPendingError,
)
from supplylens.controllers.users.register import RegisterUserCommand, register_user
from supplylens.domain.users import (
    DuplicateUserEmailError,
    UserRole,
    UserStatus,
)
from supplylens.port.persistence.users import CreateUserRequest
from supplylens.port.persistence.users import User as PortUser
from supplylens.tools.encryption import verify_password

USER_ID = UUID("12345678-1234-5678-1234-567812345678")
CREATED_AT = datetime(2026, 10, 7, tzinfo=UTC)
PASSWORD = "Synthetic1"


class FakeUserPersistence:
    def __init__(
        self,
        existing: PortUser | list[PortUser | None] | None = None,
    ) -> None:
        self._existing = existing if isinstance(existing, list) else [existing]
        self._lookups = 0
        self.created: list[CreateUserRequest] = []
        self.retried: list[tuple[UUID, CreateUserRequest]] = []
        self.retry_error: Exception | None = None
        self.create_error: Exception | None = None

    def get_user_by_email(self, email: str) -> PortUser | None:
        index = min(self._lookups, len(self._existing) - 1)
        self._lookups += 1
        user = self._existing[index]
        if user is None or user.email != email:
            return None
        return user

    def create_user(self, user: CreateUserRequest) -> PortUser:
        if self.create_error is not None:
            raise self.create_error
        self.created.append(user)
        return _user(
            email=user.email,
            password_hash=user.password_hash,
            role=UserRole.OPERATOR,
            status=UserStatus.PENDING,
        )

    def retry_user_creation(self, user_id: UUID, user: CreateUserRequest) -> PortUser:
        if self.retry_error is not None:
            raise self.retry_error
        self.retried.append((user_id, user))
        return _user(
            id=user_id,
            email=user.email,
            password_hash=user.password_hash,
            role=UserRole.OPERATOR,
            status=UserStatus.PENDING,
            accepted_by=None,
            deleted_at=None,
        )


def _user(**overrides: object) -> PortUser:
    values: dict[str, object] = {
        "id": USER_ID,
        "email": "operator@example.com",
        "password_hash": "stored-hash",
        "role": UserRole.OPERATOR,
        "status": UserStatus.PENDING,
        "accepted_by": None,
        "pending_expires_at": datetime.now(UTC) + timedelta(hours=1),
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
        "deleted_at": None,
    }
    values.update(overrides)
    return PortUser(**values)  # type: ignore[arg-type]


def _command(**overrides: object) -> RegisterUserCommand:
    values: dict[str, object] = {
        "email": "Operator@Example.com",
        "password": PASSWORD,
    }
    values.update(overrides)
    return RegisterUserCommand(**values)  # type: ignore[arg-type]


def test_register_user_creates_a_pending_account() -> None:
    persistence = FakeUserPersistence()

    result = register_user(_command(), persistence)

    assert result.user.id == USER_ID
    assert result.user.email == "operator@example.com"
    assert result.user.status is UserStatus.PENDING
    assert not hasattr(result.user, "password_hash")
    assert len(persistence.created) == 1
    assert persistence.retried == []
    assert verify_password(PASSWORD, persistence.created[0].password_hash)[0]


def test_register_user_reuses_an_expired_account() -> None:
    persistence = FakeUserPersistence(_user(status=UserStatus.EXPIRED))

    result = register_user(_command(password="Synthetic2"), persistence)

    assert result.user.id == USER_ID
    assert result.user.status is UserStatus.PENDING
    assert persistence.created == []
    assert persistence.retried[0][0] == USER_ID
    assert verify_password("Synthetic2", persistence.retried[0][1].password_hash)[0]


@pytest.mark.parametrize("status", [UserStatus.REJECTED, UserStatus.EXPIRED])
def test_register_user_reuses_rejected_and_expired_accounts(status: UserStatus) -> None:
    persistence = FakeUserPersistence(_user(status=status, pending_expires_at=None))

    register_user(_command(), persistence)

    assert len(persistence.retried) == 1
    assert persistence.created == []


def test_register_user_reuses_a_pending_account_after_expiry() -> None:
    persistence = FakeUserPersistence(
        _user(pending_expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )

    register_user(_command(), persistence)

    assert len(persistence.retried) == 1


def test_register_user_rejects_an_open_pending_account() -> None:
    naive_expiry = (datetime.now(UTC) + timedelta(hours=2)).replace(tzinfo=None)
    persistence = FakeUserPersistence(_user(pending_expires_at=naive_expiry))

    with pytest.raises(UserPendingError, match="waiting for approval"):
        register_user(_command(), persistence)

    assert persistence.created == []
    assert persistence.retried == []


def test_register_user_rejects_pending_without_an_expiry() -> None:
    persistence = FakeUserPersistence(_user(pending_expires_at=None))

    with pytest.raises(UserPendingError):
        register_user(_command(), persistence)


def test_register_user_rejects_an_accepted_account() -> None:
    persistence = FakeUserPersistence(_user(status=UserStatus.ACCEPTED))

    with pytest.raises(UserAlreadyExistsError, match="Log in instead"):
        register_user(_command(), persistence)

    assert persistence.retried == []


def test_register_user_reuses_a_deleted_account() -> None:
    persistence = FakeUserPersistence(
        _user(status=UserStatus.DELETED, deleted_at=datetime.now(UTC))
    )

    result = register_user(_command(), persistence)

    assert result.user.id == USER_ID
    assert result.user.status is UserStatus.PENDING
    assert result.user.deleted_at is None
    assert len(persistence.retried) == 1
    assert persistence.created == []


def test_register_user_turns_a_duplicate_insert_into_a_login_conflict() -> None:
    persistence = FakeUserPersistence()
    persistence.create_error = DuplicateUserEmailError("operator@example.com")

    with pytest.raises(UserAlreadyExistsError, match="Log in instead"):
        register_user(_command(), persistence)

    assert persistence.retried == []


def test_register_user_reports_pending_when_a_duplicate_insert_loses_the_race() -> None:
    persistence = FakeUserPersistence([None, _user()])
    persistence.create_error = DuplicateUserEmailError("operator@example.com")

    with pytest.raises(UserPendingError, match="waiting for approval"):
        register_user(_command(), persistence)

    assert persistence.retried == []


def test_register_user_reuses_an_expired_account_after_a_duplicate_insert() -> None:
    persistence = FakeUserPersistence([None, _user(status=UserStatus.EXPIRED)])
    persistence.create_error = DuplicateUserEmailError("operator@example.com")

    result = register_user(_command(), persistence)

    assert result.user.status is UserStatus.PENDING
    assert persistence.created == []
    assert len(persistence.retried) == 1


def test_register_user_rereads_when_retry_loses_a_race() -> None:
    persistence = FakeUserPersistence(
        [
            _user(status=UserStatus.EXPIRED),
            _user(status=UserStatus.ACCEPTED),
        ]
    )
    persistence.retry_error = ValueError("already accepted")

    with pytest.raises(UserAlreadyExistsError, match="Log in instead"):
        register_user(_command(), persistence)


def test_register_user_reraises_when_the_account_disappears_during_retry() -> None:
    persistence = FakeUserPersistence(
        [
            _user(status=UserStatus.EXPIRED),
            None,
        ]
    )
    persistence.retry_error = ValueError("already accepted")

    with pytest.raises(ValueError, match="already accepted"):
        register_user(_command(), persistence)


def test_register_user_includes_the_approver_when_reusing_an_account() -> None:
    approver_id = UUID("87654321-4321-8765-4321-876543218765")
    approver = _user(
        id=approver_id,
        email="admin@example.com",
        role=UserRole.ADMIN,
        status=UserStatus.ACCEPTED,
        pending_expires_at=None,
    )
    persistence = FakeUserPersistence(_user(status=UserStatus.EXPIRED))

    def retry(user_id: UUID, request: CreateUserRequest) -> PortUser:
        persistence.retried.append((user_id, request))
        return _user(
            id=user_id,
            email=request.email,
            password_hash=request.password_hash,
            role=UserRole.OPERATOR,
            status=UserStatus.PENDING,
            accepted_by=approver,
            deleted_at=None,
        )

    persistence.retry_user_creation = retry  # type: ignore[method-assign]

    result = register_user(_command(), persistence)

    assert result.user.accepted_by is not None
    assert result.user.accepted_by.id == approver_id
    assert result.user.accepted_by.email == "admin@example.com"
    assert result.user.accepted_by.accepted_by is None


def test_register_user_rejects_a_weak_password_before_lookup() -> None:
    persistence = FakeUserPersistence()

    with pytest.raises(InvalidPasswordError):
        register_user(_command(password="short1A"), persistence)

    assert persistence._lookups == 0
