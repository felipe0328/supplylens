from datetime import UTC, datetime, timedelta
from uuid import UUID

from supplylens.controllers.users.list_pending_users import (
    ListPendingUsersCommand,
    list_pending_users,
)
from supplylens.domain.users import UserRole, UserStatus
from supplylens.port.persistence.users import User as PortUser

USER_ID = UUID("12345678-1234-5678-1234-567812345678")
OTHER_ID = UUID("87654321-4321-8765-4321-876543218765")
CREATED_AT = datetime(2026, 10, 7, tzinfo=UTC)


class FakeUserPersistence:
    def __init__(self, users: list[PortUser] | None = None) -> None:
        self._users = users or []
        self.calls: list[tuple[int, int]] = []

    def list_pending_users(self, limit: int, offset: int) -> list[PortUser]:
        self.calls.append((limit, offset))
        return self._users[offset : offset + limit]


def _user(**overrides: object) -> PortUser:
    values: dict[str, object] = {
        "id": USER_ID,
        "email": "operator@example.com",
        "password_hash": "stored-hash",
        "role": UserRole.OPERATOR,
        "status": UserStatus.PENDING,
        "accepted_by": None,
        "pending_expires_at": datetime.now(UTC) + timedelta(hours=1),
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
        "deleted_at": None,
    }
    values.update(overrides)
    return PortUser(**values)  # type: ignore[arg-type]


def test_list_pending_users_maps_persistence_rows() -> None:
    persistence = FakeUserPersistence(
        [
            _user(),
            _user(id=OTHER_ID, email="other@example.com"),
        ]
    )

    result = list_pending_users(
        ListPendingUsersCommand(limit=10, offset=0),
        persistence,
    )

    assert persistence.calls == [(10, 0)]
    assert [user.id for user in result.users] == [USER_ID, OTHER_ID]
    assert [user.email for user in result.users] == [
        "operator@example.com",
        "other@example.com",
    ]
    assert all(not hasattr(user, "password_hash") for user in result.users)


def test_list_pending_users_forwards_pagination() -> None:
    persistence = FakeUserPersistence()

    list_pending_users(ListPendingUsersCommand(limit=2, offset=5), persistence)

    assert persistence.calls == [(2, 5)]


def test_list_pending_users_returns_an_empty_page() -> None:
    result = list_pending_users(
        ListPendingUsersCommand(limit=10, offset=0),
        FakeUserPersistence(),
    )

    assert result.users == []
