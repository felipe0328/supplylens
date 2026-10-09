from supplylens.controllers.users.types import User as ControllerUser
from supplylens.port.persistence.users import User as PortUser


def map_port_user_to_controller_user(user: PortUser) -> ControllerUser:
    accepted_by = None
    if user.accepted_by is not None:
        accepted_by = map_port_user_to_controller_user(user.accepted_by)
    return ControllerUser(
        id=user.id,
        email=user.email,
        role=user.role,
        status=user.status,
        accepted_by=accepted_by,
        pending_expires_at=user.pending_expires_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
        deleted_at=user.deleted_at,
    )
