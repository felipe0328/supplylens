import os
import sys
from contextlib import contextmanager

from dotenv import load_dotenv
from supplylens.adapters.persistence.users import UserPersistenceAdapter
from supplylens.controllers.users.mappers import map_port_user_to_controller_user
from supplylens.database.database import get_session
from supplylens.domain.users import UserRole, UserStatus
from supplylens.port.persistence.users import CreateUserRequest
from supplylens.tools.encryption import hash_password

load_dotenv()

ADMIN_USER_EMAIL = os.getenv("ADMIN_USER_EMAIL")
ADMIN_USER_PASSWORD = os.getenv("ADMIN_USER_PASSWORD")

if not ADMIN_USER_EMAIL or not ADMIN_USER_PASSWORD:
    raise ValueError("ADMIN_USER_EMAIL and ADMIN_USER_PASSWORD must be set")

hashed_password = hash_password(ADMIN_USER_PASSWORD)

print(f"Creating admin user: {ADMIN_USER_EMAIL}")

with contextmanager(get_session)() as session:
    user_persistence_adapter = UserPersistenceAdapter(session)

    user_request = CreateUserRequest(
        email=ADMIN_USER_EMAIL,
        password_hash=hashed_password,
    )

    created_user = None
    existing_user = user_persistence_adapter.get_user_by_email(ADMIN_USER_EMAIL)
    if existing_user is not None:
        if (
            existing_user.role is UserRole.ADMIN
            and existing_user.status is UserStatus.ACCEPTED
        ):
            print(
                f"Admin user already exists: \n{map_port_user_to_controller_user(existing_user)!r}"
            )
            sys.exit(0)
        else:
            created_user = user_persistence_adapter.retry_super_admin_creation(
                existing_user.id,
                user_request,
            )
    else:
        created_user = user_persistence_adapter.create_super_admin_user(user_request)

    controller_user = map_port_user_to_controller_user(created_user)
    print(f"Admin user created: \n{controller_user!r}")
