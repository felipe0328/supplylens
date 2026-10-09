from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
import pytest
from argon2 import PasswordHasher
from argon2.profiles import CHEAPEST

from supplylens.config import JWTSettings
from supplylens.controllers.users.exceptions import (
    AccountNotAcceptedError,
    InvalidCredentialsError,
    InvalidEmailAddressError,
)
from supplylens.controllers.users.login_user import LoginUserCommand, login_user
from supplylens.domain.users import UserRole, UserStatus
from supplylens.port.persistence.users import User as PortUser
from supplylens.tools.encryption import hash_password, verify_password

USER_ID = UUID("12345678-1234-5678-1234-567812345678")
CREATED_AT = datetime(2026, 10, 7, tzinfo=UTC)
PASSWORD = "Synthetic1"
JWT_SECRET = "synthetic-jwt-secret-with-32-characters"
ACCESS_TTL_SECONDS = 900


class FakeUserPersistence:
    def __init__(self, existing: PortUser | None = None) -> None:
        self._existing = existing
        self.updated: list[tuple[UUID, str]] = []

    def get_user_by_email(self, email: str) -> PortUser | None:
        if self._existing is None or self._existing.email != email:
            return None
        return self._existing

    def update_user_password(self, user_id: UUID, password_hash: str) -> PortUser:
        self.updated.append((user_id, password_hash))
        assert self._existing is not None
        return self._existing


def _user(**overrides: object) -> PortUser:
    values: dict[str, object] = {
        "id": USER_ID,
        "email": "operator@example.com",
        "password_hash": hash_password(PASSWORD),
        "role": UserRole.OPERATOR,
        "status": UserStatus.ACCEPTED,
        "accepted_by": None,
        "pending_expires_at": None,
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
        "deleted_at": None,
    }
    values.update(overrides)
    return PortUser(**values)  # type: ignore[arg-type]


def _command(**overrides: object) -> LoginUserCommand:
    values: dict[str, object] = {
        "email": "Operator@Example.com",
        "password": PASSWORD,
    }
    values.update(overrides)
    return LoginUserCommand(**values)  # type: ignore[arg-type]


@pytest.fixture
def jwt_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = JWTSettings(secret=JWT_SECRET, access_ttl_seconds=ACCESS_TTL_SECONDS)
    monkeypatch.setattr(
        "supplylens.controllers.users.login_user.get_jwt_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        "supplylens.tools.encode_decode.get_jwt_settings",
        lambda: settings,
    )


def test_login_user_returns_a_short_lived_access_token(jwt_settings: None) -> None:
    persistence = FakeUserPersistence(_user())
    before = datetime.now(UTC)

    result = login_user(_command(), persistence)

    assert result.token_type == "Bearer"
    assert result.expires_in == ACCESS_TTL_SECONDS
    assert persistence.updated == []
    payload = jwt.decode(result.access_token, JWT_SECRET, algorithms=["HS256"])
    assert payload["sub"] == str(USER_ID)
    assert payload["role"] == "OPERATOR"
    assert "email" not in payload
    assert "status" not in payload
    after = datetime.now(UTC)
    expires_at = datetime.fromtimestamp(payload["exp"], UTC)
    assert expires_at >= before + timedelta(seconds=ACCESS_TTL_SECONDS - 1)
    assert expires_at <= after + timedelta(seconds=ACCESS_TTL_SECONDS)


def test_login_user_embeds_the_admin_role(jwt_settings: None) -> None:
    persistence = FakeUserPersistence(_user(role=UserRole.ADMIN))

    result = login_user(_command(), persistence)

    payload = jwt.decode(result.access_token, JWT_SECRET, algorithms=["HS256"])
    assert payload["role"] == "ADMIN"


def test_login_user_replaces_a_stale_password_hash(jwt_settings: None) -> None:
    password_hash = PasswordHasher.from_parameters(CHEAPEST).hash(PASSWORD)
    persistence = FakeUserPersistence(_user(password_hash=password_hash))

    login_user(_command(), persistence)

    assert len(persistence.updated) == 1
    assert persistence.updated[0][0] == USER_ID
    assert verify_password(PASSWORD, persistence.updated[0][1]) == (True, False)


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("missing@example.com", PASSWORD),
        ("Operator@Example.com", "Synthetic2"),
    ],
)
def test_login_user_hides_unknown_emails_and_wrong_passwords(
    jwt_settings: None,
    email: str,
    password: str,
) -> None:
    persistence = FakeUserPersistence(_user())

    with pytest.raises(InvalidCredentialsError, match="^Invalid email or password.$"):
        login_user(_command(email=email, password=password), persistence)

    assert persistence.updated == []


@pytest.mark.parametrize(
    "status",
    [
        UserStatus.PENDING,
        UserStatus.REJECTED,
        UserStatus.EXPIRED,
        UserStatus.DELETED,
    ],
)
def test_login_user_wrong_password_does_not_reveal_account_status(
    jwt_settings: None,
    status: UserStatus,
) -> None:
    persistence = FakeUserPersistence(_user(status=status))

    with pytest.raises(InvalidCredentialsError, match="^Invalid email or password.$"):
        login_user(_command(password="Synthetic2"), persistence)

    assert persistence.updated == []


@pytest.mark.parametrize(
    "password_hash",
    [
        "not-an-argon2-hash",
        "$argon2id$v=19$m=65536,t=3,p=4$aaaa$bbbb",
    ],
)
def test_login_user_hides_an_unreadable_password_hash(
    jwt_settings: None,
    password_hash: str,
) -> None:
    persistence = FakeUserPersistence(_user(password_hash=password_hash))

    with pytest.raises(InvalidCredentialsError, match="^Invalid email or password.$"):
        login_user(_command(), persistence)

    assert persistence.updated == []


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (UserStatus.PENDING, "This account is waiting for approval."),
        (UserStatus.REJECTED, "This account was not approved."),
        (UserStatus.EXPIRED, "This registration expired. Register again."),
        (UserStatus.DELETED, "This account is not available."),
    ],
)
def test_login_user_rejects_accounts_that_are_not_accepted(
    jwt_settings: None,
    status: UserStatus,
    message: str,
) -> None:
    persistence = FakeUserPersistence(_user(status=status))

    with pytest.raises(AccountNotAcceptedError, match=f"^{message}$"):
        login_user(_command(), persistence)

    assert persistence.updated == []


def test_login_user_rejects_an_invalid_email_before_lookup(jwt_settings: None) -> None:
    persistence = FakeUserPersistence(_user())

    with pytest.raises(InvalidEmailAddressError):
        login_user(_command(email="not-an-email"), persistence)

    assert persistence.updated == []
