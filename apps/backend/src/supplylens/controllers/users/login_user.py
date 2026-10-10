from dataclasses import dataclass
from typing import NoReturn

from argon2.exceptions import InvalidHashError, VerificationError

from supplylens.config import get_jwt_settings
from supplylens.domain.users import UserStatus
from supplylens.helpers.users import is_unexpired_pending
from supplylens.port.persistence.refresh_token import RefreshTokenPersistence
from supplylens.port.persistence.users import User as PortUser
from supplylens.port.persistence.users import UserPersistence
from supplylens.tools.encryption import hash_password, verify_password

from .constants import (
    ACCOUNT_NOT_AVAILABLE,
    ACCOUNT_STATUS_MESSAGES,
    INVALID_CREDENTIALS,
    TOKEN_TYPE,
)
from .exceptions import AccountNotAcceptedError, InvalidCredentialsError
from .session_tokens import create_access_token, create_refresh_token
from .validation import validate_email_address

_DUMMY_PASSWORD_HASH: str | None = None


@dataclass(frozen=True)
class LoginUserCommand:
    email: str
    password: str


@dataclass(frozen=True)
class LoginUserCommandResult:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


def login_user(
    req: LoginUserCommand,
    user_persistence: UserPersistence,
    refresh_token_persistence: RefreshTokenPersistence,
) -> LoginUserCommandResult:
    validated_email = validate_email_address(req.email)
    user = user_persistence.get_user_by_email(validated_email)
    if user is None:
        _reject_unknown_email(req.password)

    try:
        is_password_valid, needs_rehash = verify_password(
            req.password, user.password_hash
        )
    except InvalidHashError, VerificationError:
        raise InvalidCredentialsError(INVALID_CREDENTIALS) from None
    if not is_password_valid:
        raise InvalidCredentialsError(INVALID_CREDENTIALS)

    if user.status is not UserStatus.ACCEPTED:
        raise AccountNotAcceptedError(_account_not_accepted_message(user))

    if needs_rehash:
        user_persistence.update_user_password(user.id, hash_password(req.password))

    settings = get_jwt_settings()
    refresh_token, _token_id = create_refresh_token(
        user.id, refresh_token_persistence, settings.refresh_ttl_seconds
    )
    return LoginUserCommandResult(
        access_token=create_access_token(user, settings.access_ttl_seconds),
        refresh_token=refresh_token,
        token_type=TOKEN_TYPE,
        expires_in=settings.access_ttl_seconds,
    )


def _account_not_accepted_message(user: PortUser) -> str:
    if user.status is UserStatus.PENDING and not is_unexpired_pending(
        user.status, user.pending_expires_at
    ):
        return ACCOUNT_STATUS_MESSAGES[UserStatus.EXPIRED]
    return ACCOUNT_STATUS_MESSAGES.get(user.status, ACCOUNT_NOT_AVAILABLE)


def _reject_unknown_email(password: str) -> NoReturn:
    verify_password(password, _dummy_password_hash())
    raise InvalidCredentialsError(INVALID_CREDENTIALS)


def _dummy_password_hash() -> str:
    global _DUMMY_PASSWORD_HASH
    if _DUMMY_PASSWORD_HASH is None:
        _DUMMY_PASSWORD_HASH = hash_password("synthetic-login-placeholder")
    return _DUMMY_PASSWORD_HASH
