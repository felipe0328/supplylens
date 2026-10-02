from datetime import datetime
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
from supplylens.controllers.documents.exceptions import (
    DocumentInvalidContentTypeError,
    DocumentNotFoundError,
    DocumentNotUploadedError,
    StoreDocumentInvalidSizeError,
)
from supplylens.controllers.documents.get_document_url import (
    GetDocumentURLCommandResponse,
)
from supplylens.controllers.documents.types import Document as ControllerDocument
from supplylens.database.database import get_session
from supplylens.domain.documents import DocumentProcessingStatus, DocumentUploadStatus
from supplylens.port.storage.storage import (
    StorageUnavailableError,
    UploadTooLargeError,
)
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


def test_create_upload_intent_normalizes_filename(
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

    response = client.post(
        "/api/v1/documents/uploads",
        json={**UPLOAD_REQUEST, "filename": "  invoice.pdf  "},
    )

    assert response.status_code == 201
    assert controller.call_args.kwargs["req"].filename == "invoice.pdf"


@pytest.mark.parametrize("filename", [" ", "\t", "\n"])
def test_create_upload_intent_rejects_blank_filename(
    upload_client: tuple[TestClient, Mock], filename: str
) -> None:
    client, controller = upload_client

    response = client.post(
        "/api/v1/documents/uploads",
        json={**UPLOAD_REQUEST, "filename": filename},
    )

    assert response.status_code == 422
    controller.assert_not_called()


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


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/v1/documents/uploads"),
        ("post", f"/api/v1/documents/{DOCUMENT_ID}/complete"),
        ("post", f"/api/v1/documents/{DOCUMENT_ID}/download-url"),
        ("delete", f"/api/v1/documents/{DOCUMENT_ID}"),
    ],
)
def test_storage_configuration_errors_return_service_unavailable(
    upload_client: tuple[TestClient, Mock],
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
) -> None:
    client, _ = upload_client
    monkeypatch.setattr(
        documents,
        "StorageAdapter",
        Mock(side_effect=ValueError("invalid storage configuration")),
    )

    response = client.request(
        method,
        path,
        json=UPLOAD_REQUEST if path.endswith("/uploads") else None,
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Object storage is unavailable."}


@pytest.fixture
def document_client(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[TestClient, dict[str, Mock]]:
    app = create_app(AppEnvironment.TESTING)
    app.dependency_overrides[get_session] = lambda: None
    monkeypatch.setattr(documents, "DocumentPersistenceAdapter", Mock())
    monkeypatch.setattr(documents, "StorageAdapter", Mock())
    controllers = {
        "complete": Mock(),
        "get": Mock(),
        "download_url": Mock(),
        "delete": Mock(),
    }
    monkeypatch.setattr(
        documents, "report_upload_completed_controller", controllers["complete"]
    )
    monkeypatch.setattr(documents, "get_document_data_controller", controllers["get"])
    monkeypatch.setattr(
        documents, "get_document_url_controller", controllers["download_url"]
    )
    monkeypatch.setattr(documents, "delete_document_controller", controllers["delete"])
    return TestClient(app), controllers


def _controller_document() -> ControllerDocument:
    return ControllerDocument(
        id=DOCUMENT_ID,
        filename="invoice.pdf",
        size_bytes=512,
        document_type="application/pdf",
        page_count=2,
        upload_status=DocumentUploadStatus.UPLOADED,
        processing_status=DocumentProcessingStatus.PROCESSED,
        created_at=datetime(2026, 9, 30, 12, 0),
        uploaded_at=datetime(2026, 9, 30, 12, 5),
        processed_at=datetime(2026, 9, 30, 12, 10),
    )


def test_report_upload_completed_returns_mapped_document(
    document_client: tuple[TestClient, dict[str, Mock]],
) -> None:
    client, controllers = document_client
    controllers["complete"].return_value = Mock(document=_controller_document())

    response = client.post(f"/api/v1/documents/{DOCUMENT_ID}/complete")

    assert response.status_code == 200
    assert response.json() == {
        "document": {
            "id": str(DOCUMENT_ID),
            "filename": "invoice.pdf",
            "size_bytes": 512,
            "document_type": "application/pdf",
            "page_count": 2,
            "upload_status": "UPLOADED",
            "processing_status": "PROCESSED",
            "created_at": "2026-09-30T12:00:00",
            "uploaded_at": "2026-09-30T12:05:00",
            "processed_at": "2026-09-30T12:10:00",
        }
    }
    controllers["complete"].assert_called_once()


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (DocumentNotFoundError("missing"), 404, "Document not found."),
        (
            StoreDocumentInvalidSizeError("wrong size"),
            422,
            "Uploaded document size does not match the declared size.",
        ),
        (
            DocumentInvalidContentTypeError("wrong type"),
            415,
            "Uploaded document must be a PDF.",
        ),
        (
            StorageUnavailableError("storage unavailable"),
            503,
            "Object storage is unavailable.",
        ),
    ],
)
def test_report_upload_completed_maps_controller_errors(
    document_client: tuple[TestClient, dict[str, Mock]],
    error: Exception,
    expected_status: int,
    expected_detail: str,
) -> None:
    client, controllers = document_client
    controllers["complete"].side_effect = error

    response = client.post(f"/api/v1/documents/{DOCUMENT_ID}/complete")

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}


def test_get_document_data_returns_mapped_document(
    document_client: tuple[TestClient, dict[str, Mock]],
) -> None:
    client, controllers = document_client
    controllers["get"].return_value = Mock(document=_controller_document())

    response = client.get(f"/api/v1/documents/{DOCUMENT_ID}")

    assert response.status_code == 200
    assert response.json()["document"]["filename"] == "invoice.pdf"
    assert response.json()["document"]["uploaded_at"] == "2026-09-30T12:05:00"


def test_get_document_data_maps_missing_document(
    document_client: tuple[TestClient, dict[str, Mock]],
) -> None:
    client, controllers = document_client
    controllers["get"].side_effect = DocumentNotFoundError("missing")

    response = client.get(f"/api/v1/documents/{DOCUMENT_ID}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found."}


def test_get_download_url_returns_url_and_expiration(
    document_client: tuple[TestClient, dict[str, Mock]],
) -> None:
    client, controllers = document_client
    controllers["download_url"].return_value = GetDocumentURLCommandResponse(
        id=DOCUMENT_ID,
        url="https://storage.invalid/download",
        expires_in_seconds=600,
    )

    response = client.post(f"/api/v1/documents/{DOCUMENT_ID}/download-url")

    assert response.status_code == 200
    assert response.json() == {
        "id": str(DOCUMENT_ID),
        "url": "https://storage.invalid/download",
        "expires_in_seconds": 600,
    }


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (DocumentNotFoundError("missing"), 404, "Document not found."),
        (
            DocumentNotUploadedError("not uploaded"),
            409,
            "Document has not been uploaded.",
        ),
        (
            StorageUnavailableError("storage unavailable"),
            503,
            "Object storage is unavailable.",
        ),
    ],
)
def test_get_download_url_maps_controller_errors(
    document_client: tuple[TestClient, dict[str, Mock]],
    error: Exception,
    expected_status: int,
    expected_detail: str,
) -> None:
    client, controllers = document_client
    controllers["download_url"].side_effect = error

    response = client.post(f"/api/v1/documents/{DOCUMENT_ID}/download-url")

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}


def test_delete_document_returns_no_content(
    document_client: tuple[TestClient, dict[str, Mock]],
) -> None:
    client, controllers = document_client

    response = client.delete(f"/api/v1/documents/{DOCUMENT_ID}")

    assert response.status_code == 204
    assert response.content == b""
    controllers["delete"].assert_called_once()


def test_delete_document_maps_storage_unavailable(
    document_client: tuple[TestClient, dict[str, Mock]],
) -> None:
    client, controllers = document_client
    controllers["delete"].side_effect = StorageUnavailableError("offline")

    response = client.delete(f"/api/v1/documents/{DOCUMENT_ID}")

    assert response.status_code == 503
    assert response.json() == {"detail": "Object storage is unavailable."}


def test_document_http_error_rejects_unmapped_errors() -> None:
    with pytest.raises(TypeError, match="No HTTP mapping for RuntimeError"):
        documents._document_http_error(RuntimeError("unexpected"))
