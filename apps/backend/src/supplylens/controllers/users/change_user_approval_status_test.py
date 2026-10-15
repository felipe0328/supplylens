from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from supplylens.controllers.users.change_user_approval_status import (
    ChangeUserApprovalStatusCommand,
    change_user_approval_status,
)
from supplylens.controllers.users.exceptions import (
    ApprovalForbiddenError,
    UserNotAwaitingApprovalError,
    UserNotFoundError,
)
from supplylens.domain.users import UserRole, UserStatus
from supplylens.port.persistence.users import User as PortUser

USER_ID = UUID("12345678-1234-5678-1234-567812345678")
ADMIN_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
OTHER_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
CREATED_AT = datetime(2026, 10, 7, tzinfo=UTC)
PENDING_EXPIRES_AT = datetime.now(UTC) + timedelta(hours=1)


class FakeUserPersistence:
    def __init__(
        self,
        *,
        target: PortUser | None = None,
        actor: PortUser | None = None,
    ) -> None:
        self._users = {user.id: user for user in (target, actor) if user is not None}
        self.calls: list[tuple[UUID, UUID, UserStatus]] = []

    def get_user_by_id(self, id: UUID) -> PortUser | None:
        return self._users.get(id)

    def change_user_approval_status(
        self, id: UUID, accepted_by: UUID, status: UserStatus
    ) -> PortUser:
        self.calls.append((id, accepted_by, status))
        target = self._users[id]
        actor = self._users[accepted_by]
        return PortUser(
            id=target.id,
            email=target.email,
            password_hash=target.password_hash,
            role=target.role,
            status=status,
            accepted_by=actor,
            pending_expires_at=None,
            created_at=target.created_at,
            updated_at=target.updated_at,
            deleted_at=None,
        )


def _admin(**overrides: object) -> PortUser:
    values: dict[str, object] = {
        "id": ADMIN_ID,
        "email": "admin@example.com",
        "password_hash": "admin-hash",
        "role": UserRole.ADMIN,
        "status": UserStatus.ACCEPTED,
        "accepted_by": None,
        "pending_expires_at": None,
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
        "deleted_at": None,
    }
    values.update(overrides)
    return PortUser(**values)  # type: ignore[arg-type]


def _pending_user(**overrides: object) -> PortUser:
    values: dict[str, object] = {
        "id": USER_ID,
        "email": "operator@example.com",
        "password_hash": "stored-hash",
        "role": UserRole.OPERATOR,
        "status": UserStatus.PENDING,
        "accepted_by": None,
        "pending_expires_at": PENDING_EXPIRES_AT,
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
        "deleted_at": None,
    }
    values.update(overrides)
    return PortUser(**values)  # type: ignore[arg-type]


def test_change_user_approval_status_accepts_a_pending_user() -> None:
    persistence = FakeUserPersistence(target=_pending_user(), actor=_admin())

    result = change_user_approval_status(
        ChangeUserApprovalStatusCommand(
            user_id=USER_ID,
            requested_by=ADMIN_ID,
            status=UserStatus.ACCEPTED,
        ),
        persistence,
    )

    assert persistence.calls == [(USER_ID, ADMIN_ID, UserStatus.ACCEPTED)]
    assert result.user.id == USER_ID
    assert result.user.status is UserStatus.ACCEPTED
    assert result.user.accepted_by is not None
    assert result.user.accepted_by.id == ADMIN_ID
    assert not hasattr(result.user, "password_hash")


def test_change_user_approval_status_rejects_a_pending_user() -> None:
    persistence = FakeUserPersistence(target=_pending_user(), actor=_admin())

    result = change_user_approval_status(
        ChangeUserApprovalStatusCommand(
            user_id=USER_ID,
            requested_by=ADMIN_ID,
            status=UserStatus.REJECTED,
        ),
        persistence,
    )

    assert persistence.calls == [(USER_ID, ADMIN_ID, UserStatus.REJECTED)]
    assert result.user.status is UserStatus.REJECTED


def test_change_user_approval_status_rejects_a_missing_user() -> None:
    persistence = FakeUserPersistence(actor=_admin())

    with pytest.raises(UserNotFoundError, match="User not found"):
        change_user_approval_status(
            ChangeUserApprovalStatusCommand(
                user_id=USER_ID,
                requested_by=ADMIN_ID,
                status=UserStatus.ACCEPTED,
            ),
            persistence,
        )

    assert persistence.calls == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": UserStatus.ACCEPTED, "pending_expires_at": None},
        {"status": UserStatus.REJECTED, "pending_expires_at": None},
        {"status": UserStatus.EXPIRED, "pending_expires_at": None},
        {"status": UserStatus.DELETED, "pending_expires_at": None},
        {"pending_expires_at": datetime.now(UTC) - timedelta(seconds=1)},
        {"pending_expires_at": None},
    ],
)
def test_change_user_approval_status_rejects_users_not_awaiting_approval(
    overrides: dict[str, object],
) -> None:
    persistence = FakeUserPersistence(
        target=_pending_user(**overrides),
        actor=_admin(),
    )

    with pytest.raises(
        UserNotAwaitingApprovalError,
        match="not awaiting approval",
    ):
        change_user_approval_status(
            ChangeUserApprovalStatusCommand(
                user_id=USER_ID,
                requested_by=ADMIN_ID,
                status=UserStatus.ACCEPTED,
            ),
            persistence,
        )

    assert persistence.calls == []


def test_change_user_approval_status_rejects_a_missing_actor() -> None:
    persistence = FakeUserPersistence(target=_pending_user())

    with pytest.raises(ApprovalForbiddenError, match="Forbidden"):
        change_user_approval_status(
            ChangeUserApprovalStatusCommand(
                user_id=USER_ID,
                requested_by=ADMIN_ID,
                status=UserStatus.ACCEPTED,
            ),
            persistence,
        )

    assert persistence.calls == []


def test_change_user_approval_status_rejects_a_non_admin_actor() -> None:
    persistence = FakeUserPersistence(
        target=_pending_user(),
        actor=_admin(id=OTHER_ID, role=UserRole.OPERATOR, email="op@example.com"),
    )

    with pytest.raises(ApprovalForbiddenError, match="Forbidden"):
        change_user_approval_status(
            ChangeUserApprovalStatusCommand(
                user_id=USER_ID,
                requested_by=OTHER_ID,
                status=UserStatus.ACCEPTED,
            ),
            persistence,
        )

    assert persistence.calls == []


def test_change_user_approval_status_rejects_an_unaccepted_admin() -> None:
    persistence = FakeUserPersistence(
        target=_pending_user(),
        actor=_admin(status=UserStatus.PENDING, pending_expires_at=PENDING_EXPIRES_AT),
    )

    with pytest.raises(ApprovalForbiddenError, match="Forbidden"):
        change_user_approval_status(
            ChangeUserApprovalStatusCommand(
                user_id=USER_ID,
                requested_by=ADMIN_ID,
                status=UserStatus.ACCEPTED,
            ),
            persistence,
        )

    assert persistence.calls == []


def test_change_user_approval_status_rejects_unsupported_statuses() -> None:
    persistence = FakeUserPersistence(target=_pending_user(), actor=_admin())

    with pytest.raises(ValueError, match="Unsupported approval status"):
        change_user_approval_status(
            ChangeUserApprovalStatusCommand(
                user_id=USER_ID,
                requested_by=ADMIN_ID,
                status=UserStatus.PENDING,
            ),
            persistence,
        )

    assert persistence.calls == []
