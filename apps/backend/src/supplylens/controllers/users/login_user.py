from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from supplylens.config import get_jwt_settings
from supplylens.controllers.users.types import User
from supplylens.port.persistence.users import UserPersistence, UserStatus
from supplylens.tools.encode_decode import encode_jwt
from supplylens.tools.encryption import hash_password, verify_password

from .exceptions import InvalidCredentialsError, UserPendingError
from .helpers import validate_email_address


@dataclass(frozen=True)
class LoginUserCommand:
    email: str
    password: str


@dataclass(frozen=True)
class LoginUserCommandResult:
    access_token: str
    token_type: str
    expires_in: int


def login_user(
    req: LoginUserCommand, persistence: UserPersistence
) -> LoginUserCommandResult:
    validated_email = validate_email_address(req.email)
    user = persistence.get_user_by_email(validated_email)
    if user is None:
        raise InvalidCredentialsError("Invalid email or password")

    is_password_valid, needs_rehash = verify_password(req.password, user.password_hash)
    if not is_password_valid:
        raise InvalidCredentialsError("Invalid email or password")

    if user.status != UserStatus.ACCEPTED:
        raise UserPendingError(f"User {validated_email} status is {user.status}")

    if needs_rehash:
        persistence.update_user_password(user.id, hash_password(req.password))

    payload = _create_access_token_payload(user, get_jwt_settings().access_ttl_seconds)
    access_token = encode_jwt(payload)
    return LoginUserCommandResult(
        access_token=access_token,
        token_type="Bearer",
        expires_in=get_jwt_settings().access_ttl_seconds,
    )


def _create_access_token_payload(user: User, ttl_seconds: int) -> dict:
    token_ttl = timedelta(seconds=ttl_seconds)
    expiration_time = datetime.now(timezone.utc) + token_ttl

    return {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value,
        "exp": expiration_time,
    }
