from dataclasses import dataclass

from supplylens.controllers.users.types import User
from supplylens.domain.users import DuplicateUserEmailError, UserStatus
from supplylens.helpers.users import is_unexpired_pending
from supplylens.port.persistence.users import (
    CreateUserRequest,
    UserPersistence,
)
from supplylens.port.persistence.users import User as PortUser
from supplylens.tools.encryption import hash_password

from .exceptions import UserAlreadyExistsError, UserPendingError
from .helpers import validate_email_address, validate_password
from .mappers import map_port_user_to_controller_user


@dataclass(frozen=True)
class RegisterUserCommand:
    email: str
    password: str


@dataclass(frozen=True)
class RegisterUserCommandResult:
    user: User


def register_user(
    req: RegisterUserCommand, persistence: UserPersistence
) -> RegisterUserCommandResult:
    validated_email = validate_email_address(req.email)
    validated_password = validate_password(req.password)

    existing_user = persistence.get_user_by_email(validated_email)
    if existing_user is not None:
        _raise_unless_reusable(existing_user)
        return _retry_registration(
            existing_user,
            _create_request(validated_email, validated_password),
            persistence,
        )

    request = _create_request(validated_email, validated_password)
    try:
        user = persistence.create_user(user=request)
    except DuplicateUserEmailError as exc:
        current_user = persistence.get_user_by_email(validated_email)
        if current_user is None:
            raise UserAlreadyExistsError(
                "An account with this email already exists. Log in instead."
            ) from exc
        _raise_unless_reusable(current_user)
        return _retry_registration(current_user, request, persistence)
    return RegisterUserCommandResult(user=map_port_user_to_controller_user(user))


def _retry_registration(
    existing_user: PortUser, request: CreateUserRequest, persistence: UserPersistence
) -> RegisterUserCommandResult:
    try:
        reused_user = persistence.retry_user_creation(existing_user.id, request)
    except ValueError as exc:
        current_user = persistence.get_user_by_email(request.email)
        if current_user is not None:
            _raise_unless_reusable(current_user)
        raise exc
    return RegisterUserCommandResult(user=map_port_user_to_controller_user(reused_user))


def _create_request(email: str, password: str) -> CreateUserRequest:
    return CreateUserRequest(
        email=email,
        password_hash=hash_password(password),
    )


def _raise_unless_reusable(existing_user: PortUser) -> None:
    if is_unexpired_pending(existing_user.status, existing_user.pending_expires_at):
        raise UserPendingError("This email is already waiting for approval.")
    if existing_user.status is UserStatus.ACCEPTED:
        raise UserAlreadyExistsError(
            "An account with this email already exists. Log in instead."
        )
