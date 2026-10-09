from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from supplylens.domain.users import UserRole, UserStatus


@dataclass(frozen=True)
class User:
    id: UUID
    email: str
    role: UserRole
    status: UserStatus
    accepted_by: User | None
    pending_expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
