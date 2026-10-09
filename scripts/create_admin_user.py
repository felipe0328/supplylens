"""Create the local accepted admin from ADMIN_USER_EMAIL and ADMIN_USER_PASSWORD."""

import os
from contextlib import contextmanager

from dotenv import load_dotenv
from supplylens.adapters.persistence.users import UserPersistenceAdapter
from supplylens.controllers.users.bootstrap_admin import (
    BootstrapAdminCommand,
    BootstrapAdminOutcome,
    bootstrap_admin_user,
)
from supplylens.database.database import get_session


def main() -> None:
    load_dotenv()
    command = BootstrapAdminCommand(
        email=_required_env("ADMIN_USER_EMAIL"),
        password=_required_env("ADMIN_USER_PASSWORD"),
    )
    with contextmanager(get_session)() as session:
        result = bootstrap_admin_user(command, UserPersistenceAdapter(session))

    user = result.user
    message = {
        BootstrapAdminOutcome.ALREADY_EXISTS: "Admin user already exists",
        BootstrapAdminOutcome.CREATED: "Admin user created",
        BootstrapAdminOutcome.UPDATED: "Admin user updated",
    }[result.outcome]
    print(f"{message}: {user.email} role={user.role.value} status={user.status.value}")


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise ValueError(f"{name} must be set")
    return value.strip()


if __name__ == "__main__":
    main()
