from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from supplylens.adapters.persistence.users import UserPersistenceAdapter
from supplylens.controllers.users.exceptions import (
    InvalidCredentialsError,
    InvalidEmailAddressError,
    InvalidPasswordError,
    UserAlreadyExistsError,
    UserNotFoundError,
    UserPendingError,
)
from supplylens.controllers.users.login_user import LoginUserCommand, login_user
from supplylens.controllers.users.register import RegisterUserCommand, register_user
from supplylens.controllers.users.types import User as ControllerUser
from supplylens.database.database import get_session
from supplylens.schemas.common import ErrorResponse
from supplylens.schemas.users import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
)
from supplylens.schemas.users import User as SchemaUser

auth_router = APIRouter(prefix="/auth", tags=["Auth"])

_VALIDATION_ERROR_SCHEMA = {"$ref": "#/components/schemas/HTTPValidationError"}
_REGISTER_ERRORS = (
    UserPendingError,
    UserAlreadyExistsError,
    InvalidEmailAddressError,
    InvalidPasswordError,
)
_LOGIN_ERRORS = (
    UserNotFoundError,
    InvalidPasswordError,
    UserPendingError,
    InvalidEmailAddressError,
    InvalidCredentialsError,
)


def _register_http_error(error: Exception) -> HTTPException:
    if isinstance(error, UserPendingError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        )
    if isinstance(error, UserAlreadyExistsError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        )
    if isinstance(error, (InvalidEmailAddressError, InvalidPasswordError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        )
    if isinstance(error, InvalidEmailAddressError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        )
    raise TypeError(f"No HTTP mapping for {type(error).__name__}")


def _login_http_error(error: Exception) -> HTTPException:
    if isinstance(error, InvalidCredentialsError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )
    if isinstance(error, UserPendingError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        )
    raise TypeError(f"No HTTP mapping for {type(error).__name__}")


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
    description=(
        "Creates a pending account with a 48-hour approval window and does not "
        "start a session. An email that is still pending returns 409. An accepted "
        "email returns 409 and should log in. An expired, rejected, or deleted "
        "email reuses the same account, replaces the password, and returns to "
        "pending."
    ),
    responses={
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": ("The email is already accepted or still pending approval."),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "The email address or password does not meet the registration rules."
            ),
            "content": {
                "application/json": {
                    "schema": {
                        "oneOf": [
                            {"$ref": "#/components/schemas/ErrorResponse"},
                            _VALIDATION_ERROR_SCHEMA,
                        ]
                    }
                }
            },
        },
    },
)
def register(
    request: RegisterRequest,
    session: Annotated[Session, Depends(get_session, scope="function")],
) -> RegisterResponse:
    persistence = UserPersistenceAdapter(session=session)
    try:
        result = register_user(
            RegisterUserCommand(
                email=request.email,
                password=request.password,
            ),
            persistence,
        )
    except _REGISTER_ERRORS as exc:
        raise _register_http_error(exc) from exc
    return RegisterResponse(user=_to_schema_user(result.user))


@auth_router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    summary="Login a user",
    description="Logs in a user and returns a JWT token.",
)
def login(
    request: LoginRequest,
    session: Annotated[Session, Depends(get_session, scope="function")],
) -> LoginResponse:
    persistence = UserPersistenceAdapter(session=session)
    try:
        result = login_user(
            LoginUserCommand(
                email=request.email,
                password=request.password,
            ),
            persistence,
        )
    except _LOGIN_ERRORS as exc:
        raise _login_http_error(exc) from exc
    return LoginResponse(
        access_token=result.access_token,
        token_type=result.token_type,
        expires_in=result.expires_in,
    )
