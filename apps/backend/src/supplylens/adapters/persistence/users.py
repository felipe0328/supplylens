from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from supplylens.domain.users import DuplicateUserEmailError, UserRole, UserStatus
from supplylens.helpers.users import is_unexpired_pending
from supplylens.models.user import User as UserModel
from supplylens.port.persistence.users import (
    CreateUserRequest,
    User,
    UserPersistence,
)

from .mappers import map_model_user_to_abstraction
from .refresh_tokens import revoke_refresh_tokens_for_user


def _require_user(user: User | None) -> User:
    if user is None:
        raise RuntimeError("User row could not be mapped.")
    return user


class UserPersistenceAdapter(UserPersistence):
    _session: Session

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_user(self, user: CreateUserRequest) -> User:
        new_user = UserModel(
            email=user.email,
            password_hash=user.password_hash,
            role=UserRole.OPERATOR,
            status=UserStatus.PENDING,
            accepted_by=None,
            pending_expires_at=datetime.now(UTC) + timedelta(days=2),
            deleted_at=None,
        )

        def _insert_user() -> None:
            self._session.add(new_user)

        self._flush_unique_email(user.email, _insert_user)
        return self._map_user(new_user)

    def create_super_admin_user(self, user: CreateUserRequest) -> User:
        new_user = UserModel(
            email=user.email,
            password_hash=user.password_hash,
            role=UserRole.ADMIN,
            status=UserStatus.ACCEPTED,
            accepted_by=None,
            pending_expires_at=None,
            deleted_at=None,
        )

        def _insert_user() -> None:
            self._session.add(new_user)

        self._flush_unique_email(user.email, _insert_user)
        return self._map_user(new_user)

    def retry_super_admin_creation(
        self, user_id: UUID, user: CreateUserRequest
    ) -> User:
        existing_user = self._session.get(UserModel, user_id, with_for_update=True)
        if existing_user is None:
            raise ValueError(f"User with id {user_id} not found")

        def _reopen_account() -> None:
            existing_user.email = user.email
            existing_user.password_hash = user.password_hash
            existing_user.role = UserRole.ADMIN
            existing_user.status = UserStatus.ACCEPTED
            existing_user.accepted_by = None
            existing_user.pending_expires_at = None
            existing_user.deleted_at = None

        self._flush_unique_email(user.email, _reopen_account)
        revoke_refresh_tokens_for_user(self._session, user_id)
        return self._map_user(existing_user)

    def retry_user_creation(self, user_id: UUID, user: CreateUserRequest) -> User:
        existing_user = self._session.get(UserModel, user_id, with_for_update=True)
        if existing_user is None:
            raise ValueError(f"User with id {user_id} not found")
        if existing_user.status is UserStatus.ACCEPTED:
            raise ValueError(f"User with id {user_id} is already accepted")
        if is_unexpired_pending(existing_user.status, existing_user.pending_expires_at):
            raise ValueError(f"User with id {user_id} is already pending")

        def _reopen_account() -> None:
            existing_user.email = user.email
            existing_user.password_hash = user.password_hash
            existing_user.role = UserRole.OPERATOR
            existing_user.status = UserStatus.PENDING
            existing_user.accepted_by = None
            existing_user.pending_expires_at = datetime.now(UTC) + timedelta(days=2)
            existing_user.deleted_at = None

        self._flush_unique_email(user.email, _reopen_account)
        revoke_refresh_tokens_for_user(self._session, user_id)
        return self._map_user(existing_user)

    def get_user_by_email(self, email: str) -> User | None:
        user = self._session.scalar(select(UserModel).where(UserModel.email == email))
        if user is None:
            return None
        return self._map_user(user)

    def get_user_by_id(self, id: UUID) -> User | None:
        user = self._session.get(UserModel, id)
        if user is None:
            return None
        return self._map_user(user)

    def update_user_email(self, id: UUID, email: str) -> User:
        existing_user = self._session.get(UserModel, id, with_for_update=True)
        if existing_user is None:
            raise ValueError(f"User with id {id} not found")

        def _assign_email() -> None:
            existing_user.email = email

        self._flush_unique_email(email, _assign_email)
        return self._map_user(existing_user)

    def update_user_password(self, id: UUID, password_hash: str) -> User:
        user = self._session.get(UserModel, id, with_for_update=True)
        if user is None:
            raise ValueError(f"User with id {id} not found")
        user.password_hash = password_hash
        self._session.flush()
        return self._map_user(user)

    def change_user_approval_status(
        self, id: UUID, accepted_by: UUID, status: UserStatus
    ) -> User:
        user = self._session.get(UserModel, id, with_for_update=True)
        if user is None:
            raise ValueError(f"User with id {id} not found")
        actor = self._require_accepted_admin(accepted_by)
        user.accepted_by = actor.id
        user.status = status
        if status is UserStatus.PENDING:
            user.pending_expires_at = datetime.now(UTC) + timedelta(days=2)
        else:
            user.pending_expires_at = None
        if status is not UserStatus.ACCEPTED:
            revoke_refresh_tokens_for_user(self._session, id)
        self._session.flush()
        return self._map_user(user)

    def change_user_role(self, id: UUID, requested_by: UUID, role: UserRole) -> User:
        user = self._session.get(UserModel, id, with_for_update=True)
        if user is None:
            raise ValueError(f"User with id {id} not found")
        if user.status is not UserStatus.ACCEPTED:
            raise ValueError(f"User with id {id} is not accepted")
        self._require_accepted_admin(requested_by)
        user.role = role
        self._session.flush()
        return self._map_user(user)

    def delete_user(self, id: UUID, requested_by: UUID) -> None:
        user = self._session.get(UserModel, id, with_for_update=True)
        if user is None:
            raise ValueError(f"User with id {id} not found")
        self._require_accepted_admin(requested_by)
        user.deleted_at = func.now()
        user.status = UserStatus.DELETED
        user.pending_expires_at = None
        revoke_refresh_tokens_for_user(self._session, id)
        self._session.flush()

    def _map_user(self, model_user: UserModel) -> User:
        accepted_by = None
        if model_user.accepted_by is not None:
            accepted_by = self._session.get(UserModel, model_user.accepted_by)
            if accepted_by is None:
                raise ValueError(f"User with id {model_user.accepted_by} not found")
        return _require_user(map_model_user_to_abstraction(model_user, accepted_by))

    def _require_accepted_admin(self, actor_id: UUID) -> UserModel:
        actor = self._session.get(UserModel, actor_id)
        if actor is None:
            raise ValueError(f"User with id {actor_id} not found")
        if actor.role is not UserRole.ADMIN or actor.status is not UserStatus.ACCEPTED:
            raise ValueError(f"User with id {actor_id} is not an accepted admin")
        return actor

    def _flush_unique_email(self, email: str, apply_change: Callable[[], None]) -> None:
        """Flush inside a savepoint so a duplicate email does not abort the caller."""
        try:
            with self._session.begin_nested():
                apply_change()
                self._session.flush()
        except IntegrityError as exc:
            raise DuplicateUserEmailError(email) from exc
