import json

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from supplylens.controllers.documents.exceptions import (
    DocumentNotFoundError,
    StoreDocumentInvalidSizeError,
)
from supplylens.controllers.users.constants import INVALID_REFRESH_TOKEN
from supplylens.controllers.users.exceptions import (
    InvalidOrExpiredRefreshTokenError,
    InvalidPasswordError,
    UserAlreadyExistsError,
    UserPendingError,
)
from supplylens.port.storage.storage import StorageUnavailableError
from supplylens.routes.v1.errors import (
    HTTP_ERRORS,
    error_responses,
    http_error_response,
    register_http_exception_handlers,
)


def test_http_error_response_rejects_unmapped_errors() -> None:
    error = RuntimeError("synthetic internal detail")

    with pytest.raises(TypeError, match="No HTTP mapping for RuntimeError"):
        http_error_response(error)


def test_http_error_response_hides_document_exception_text() -> None:
    response = http_error_response(
        DocumentNotFoundError("Document with ID secret-id was missing in storage")
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert json.loads(response.body) == {"detail": "Document not found."}
    assert b"secret-id" not in response.body


def test_http_error_response_uses_auth_exception_message() -> None:
    message = "Password must contain at least one digit"
    response = http_error_response(InvalidPasswordError(message))

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert json.loads(response.body) == {"detail": message}


def test_http_error_response_uses_the_refresh_token_message() -> None:
    response = http_error_response(
        InvalidOrExpiredRefreshTokenError(INVALID_REFRESH_TOKEN)
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert json.loads(response.body) == {"detail": INVALID_REFRESH_TOKEN}


def test_error_responses_merges_shared_statuses_and_validation_schemas() -> None:
    responses = error_responses(
        UserPendingError,
        UserAlreadyExistsError,
        InvalidPasswordError,
        validation=True,
    )

    conflict = responses[status.HTTP_409_CONFLICT]
    assert isinstance(conflict["description"], str)
    assert "pending" in conflict["description"]
    assert "already accepted" in conflict["description"]
    assert conflict["model"] is not None

    validation = responses[status.HTTP_422_UNPROCESSABLE_CONTENT]
    assert isinstance(validation["description"], str)
    assert "password" in validation["description"]
    assert "request body failed validation" in validation["description"]
    content = validation["content"]
    assert isinstance(content, dict)
    schema = content["application/json"]["schema"]
    references = {item["$ref"] for item in schema["oneOf"]}
    assert references == {
        "#/components/schemas/ErrorResponse",
        "#/components/schemas/HTTPValidationError",
    }


def test_error_responses_keeps_storage_failure_off_unrelated_statuses() -> None:
    responses = error_responses(DocumentNotFoundError, StoreDocumentInvalidSizeError)

    assert status.HTTP_503_SERVICE_UNAVAILABLE not in responses
    assert StorageUnavailableError in HTTP_ERRORS


def test_registered_handler_translates_a_raised_storage_error() -> None:
    app = FastAPI()
    register_http_exception_handlers(app)

    @app.get("/storage")
    def read_storage() -> None:
        raise StorageUnavailableError("bucket secret is offline")

    response = TestClient(app).get("/storage")

    assert response.status_code == 503
    assert response.json() == {"detail": "Object storage is unavailable."}
    assert "secret" not in response.text
