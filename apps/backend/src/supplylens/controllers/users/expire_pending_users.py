from supplylens.port.persistence.users import UserPersistence


def expire_pending_users(persistence: UserPersistence) -> None:
    persistence.expire_pending_users()
