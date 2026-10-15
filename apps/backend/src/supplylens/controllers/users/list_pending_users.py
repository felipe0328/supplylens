from dataclasses import dataclass

from supplylens.port.persistence.users import UserPersistence

from .mappers import map_port_user_to_controller_user
from .types import User


@dataclass(frozen=True)
class ListPendingUsersCommand:
    limit: int
    offset: int


@dataclass(frozen=True)
class ListPendingUsersResult:
    users: list[User]


def list_pending_users(
    req: ListPendingUsersCommand, user_persistence: UserPersistence
) -> ListPendingUsersResult:
    users = user_persistence.list_pending_users(req.limit, req.offset)

    mapped_users = [map_port_user_to_controller_user(user) for user in users]
    return ListPendingUsersResult(users=mapped_users)
