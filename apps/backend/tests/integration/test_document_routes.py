from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TypedDict, cast
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import boto3
import jwt
import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.engine import URL, make_url

from alembic import command
from supplylens.api import create_app
from supplylens.config import AppEnvironment
from supplylens.database import database

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEST_DATABASE_URL = (
    "postgresql+psycopg://supplylens:localdev@127.0.0.1:5434/supplylens_test"
)
PDF_BYTES = b"%PDF-1.4\nSupplyLens synthetic integration fixture\n%%EOF\n"
JWT_SECRET = "synthetic-jwt-secret-with-32-characters"
ACCESS_USER_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


class UploadInstructions(TypedDict):
    url: str
    method: str
    headers: dict[str, str]
    expires_in_seconds: int


class CreatedDocument(TypedDict):
    id: str
    upload: UploadInstructions


class UploadedDocument(TypedDict):
    id: str
    upload: UploadInstructions
    uploaded_at: str
    download_url: str


def _require_test_database_url() -> URL:
    database_url = make_url(os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL))
    if not database_url.database or not database_url.database.endswith("_test"):
        pytest.fail("TEST_DATABASE_URL must name a database ending in '_test'.")
    return database_url


@pytest.fixture
def document_api_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    database_url = _require_test_database_url()
    monkeypatch.setenv(
        "DATABASE_URL", database_url.render_as_string(hide_password=False)
    )
    monkeypatch.setattr(database, "SessionEngine", None)
    monkeypatch.setattr(database, "SessionLocal", None)

    alembic_config = Config(str(BACKEND_ROOT / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.upgrade(alembic_config, "head")

    endpoint = os.getenv("STORAGE_TEST_ENDPOINT", "http://127.0.0.1:9002")
    access_key_id = os.getenv("STORAGE_TEST_ACCESS_KEY_ID", "supplylens-test")
    secret_access_key = os.getenv(
        "STORAGE_TEST_SECRET_ACCESS_KEY", "supplylens-test-only"
    )
    bucket = f"supplylens-route-it-{uuid.uuid4().hex}"
    region = os.getenv("STORAGE_TEST_REGION", "us-east-1")
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name=region,
    )
    client.create_bucket(Bucket=bucket)

    monkeypatch.setenv("S3_ENDPOINT", endpoint)
    monkeypatch.setenv("S3_BUCKET", bucket)
    monkeypatch.setenv("S3_ACCESS_KEY_ID", access_key_id)
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", secret_access_key)
    monkeypatch.setenv("S3_REGION", region)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.setattr("supplylens.config.__jwt_settings", None)

    app = create_app(AppEnvironment.TESTING)
    access_token = jwt.encode(
        {
            "sub": ACCESS_USER_ID,
            "role": "OPERATOR",
            "exp": datetime.now(UTC) + timedelta(minutes=15),
        },
        JWT_SECRET,
        algorithm="HS256",
    )
    try:
        with TestClient(
            app, headers={"Authorization": f"Bearer {access_token}"}
        ) as test_client:
            yield test_client
    finally:
        objects = client.list_objects_v2(Bucket=bucket).get("Contents", [])
        if objects:
            client.delete_objects(
                Bucket=bucket,
                Delete={"Objects": [{"Key": item["Key"]} for item in objects]},
            )
        client.delete_bucket(Bucket=bucket)
        if database.SessionEngine is not None:
            database.SessionEngine.dispose()
        database.SessionEngine = None
        database.SessionLocal = None


def _send_put(url: str, headers: dict[str, str], body: bytes) -> tuple[int, bytes]:
    request = Request(url, data=body, headers=headers, method="PUT")
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()


def _create_document(client: TestClient) -> CreatedDocument:
    response = client.post(
        "/api/v1/documents/uploads",
        json={
            "filename": "synthetic-invoice.pdf",
            "content_type": "application/pdf",
            "size_bytes": len(PDF_BYTES),
        },
    )
    assert response.status_code == 201, "document upload intent should be created"
    return cast(CreatedDocument, response.json())


@pytest.fixture
def created_document(document_api_client: TestClient) -> CreatedDocument:
    return _create_document(document_api_client)


@pytest.fixture
def uploaded_document(
    document_api_client: TestClient,
    created_document: CreatedDocument,
) -> UploadedDocument:
    upload = created_document["upload"]
    upload_status, _ = _send_put(upload["url"], upload["headers"], PDF_BYTES)
    assert upload_status in {200, 204}, "the presigned document upload should succeed"

    completion = document_api_client.post(
        f"/api/v1/documents/{created_document['id']}/complete"
    )
    assert completion.status_code == 200, "uploaded document should be completable"
    uploaded_at = completion.json()["document"]["uploaded_at"]
    assert uploaded_at is not None, "completion should persist uploaded_at"

    download_response = document_api_client.post(
        f"/api/v1/documents/{created_document['id']}/download-url"
    )
    assert download_response.status_code == 200, (
        "uploaded document should be downloadable"
    )
    download_url = download_response.json()["url"]

    return UploadedDocument(
        id=created_document["id"],
        upload=upload,
        uploaded_at=uploaded_at,
        download_url=download_url,
    )


@pytest.mark.integration
def test_document_creation_requires_an_access_token(
    document_api_client: TestClient,
) -> None:
    response = TestClient(document_api_client.app).post(
        "/api/v1/documents/uploads",
        json={
            "filename": "synthetic-invoice.pdf",
            "content_type": "application/pdf",
            "size_bytes": len(PDF_BYTES),
        },
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


@pytest.mark.integration
def test_document_creation_returns_upload_intent(
    document_api_client: TestClient,
) -> None:
    upload_intent = _create_document(document_api_client)
    upload = upload_intent["upload"]
    assert uuid.UUID(upload_intent["id"])
    assert upload["method"] == "PUT"
    assert upload["expires_in_seconds"] > 0
    assert upload["headers"] == {
        "Content-Type": "application/pdf",
        "If-None-Match": "*",
    }


@pytest.mark.integration
def test_document_exists_in_pending_state_after_creation(
    document_api_client: TestClient,
    created_document: CreatedDocument,
) -> None:
    response = document_api_client.get(f"/api/v1/documents/{created_document['id']}")
    assert response.status_code == 200
    pending_document = response.json()["document"]
    assert pending_document["filename"] == "synthetic-invoice.pdf"
    assert pending_document["size_bytes"] == len(PDF_BYTES)
    assert pending_document["upload_status"] == "PENDING"
    assert pending_document["processing_status"] == "PENDING"
    assert pending_document["created_at"] is not None
    assert pending_document["uploaded_at"] is None


@pytest.mark.integration
def test_pending_document_cannot_be_downloaded(
    document_api_client: TestClient,
    created_document: CreatedDocument,
) -> None:
    response = document_api_client.post(
        f"/api/v1/documents/{created_document['id']}/download-url"
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "Document has not been uploaded."}


@pytest.mark.integration
def test_presigned_upload_cannot_replace_existing_document_bytes(
    document_api_client: TestClient,
    uploaded_document: UploadedDocument,
) -> None:
    upload = uploaded_document["upload"]
    replay_status, _ = _send_put(
        upload["url"], upload["headers"], PDF_BYTES.replace(b"fixture", b"changed")
    )
    assert replay_status in {400, 403, 409, 412}
    with urlopen(uploaded_document["download_url"], timeout=10) as original_file:
        assert original_file.read() == PDF_BYTES


@pytest.mark.integration
def test_upload_completion_marks_document_uploaded_and_is_idempotent(
    document_api_client: TestClient,
    uploaded_document: UploadedDocument,
) -> None:
    response = document_api_client.post(
        f"/api/v1/documents/{uploaded_document['id']}/complete"
    )
    assert response.status_code == 200
    document = response.json()["document"]
    assert document["id"] == uploaded_document["id"]
    assert document["upload_status"] == "UPLOADED"
    assert document["uploaded_at"] == uploaded_document["uploaded_at"]


@pytest.mark.integration
def test_document_download_returns_original_uploaded_bytes(
    uploaded_document: UploadedDocument,
) -> None:
    with urlopen(uploaded_document["download_url"], timeout=10) as downloaded_file:
        assert downloaded_file.status == 200
        assert downloaded_file.read() == PDF_BYTES


@pytest.mark.integration
def test_delete_document_removes_document_record(
    document_api_client: TestClient,
    uploaded_document: UploadedDocument,
) -> None:
    response = document_api_client.delete(
        f"/api/v1/documents/{uploaded_document['id']}"
    )
    assert response.status_code == 204
    assert response.content == b""

    response = document_api_client.get(f"/api/v1/documents/{uploaded_document['id']}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found."}


@pytest.mark.integration
def test_delete_document_removes_uploaded_object(
    document_api_client: TestClient,
    uploaded_document: UploadedDocument,
) -> None:
    response = document_api_client.delete(
        f"/api/v1/documents/{uploaded_document['id']}"
    )
    assert response.status_code == 204

    with pytest.raises(HTTPError) as error:
        urlopen(uploaded_document["download_url"], timeout=10)
    assert error.value.code == 404
