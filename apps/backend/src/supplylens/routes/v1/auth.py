from typing import Annotated

from fastapi import APIRouter, Depends, status

from supplylens.controllers.users.exceptions import (
    AccountNotAcceptedError,
    InvalidCredentialsError,
    InvalidEmailAddressError,
    InvalidPasswordError,
    UserAlreadyExistsError,
    UserPendingError,
)
from supplylens.controllers.users.login_user import LoginUserCommand, login_user
from supplylens.controllers.users.register import RegisterUserCommand, register_user
from supplylens.controllers.users.types import User as ControllerUser
from supplylens.port.persistence.users import UserPersistence
from supplylens.schemas.users import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
)
from supplylens.schemas.users import User as SchemaUser

from .dependencies import get_user_persistence
from .errors import error_responses

auth_router = APIRouter(prefix="/auth", tags=["Auth"])


def _to_schema_user(user: ControllerUser) -> SchemaUser:
    accepted_by = None
    if user.accepted_by is not None:
        accepted_by = _to_schema_user(user.accepted_by)
    return SchemaUser(
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


@auth_router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a pending user",
    responses=error_responses(
        UserPendingError,
        UserAlreadyExistsError,
        InvalidEmailAddressError,
        InvalidPasswordError,
        validation=True,
    ),
)
def register(
    request: RegisterRequest,
    persistence: Annotated[UserPersistence, Depends(get_user_persistence)],
) -> RegisterResponse:
    """Creates a pending account with a 48-hour approval window and does not
    start a session. An email that is still pending returns 409. An accepted
    email returns 409 and should log in. An expired, rejected, or deleted
    email reuses the same account, replaces the password, and returns to
    pending.
    """
    result = register_user(
        RegisterUserCommand(email=request.email, password=request.password),
        persistence,
    )
    return RegisterResponse(user=_to_schema_user(result.user))


@auth_router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    summary="Log in an accepted user",
    responses=error_responses(
        InvalidCredentialsError,
        AccountNotAcceptedError,
        InvalidEmailAddressError,
        validation=True,
    ),
)
def login(
    request: LoginRequest,
    persistence: Annotated[UserPersistence, Depends(get_user_persistence)],
) -> LoginResponse:
    """Returns a short-lived JWT access token when the email and password match
    an accepted account. An unknown email and a wrong password return the same
    401. Pending, rejected, expired, and deleted accounts return 403. A pending
    account past its approval window is treated as expired.
    """
    result = login_user(
        LoginUserCommand(email=request.email, password=request.password),
        persistence,
    )
    return LoginResponse(
        access_token=result.access_token,
        token_type=result.token_type,
        expires_in=result.expires_in,
    )
