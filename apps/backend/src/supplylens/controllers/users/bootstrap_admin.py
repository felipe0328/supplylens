import enum
from dataclasses import dataclass
from typing import TypeGuard

from supplylens.controllers.users.types import User
from supplylens.domain.users import UserRole, UserStatus
from supplylens.port.persistence.users import CreateUserRequest, UserPersistence
from supplylens.port.persistence.users import User as PortUser
from supplylens.tools.encryption import hash_password

from .helpers import validate_email_address, validate_password
from .mappers import map_port_user_to_controller_user


class BootstrapAdminOutcome(enum.Enum):
    CREATED = "created"
    UPDATED = "updated"
    ALREADY_EXISTS = "already_exists"


@dataclass(frozen=True)
class BootstrapAdminCommand:
    email: str
    password: str


@dataclass(frozen=True)
class BootstrapAdminCommandResult:
    user: User
    outcome: BootstrapAdminOutcome


def bootstrap_admin_user(
    req: BootstrapAdminCommand, persistence: UserPersistence
) -> BootstrapAdminCommandResult:
    """Create one accepted admin, or leave an existing accepted admin unchanged."""
    email = validate_email_address(req.email)
    password = validate_password(req.password)
    existing_user = persistence.get_user_by_email(email)
    if _is_accepted_admin(existing_user):
        return BootstrapAdminCommandResult(
            user=map_port_user_to_controller_user(existing_user),
            outcome=BootstrapAdminOutcome.ALREADY_EXISTS,
        )

    request = CreateUserRequest(email=email, password_hash=hash_password(password))
    if existing_user is None:
        stored = persistence.create_super_admin_user(request)
        outcome = BootstrapAdminOutcome.CREATED
    else:
        stored = persistence.retry_super_admin_creation(existing_user.id, request)
        outcome = BootstrapAdminOutcome.UPDATED
    return BootstrapAdminCommandResult(
        user=map_port_user_to_controller_user(stored),
        outcome=outcome,
    )


def _is_accepted_admin(user: PortUser | None) -> TypeGuard[PortUser]:
    return (
        user is not None
        and user.role is UserRole.ADMIN
        and user.status is UserStatus.ACCEPTED
    )
