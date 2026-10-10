import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import NoReturn

from argon2.exceptions import InvalidHashError, VerificationError

from supplylens.config import get_jwt_settings
from supplylens.domain.users import UserStatus
from supplylens.helpers.users import is_unexpired_pending
from supplylens.port.persistence.refresh_token import (
    RefreshTokenPersistence,
    StoreRefreshTokenRequest,
)
from supplylens.port.persistence.users import User as PortUser
from supplylens.port.persistence.users import UserPersistence
from supplylens.tools.encode_decode import encode_jwt
from supplylens.tools.encryption import hash_password, verify_password
from supplylens.tools.token_hash import hash_token

from .exceptions import AccountNotAcceptedError, InvalidCredentialsError
from .validation import validate_email_address

_INVALID_CREDENTIALS = "Invalid email or password."
_DUMMY_PASSWORD_HASH: str | None = None
_STATUS_MESSAGES = {
    UserStatus.PENDING: "This account is waiting for approval.",
    UserStatus.REJECTED: "This account was not approved.",
    UserStatus.EXPIRED: "This registration expired. Register again.",
    UserStatus.DELETED: "This account is not available.",
}


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
        raise InvalidCredentialsError(_INVALID_CREDENTIALS) from None
    if not is_password_valid:
        raise InvalidCredentialsError(_INVALID_CREDENTIALS)

    if user.status is not UserStatus.ACCEPTED:
        raise AccountNotAcceptedError(_account_not_accepted_message(user))

    if needs_rehash:
        user_persistence.update_user_password(user.id, hash_password(req.password))

    settings = get_jwt_settings()
    access_token = encode_jwt(
        _create_access_token_payload(user, settings.access_ttl_seconds)
    )
    refresh_token = secrets.token_urlsafe(32)
    refresh_token_persistence.store_refresh_token(
        StoreRefreshTokenRequest(
            user_id=user.id,
            hashed_token=hash_token(refresh_token),
            expires_at=datetime.now(timezone.utc)
            + timedelta(seconds=settings.refresh_ttl_seconds),
        )
    )
    return LoginUserCommandResult(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="Bearer",
        expires_in=settings.access_ttl_seconds,
    )


def _account_not_accepted_message(user: PortUser) -> str:
    if user.status is UserStatus.PENDING and not is_unexpired_pending(
        user.status, user.pending_expires_at
    ):
        return _STATUS_MESSAGES[UserStatus.EXPIRED]
    return _STATUS_MESSAGES.get(user.status, "This account is not available.")


def _reject_unknown_email(password: str) -> NoReturn:
    verify_password(password, _dummy_password_hash())
    raise InvalidCredentialsError(_INVALID_CREDENTIALS)


def _dummy_password_hash() -> str:
    global _DUMMY_PASSWORD_HASH
    if _DUMMY_PASSWORD_HASH is None:
        _DUMMY_PASSWORD_HASH = hash_password("synthetic-login-placeholder")
    return _DUMMY_PASSWORD_HASH


def _create_access_token_payload(user: PortUser, ttl_seconds: int) -> dict:
    expiration_time = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    return {
        "sub": str(user.id),
        "role": user.role.value,
        "exp": expiration_time,
    }
