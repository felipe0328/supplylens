from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from supplylens.api import create_app
from supplylens.config import AppEnvironment
from supplylens.controllers.users.exceptions import (
    AccountNotAcceptedError,
    InvalidCredentialsError,
    InvalidEmailAddressError,
    InvalidPasswordError,
    UserAlreadyExistsError,
    UserPendingError,
)
from supplylens.controllers.users.login_user import LoginUserCommandResult
from supplylens.controllers.users.register import RegisterUserCommandResult
from supplylens.controllers.users.types import User as ControllerUser
from supplylens.database import database
from supplylens.database.database import Base
from supplylens.domain.users import UserRole, UserStatus
from supplylens.models.user import User as UserModel
from supplylens.routes.v1 import auth
from supplylens.routes.v1.dependencies import get_user_persistence
from supplylens.tools.encode_decode import decode_jwt
from supplylens.tools.encryption import verify_password

USER_ID = UUID("12345678-1234-5678-1234-567812345678")
CREATED_AT = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
REGISTER_BODY = {
    "email": "Operator@Example.com",
    "password": "Synthetic1",
}


def _controller_user() -> ControllerUser:
    return ControllerUser(
        id=USER_ID,
        email="operator@example.com",
        role=UserRole.OPERATOR,
        status=UserStatus.PENDING,
        accepted_by=None,
        pending_expires_at=CREATED_AT + timedelta(days=2),
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
        deleted_at=None,
    )


@pytest.fixture
def register_client(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, Mock]:
    app = create_app(AppEnvironment.TESTING)
    app.dependency_overrides[get_user_persistence] = lambda: Mock()
    controller = Mock(return_value=RegisterUserCommandResult(user=_controller_user()))
    monkeypatch.setattr(auth, "register_user", controller)
    return TestClient(app), controller


def test_register_returns_created_user_without_a_password(
    register_client: tuple[TestClient, Mock],
) -> None:
    client, controller = register_client

    response = client.post("/api/v1/auth/register", json=REGISTER_BODY)

    assert response.status_code == 201
    assert response.json() == {
        "user": {
            "id": str(USER_ID),
            "email": "operator@example.com",
            "role": "OPERATOR",
            "status": "PENDING",
            "accepted_by": None,
            "pending_expires_at": "2026-10-09T12:00:00Z",
            "created_at": "2026-10-07T12:00:00Z",
            "updated_at": "2026-10-07T12:00:00Z",
            "deleted_at": None,
        }
    }
    command = controller.call_args.args[0]
    assert command.email == "Operator@example.com"
    assert command.password == "Synthetic1"
    assert not hasattr(command, "role")
    assert "password" not in response.json()["user"]
    assert "password_hash" not in response.json()["user"]


def test_register_includes_the_approver(
    register_client: tuple[TestClient, Mock],
) -> None:
    client, controller = register_client
    approver = ControllerUser(
        id=UUID("87654321-4321-8765-4321-876543218765"),
        email="admin@example.com",
        role=UserRole.ADMIN,
        status=UserStatus.ACCEPTED,
        accepted_by=None,
        pending_expires_at=None,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
        deleted_at=None,
    )
    controller.return_value = RegisterUserCommandResult(
        user=replace(_controller_user(), accepted_by=approver)
    )

    response = client.post("/api/v1/auth/register", json=REGISTER_BODY)

    assert response.status_code == 201
    user = response.json()["user"]
    approver_body = user["accepted_by"]
    assert approver_body["id"] == str(approver.id)
    assert approver_body["email"] == "admin@example.com"
    assert approver_body["accepted_by"] is None
    assert "password_hash" not in user
    assert "password_hash" not in approver_body


def _assert_openapi_422_resolves_both_error_shapes(
    schema: dict, operation: dict
) -> None:
    response_schema = operation["responses"]["422"]["content"]["application/json"][
        "schema"
    ]
    references = {item["$ref"] for item in response_schema["oneOf"]}
    components = schema["components"]["schemas"]
    for reference in (
        "#/components/schemas/ErrorResponse",
        "#/components/schemas/HTTPValidationError",
    ):
        assert reference in references
        assert reference.removeprefix("#/components/schemas/") in components


def test_register_openapi_documents_pending_registration() -> None:
    schema = create_app(AppEnvironment.TESTING).openapi()
    operation = schema["paths"]["/api/v1/auth/register"]["post"]

    assert operation["summary"] == "Register a pending user"
    assert "does not" in operation["description"]
    assert "409" in operation["responses"]
    _assert_openapi_422_resolves_both_error_shapes(schema, operation)


@pytest.mark.parametrize(
    "error",
    [
        UserPendingError("This email is already waiting for approval."),
        UserAlreadyExistsError(
            "An account with this email already exists. Log in instead."
        ),
    ],
)
def test_register_maps_conflicts(
    register_client: tuple[TestClient, Mock],
    error: Exception,
) -> None:
    client, controller = register_client
    controller.side_effect = error

    response = client.post("/api/v1/auth/register", json=REGISTER_BODY)

    assert response.status_code == 409
    assert response.json() == {"detail": str(error)}


def test_register_maps_invalid_password(
    register_client: tuple[TestClient, Mock],
) -> None:
    client, controller = register_client
    controller.side_effect = InvalidPasswordError(
        "Password must be at least 8 characters long"
    )

    response = client.post("/api/v1/auth/register", json=REGISTER_BODY)

    assert response.status_code == 422
    assert response.json() == {"detail": "Password must be at least 8 characters long"}


@pytest.fixture
def registration_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, autoflush=False)
        monkeypatch.setattr(database, "SessionLocal", factory)
        with TestClient(create_app(AppEnvironment.TESTING)) as client:
            yield client, factory
    finally:
        engine.dispose()


def test_register_api_creates_a_pending_user(
    registration_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = registration_client

    response = client.post("/api/v1/auth/register", json=REGISTER_BODY)

    assert response.status_code == 201
    body = response.json()["user"]
    assert body["email"] == "operator@example.com"
    assert body["status"] == "PENDING"
    assert body["role"] == "OPERATOR"
    assert "password" not in body
    expires = datetime.fromisoformat(body["pending_expires_at"])
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    remaining = expires - datetime.now(UTC)
    assert timedelta(hours=47) < remaining < timedelta(hours=49)
    with factory() as session:
        stored = session.scalar(select(UserModel))
        assert stored is not None
        assert verify_password("Synthetic1", stored.password_hash)[0]


def test_register_api_reuses_an_expired_user(
    registration_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = registration_client
    created = client.post("/api/v1/auth/register", json=REGISTER_BODY)
    created_id = created.json()["user"]["id"]
    with factory() as session:
        stored = session.scalar(select(UserModel))
        assert stored is not None
        stored.status = UserStatus.EXPIRED
        session.commit()

    response = client.post(
        "/api/v1/auth/register",
        json={**REGISTER_BODY, "password": "Synthetic2"},
    )

    assert response.status_code == 201
    assert response.json()["user"]["id"] == created_id
    assert response.json()["user"]["status"] == "PENDING"
    with factory() as session:
        stored = session.scalar(select(UserModel))
        assert stored is not None
        assert verify_password("Synthetic2", stored.password_hash)[0]
        assert not verify_password("Synthetic1", stored.password_hash)[0]
        assert session.scalar(select(func.count()).select_from(UserModel)) == 1


def test_register_api_reuses_a_deleted_user(
    registration_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = registration_client
    created = client.post("/api/v1/auth/register", json=REGISTER_BODY)
    created_id = created.json()["user"]["id"]
    with factory() as session:
        stored = session.scalar(select(UserModel))
        assert stored is not None
        stored.status = UserStatus.DELETED
        stored.deleted_at = datetime.now(UTC)
        session.commit()

    response = client.post(
        "/api/v1/auth/register",
        json={**REGISTER_BODY, "password": "Synthetic2"},
    )

    assert response.status_code == 201
    assert response.json()["user"]["id"] == created_id
    assert response.json()["user"]["status"] == "PENDING"
    with factory() as session:
        stored = session.scalar(select(UserModel))
        assert stored is not None
        assert stored.status is UserStatus.PENDING
        assert stored.deleted_at is None
        assert verify_password("Synthetic2", stored.password_hash)[0]


def test_register_api_conflicts_when_the_account_is_accepted(
    registration_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = registration_client
    client.post("/api/v1/auth/register", json=REGISTER_BODY)
    with factory() as session:
        stored = session.scalar(select(UserModel))
        assert stored is not None
        stored.status = UserStatus.ACCEPTED
        original_hash = stored.password_hash
        session.commit()

    response = client.post(
        "/api/v1/auth/register",
        json={**REGISTER_BODY, "password": "Synthetic2"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "An account with this email already exists. Log in instead."
    )
    with factory() as session:
        stored = session.scalar(select(UserModel))
        assert stored is not None
        assert stored.password_hash == original_hash
        assert stored.status is UserStatus.ACCEPTED


def test_register_api_stores_an_operator_when_the_body_requests_admin(
    registration_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = registration_client

    response = client.post(
        "/api/v1/auth/register",
        json={**REGISTER_BODY, "role": "ADMIN"},
    )

    assert response.status_code == 201
    assert response.json()["user"]["role"] == "OPERATOR"
    with factory() as session:
        stored = session.scalar(select(UserModel))
        assert stored is not None
        assert stored.role is UserRole.OPERATOR


def test_register_api_conflicts_when_the_account_is_still_pending(
    registration_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _factory = registration_client
    client.post("/api/v1/auth/register", json=REGISTER_BODY)

    response = client.post("/api/v1/auth/register", json=REGISTER_BODY)

    assert response.status_code == 409
    assert response.json()["detail"] == "This email is already waiting for approval."


def test_register_api_rejects_a_weak_password(
    registration_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = registration_client

    response = client.post(
        "/api/v1/auth/register",
        json={**REGISTER_BODY, "password": "short1A"},
    )

    assert response.status_code == 422
    assert "8 characters" in response.json()["detail"]
    with factory() as session:
        assert session.scalar(select(UserModel)) is None


JWT_SECRET = "synthetic-jwt-secret-with-32-characters"


@pytest.fixture
def login_client(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, Mock]:
    app = create_app(AppEnvironment.TESTING)
    app.dependency_overrides[get_user_persistence] = lambda: Mock()
    controller = Mock(
        return_value=LoginUserCommandResult(
            access_token="synthetic-access-token",
            token_type="Bearer",
            expires_in=900,
        )
    )
    monkeypatch.setattr(auth, "login_user", controller)
    return TestClient(app), controller


@pytest.fixture
def jwt_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("JWT_ACCESS_TTL_SECONDS", "900")
    monkeypatch.setattr("supplylens.config.__jwt_settings", None)


def test_login_returns_the_access_token(
    login_client: tuple[TestClient, Mock],
) -> None:
    client, controller = login_client

    response = client.post("/api/v1/auth/login", json=REGISTER_BODY)

    assert response.status_code == 200
    assert response.json() == {
        "access_token": "synthetic-access-token",
        "token_type": "Bearer",
        "expires_in": 900,
    }
    command = controller.call_args.args[0]
    assert command.email == "Operator@example.com"
    assert command.password == "Synthetic1"
    assert "password_hash" not in response.json()


def test_login_openapi_documents_credential_and_status_failures() -> None:
    schema = create_app(AppEnvironment.TESTING).openapi()
    operation = schema["paths"]["/api/v1/auth/login"]["post"]

    assert operation["summary"] == "Log in an accepted user"
    assert "401" in operation["responses"]
    assert "403" in operation["responses"]
    assert "422" in operation["responses"]


def test_login_maps_invalid_credentials(
    login_client: tuple[TestClient, Mock],
) -> None:
    client, controller = login_client
    controller.side_effect = InvalidCredentialsError("Invalid email or password.")

    response = client.post("/api/v1/auth/login", json=REGISTER_BODY)

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password."}


@pytest.mark.parametrize(
    "message",
    [
        "This account is waiting for approval.",
        "This account was not approved.",
        "This registration expired. Register again.",
        "This account is not available.",
    ],
)
def test_login_maps_accounts_that_are_not_accepted(
    login_client: tuple[TestClient, Mock],
    message: str,
) -> None:
    client, controller = login_client
    controller.side_effect = AccountNotAcceptedError(message)

    response = client.post("/api/v1/auth/login", json=REGISTER_BODY)

    assert response.status_code == 403
    assert response.json() == {"detail": message}


def test_login_maps_an_invalid_email(login_client: tuple[TestClient, Mock]) -> None:
    client, controller = login_client
    controller.side_effect = InvalidEmailAddressError(
        "Invalid email address: synthetic"
    )

    response = client.post("/api/v1/auth/login", json=REGISTER_BODY)

    assert response.status_code == 422
    assert response.json()["detail"].startswith("Invalid email address:")


def test_login_api_returns_a_token_for_an_accepted_user(
    registration_client: tuple[TestClient, sessionmaker[Session]],
    jwt_environment: None,
) -> None:
    client, factory = registration_client
    created = client.post("/api/v1/auth/register", json=REGISTER_BODY)
    created_id = created.json()["user"]["id"]
    with factory() as session:
        stored = session.scalar(select(UserModel))
        assert stored is not None
        stored.status = UserStatus.ACCEPTED
        session.commit()

    response = client.post("/api/v1/auth/login", json=REGISTER_BODY)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == 900
    assert "password" not in body
    decoded = decode_jwt(body["access_token"])
    assert decoded["sub"] == created_id
    assert decoded["role"] == "OPERATOR"
    assert "email" not in decoded


def test_login_api_wrong_password_does_not_reveal_a_pending_account(
    registration_client: tuple[TestClient, sessionmaker[Session]],
    jwt_environment: None,
) -> None:
    client, _factory = registration_client
    client.post("/api/v1/auth/register", json=REGISTER_BODY)

    response = client.post(
        "/api/v1/auth/login",
        json={**REGISTER_BODY, "password": "Synthetic2"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password."}


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("Operator@Example.com", "Synthetic2"),
        ("missing@example.com", "Synthetic1"),
    ],
)
def test_login_api_uses_the_same_response_for_bad_credentials(
    registration_client: tuple[TestClient, sessionmaker[Session]],
    jwt_environment: None,
    email: str,
    password: str,
) -> None:
    client, factory = registration_client
    client.post("/api/v1/auth/register", json=REGISTER_BODY)
    with factory() as session:
        stored = session.scalar(select(UserModel))
        assert stored is not None
        stored.status = UserStatus.ACCEPTED
        session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password."}


def test_login_api_treats_an_elapsed_pending_window_as_expired(
    registration_client: tuple[TestClient, sessionmaker[Session]],
    jwt_environment: None,
) -> None:
    client, factory = registration_client
    client.post("/api/v1/auth/register", json=REGISTER_BODY)
    with factory() as session:
        stored = session.scalar(select(UserModel))
        assert stored is not None
        stored.pending_expires_at = datetime.now(UTC) - timedelta(minutes=1)
        session.commit()

    response = client.post("/api/v1/auth/login", json=REGISTER_BODY)

    assert response.status_code == 403
    assert response.json() == {"detail": "This registration expired. Register again."}


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (UserStatus.PENDING, "This account is waiting for approval."),
        (UserStatus.REJECTED, "This account was not approved."),
        (UserStatus.EXPIRED, "This registration expired. Register again."),
        (UserStatus.DELETED, "This account is not available."),
    ],
)
def test_login_api_rejects_accounts_that_are_not_accepted(
    registration_client: tuple[TestClient, sessionmaker[Session]],
    jwt_environment: None,
    status: UserStatus,
    message: str,
) -> None:
    client, factory = registration_client
    client.post("/api/v1/auth/register", json=REGISTER_BODY)
    with factory() as session:
        stored = session.scalar(select(UserModel))
        assert stored is not None
        stored.status = status
        session.commit()

    response = client.post("/api/v1/auth/login", json=REGISTER_BODY)

    assert response.status_code == 403
    assert response.json() == {"detail": message}
