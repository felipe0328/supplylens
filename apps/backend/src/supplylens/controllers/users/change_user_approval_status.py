from dataclasses import dataclass
from uuid import UUID

from supplylens.domain.users import UserRole, UserStatus
from supplylens.helpers.users import is_unexpired_pending
from supplylens.port.persistence.users import User as PortUser
from supplylens.port.persistence.users import UserPersistence

from .constants import (
    APPROVAL_FORBIDDEN,
    USER_NOT_AWAITING_APPROVAL,
    USER_NOT_FOUND,
)
from .exceptions import (
    ApprovalForbiddenError,
    UserNotAwaitingApprovalError,
    UserNotFoundError,
)
from .mappers import map_port_user_to_controller_user
from .types import User


@dataclass(frozen=True)
class ChangeUserApprovalStatusCommand:
    user_id: UUID
    requested_by: UUID
    status: UserStatus


@dataclass(frozen=True)
class ChangeUserApprovalStatusResult:
    user: User


def change_user_approval_status(
    req: ChangeUserApprovalStatusCommand, user_persistence: UserPersistence
) -> ChangeUserApprovalStatusResult:
    if req.status not in {UserStatus.ACCEPTED, UserStatus.REJECTED}:
        raise ValueError(f"Unsupported approval status: {req.status}")

    target = user_persistence.get_user_by_id(req.user_id)
    if target is None:
        raise UserNotFoundError(USER_NOT_FOUND)
    if not is_unexpired_pending(target.status, target.pending_expires_at):
        raise UserNotAwaitingApprovalError(USER_NOT_AWAITING_APPROVAL)

    actor = user_persistence.get_user_by_id(req.requested_by)
    _require_accepted_admin(actor)

    updated_user = user_persistence.change_user_approval_status(
        req.user_id, req.requested_by, req.status
    )
    return ChangeUserApprovalStatusResult(
        user=map_port_user_to_controller_user(updated_user)
    )


def _require_accepted_admin(actor: PortUser | None) -> None:
    if (
        actor is None
        or actor.role is not UserRole.ADMIN
        or actor.status is not UserStatus.ACCEPTED
    ):
        raise ApprovalForbiddenError(APPROVAL_FORBIDDEN)
