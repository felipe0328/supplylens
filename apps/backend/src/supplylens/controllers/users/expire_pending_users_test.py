from supplylens.controllers.users.expire_pending_users import expire_pending_users


class FakeUserPersistence:
    def __init__(self) -> None:
        self.expire_calls = 0

    def expire_pending_users(self) -> None:
        self.expire_calls += 1


def test_expire_pending_users_forwards_to_persistence() -> None:
    persistence = FakeUserPersistence()

    expire_pending_users(persistence)

    assert persistence.expire_calls == 1
