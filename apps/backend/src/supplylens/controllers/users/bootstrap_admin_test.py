from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from supplylens.controllers.users.bootstrap_admin import (
    BootstrapAdminCommand,
    BootstrapAdminOutcome,
    bootstrap_admin_user,
)
from supplylens.controllers.users.exceptions import (
    InvalidEmailAddressError,
    InvalidPasswordError,
)
from supplylens.domain.users import UserRole, UserStatus
from supplylens.port.persistence.users import CreateUserRequest
from supplylens.port.persistence.users import User as PortUser
from supplylens.tools.encryption import verify_password

USER_ID = UUID("12345678-1234-5678-1234-567812345678")
CREATED_AT = datetime(2026, 10, 7, tzinfo=UTC)
PASSWORD = "Synthetic1"


class FakeUserPersistence:
    def __init__(self, existing: PortUser | None = None) -> None:
        self.existing = existing
        self.created: list[CreateUserRequest] = []
        self.retried: list[tuple[UUID, CreateUserRequest]] = []

    def get_user_by_email(self, email: str) -> PortUser | None:
        if self.existing is None or self.existing.email != email:
            return None
        return self.existing

    def create_super_admin_user(self, user: CreateUserRequest) -> PortUser:
        self.created.append(user)
        return _user(
            email=user.email,
            password_hash=user.password_hash,
            role=UserRole.ADMIN,
            status=UserStatus.ACCEPTED,
            pending_expires_at=None,
        )

    def retry_super_admin_creation(
        self, user_id: UUID, user: CreateUserRequest
    ) -> PortUser:
        self.retried.append((user_id, user))
        return _user(
            id=user_id,
            email=user.email,
            password_hash=user.password_hash,
            role=UserRole.ADMIN,
            status=UserStatus.ACCEPTED,
            pending_expires_at=None,
            deleted_at=None,
        )


def _user(**overrides: object) -> PortUser:
    values: dict[str, object] = {
        "id": USER_ID,
        "email": "admin@example.com",
        "password_hash": "stored-hash",
        "role": UserRole.ADMIN,
        "status": UserStatus.ACCEPTED,
        "accepted_by": None,
        "pending_expires_at": None,
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
        "deleted_at": None,
    }
    values.update(overrides)
    return PortUser(**values)  # type: ignore[arg-type]


def _command(**overrides: object) -> BootstrapAdminCommand:
    values: dict[str, object] = {
        "email": "Admin@Example.com",
        "password": PASSWORD,
    }
    values.update(overrides)
    return BootstrapAdminCommand(**values)  # type: ignore[arg-type]


def test_bootstrap_admin_user_creates_an_accepted_admin() -> None:
    persistence = FakeUserPersistence()

    result = bootstrap_admin_user(_command(), persistence)

    assert result.outcome is BootstrapAdminOutcome.CREATED
    assert result.user.email == "admin@example.com"
    assert result.user.role is UserRole.ADMIN
    assert result.user.status is UserStatus.ACCEPTED
    assert result.user.pending_expires_at is None
    assert persistence.retried == []
    assert len(persistence.created) == 1
    assert persistence.created[0].email == "admin@example.com"
    assert verify_password(PASSWORD, persistence.created[0].password_hash)[0] is True


def test_bootstrap_admin_user_leaves_an_accepted_admin_unchanged() -> None:
    persistence = FakeUserPersistence(_user())

    result = bootstrap_admin_user(_command(), persistence)

    assert result.outcome is BootstrapAdminOutcome.ALREADY_EXISTS
    assert result.user.id == USER_ID
    assert result.user.email == "admin@example.com"
    assert result.user.role is UserRole.ADMIN
    assert result.user.status is UserStatus.ACCEPTED
    assert persistence.created == []
    assert persistence.retried == []


@pytest.mark.parametrize(
    ("role", "status"),
    [
        (UserRole.OPERATOR, UserStatus.PENDING),
        (UserRole.OPERATOR, UserStatus.REJECTED),
        (UserRole.OPERATOR, UserStatus.EXPIRED),
        (UserRole.OPERATOR, UserStatus.DELETED),
        (UserRole.OPERATOR, UserStatus.ACCEPTED),
        (UserRole.ADMIN, UserStatus.PENDING),
    ],
)
def test_bootstrap_admin_user_reopens_any_other_existing_account(
    role: UserRole, status: UserStatus
) -> None:
    persistence = FakeUserPersistence(
        _user(
            role=role,
            status=status,
            pending_expires_at=datetime.now(UTC) + timedelta(hours=1),
            deleted_at=datetime.now(UTC),
        )
    )

    result = bootstrap_admin_user(_command(), persistence)

    assert result.outcome is BootstrapAdminOutcome.UPDATED
    assert result.user.id == USER_ID
    assert result.user.role is UserRole.ADMIN
    assert result.user.status is UserStatus.ACCEPTED
    assert persistence.created == []
    assert len(persistence.retried) == 1
    assert persistence.retried[0][0] == USER_ID
    assert verify_password(PASSWORD, persistence.retried[0][1].password_hash)[0]


def test_bootstrap_admin_user_rejects_an_invalid_email() -> None:
    persistence = FakeUserPersistence()

    with pytest.raises(InvalidEmailAddressError):
        bootstrap_admin_user(_command(email="not-an-email"), persistence)

    assert persistence.created == []
    assert persistence.retried == []


def test_bootstrap_admin_user_rejects_an_invalid_password() -> None:
    persistence = FakeUserPersistence()

    with pytest.raises(InvalidPasswordError):
        bootstrap_admin_user(_command(password="short"), persistence)

    assert persistence.created == []
    assert persistence.retried == []
