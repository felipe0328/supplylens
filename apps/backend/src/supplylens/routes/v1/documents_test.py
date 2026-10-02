from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from supplylens.api import create_app
from supplylens.config import AppEnvironment
from supplylens.controllers.documents.create_upload_intent import (
    CreateUploadIntentCommandResult,
    UploadInstructions,
)
from supplylens.database.database import get_session
from supplylens.port.storage.storage import StorageUnavailableError, UploadTooLargeError
from supplylens.routes.v1 import documents

DOCUMENT_ID = UUID("12345678-1234-5678-1234-567812345678")
UPLOAD_REQUEST = {
    "filename": "invoice.pdf",
    "content_type": "application/pdf",
    "size_bytes": 512,
}


@pytest.fixture
def upload_client(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, Mock]:
    app = create_app(AppEnvironment.TESTING)
    app.dependency_overrides[get_session] = lambda: None
    monkeypatch.setattr(documents, "DocumentPersistenceAdapter", Mock())
    monkeypatch.setattr(documents, "StorageAdapter", Mock())
    controller = Mock()
    monkeypatch.setattr(documents, "create_upload_intent_controller", controller)
    return TestClient(app), controller


def test_create_upload_intent_returns_created(
    upload_client: tuple[TestClient, Mock],
) -> None:
    client, controller = upload_client
    controller.return_value = CreateUploadIntentCommandResult(
        id=DOCUMENT_ID,
        upload=UploadInstructions(
            url="https://storage.invalid/upload",
            method="PUT",
            headers={"Content-Type": "application/pdf"},
            expires_in_seconds=900,
        ),
    )

    response = client.post("/api/v1/documents/uploads", json=UPLOAD_REQUEST)

    assert response.status_code == 201
    assert response.json() == {
        "id": str(DOCUMENT_ID),
        "upload": {
            "url": "https://storage.invalid/upload",
            "method": "PUT",
            "headers": {"Content-Type": "application/pdf"},
            "expires_in_seconds": 900,
        },
    }


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (
            UploadTooLargeError("limit exceeded"),
            413,
            "Upload exceeds the maximum document size.",
        ),
        (
            StorageUnavailableError("storage timeout"),
            503,
            "Object storage is unavailable.",
        ),
    ],
)
def test_create_upload_intent_maps_expected_errors(
    upload_client: tuple[TestClient, Mock],
    error: Exception,
    expected_status: int,
    expected_detail: str,
) -> None:
    client, controller = upload_client
    controller.side_effect = error

    response = client.post("/api/v1/documents/uploads", json=UPLOAD_REQUEST)

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}


def test_create_upload_intent_does_not_treat_configuration_errors_as_client_errors(
    upload_client: tuple[TestClient, Mock],
) -> None:
    client, controller = upload_client
    controller.side_effect = ValueError("invalid storage configuration")

    with pytest.raises(ValueError, match="invalid storage configuration"):
        client.post("/api/v1/documents/uploads", json=UPLOAD_REQUEST)
