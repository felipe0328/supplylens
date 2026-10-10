from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from supplylens.domain.users import UserRole, UserStatus


@dataclass(frozen=True)
class UserBase:
    email: str


@dataclass(frozen=True)
class User(UserBase):
    id: UUID
    password_hash: str
    role: UserRole
    status: UserStatus
    accepted_by: User | None
    pending_expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


@dataclass(frozen=True)
class CreateUserRequest:
    email: str
    password_hash: str


class UserPersistence(Protocol):
    def create_user(self, user: CreateUserRequest) -> User: ...
    def create_super_admin_user(self, user: CreateUserRequest) -> User: ...
    def retry_user_creation(self, user_id: UUID, user: CreateUserRequest) -> User: ...
    def retry_super_admin_creation(
        self, user_id: UUID, user: CreateUserRequest
    ) -> User: ...
    def get_user_by_email(self, email: str) -> User | None: ...
    def get_user_by_id(self, id: UUID) -> User | None: ...
    def update_user_email(self, id: UUID, email: str) -> User: ...
    def update_user_password(self, id: UUID, password_hash: str) -> User: ...
    def change_user_approval_status(
        self, id: UUID, accepted_by: UUID, status: UserStatus
    ) -> User: ...
    def change_user_role(
        self, id: UUID, requested_by: UUID, role: UserRole
    ) -> User: ...
    def delete_user(self, id: UUID, requested_by: UUID) -> None: ...
