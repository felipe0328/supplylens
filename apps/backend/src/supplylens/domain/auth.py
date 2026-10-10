from dataclasses import dataclass
from uuid import UUID

from supplylens.domain.users import UserRole


@dataclass(frozen=True)
class AccessPrincipal:
    user_id: UUID
    role: UserRole
