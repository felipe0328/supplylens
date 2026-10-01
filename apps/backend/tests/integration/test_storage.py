from __future__ import annotations

import hashlib
import io
import os
import uuid
from collections.abc import Iterator
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import boto3
import pytest

from supplylens.adapters.storage.storage import StorageAdapter
from supplylens.config import StorageSettings
from supplylens.port.storage.storage import ObjectNotFoundError, PresignedURL

CONTENT_TYPE = "application/pdf"
ORIGINAL_BYTES = b"synthetic-pdf-payload"
DIFFERENT_SAME_LENGTH_BYTES = b"different-pdf-payload"


@pytest.fixture
def storage_adapter() -> Iterator[StorageAdapter]:
    endpoint = os.getenv("STORAGE_TEST_ENDPOINT", "http://127.0.0.1:9002")
    access_key_id = os.getenv("STORAGE_TEST_ACCESS_KEY_ID", "supplylens-test")
    secret_access_key = os.getenv(
        "STORAGE_TEST_SECRET_ACCESS_KEY", "supplylens-test-only"
    )
    bucket = f"supplylens-it-{uuid.uuid4().hex}"
    settings = StorageSettings(
        endpoint=endpoint,
        bucket=bucket,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        region=os.getenv("STORAGE_TEST_REGION", "us-east-1"),
    )
    client = boto3.client(
        "s3",
        endpoint_url=settings.endpoint,
        aws_access_key_id=settings.access_key_id,
        aws_secret_access_key=settings.secret_access_key,
        region_name=settings.region,
    )
    client.create_bucket(Bucket=bucket)
    try:
        yield StorageAdapter(settings)
    finally:
        objects = client.list_objects_v2(Bucket=bucket).get("Contents", [])
        if objects:
            client.delete_objects(
                Bucket=bucket,
                Delete={"Objects": [{"Key": item["Key"]} for item in objects]},
            )
        client.delete_bucket(Bucket=bucket)


@pytest.fixture
def object_key() -> str:
    return f"integration/{uuid.uuid4().hex}/original.pdf"


@pytest.fixture
def upload_url(storage_adapter: StorageAdapter, object_key: str) -> PresignedURL:
    return storage_adapter.create_upload_url(
        object_key, CONTENT_TYPE, size_bytes=len(ORIGINAL_BYTES)
    )


@pytest.fixture
def stored_object(
    storage_adapter: StorageAdapter,
    object_key: str,
    upload_url: PresignedURL,
) -> None:
    status, _ = _send_put(upload_url.url, upload_url.headers, ORIGINAL_BYTES)
    assert status in {200, 204}, "the setup upload should succeed"


def _send_put(url: str, headers: dict[str, str], body: bytes) -> tuple[int, bytes]:
    request = Request(url, data=body, headers=headers, method="PUT")
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()


@pytest.mark.integration
def test_upload_url_returns_required_browser_headers(upload_url: PresignedURL) -> None:
    assert upload_url.method == "PUT"
    assert upload_url.headers == {
        "Content-Type": CONTENT_TYPE,
        "If-None-Match": "*",
    }


@pytest.mark.integration
def test_presigned_put_uploads_file_to_test_bucket(
    storage_adapter: StorageAdapter,
    object_key: str,
    upload_url: PresignedURL,
) -> None:
    status, _ = _send_put(upload_url.url, upload_url.headers, ORIGINAL_BYTES)
    assert status in {200, 204}

    downloaded = io.BytesIO()
    storage_adapter.download_fileobj(object_key, downloaded)
    assert downloaded.getvalue() == ORIGINAL_BYTES


@pytest.mark.integration
def test_head_confirms_uploaded_object_exists(
    storage_adapter: StorageAdapter,
    object_key: str,
    stored_object: None,
) -> None:
    info = storage_adapter.head_object(object_key)
    assert info.key == object_key


@pytest.mark.integration
def test_presigned_put_rejects_wrong_content_type(
    storage_adapter: StorageAdapter,
    object_key: str,
    upload_url: PresignedURL,
) -> None:
    status, _ = _send_put(
        upload_url.url,
        {**upload_url.headers, "Content-Type": "application/octet-stream"},
        ORIGINAL_BYTES,
    )
    assert status in {400, 403}
    with pytest.raises(ObjectNotFoundError):
        storage_adapter.head_object(object_key)


@pytest.mark.integration
def test_presigned_put_rejects_wrong_content_length(
    storage_adapter: StorageAdapter,
    object_key: str,
    upload_url: PresignedURL,
) -> None:
    status, _ = _send_put(upload_url.url, upload_url.headers, ORIGINAL_BYTES + b"x")
    assert status in {400, 403}
    with pytest.raises(ObjectNotFoundError):
        storage_adapter.head_object(object_key)


@pytest.mark.integration
def test_head_returns_size_content_type_and_etag(
    storage_adapter: StorageAdapter,
    object_key: str,
    stored_object: None,
) -> None:
    info = storage_adapter.head_object(object_key)
    assert info.key == object_key
    assert info.size_bytes == len(ORIGINAL_BYTES)
    assert info.content_type == CONTENT_TYPE
    assert info.etag == f'"{hashlib.md5(ORIGINAL_BYTES).hexdigest()}"'


@pytest.mark.integration
def test_adapter_download_returns_original_bytes(
    storage_adapter: StorageAdapter,
    object_key: str,
    stored_object: None,
) -> None:
    downloaded = io.BytesIO()
    storage_adapter.download_fileobj(object_key, downloaded)
    assert downloaded.getvalue() == ORIGINAL_BYTES


@pytest.mark.integration
def test_presigned_get_returns_original_bytes_and_metadata(
    storage_adapter: StorageAdapter,
    object_key: str,
    stored_object: None,
) -> None:
    download = storage_adapter.create_download_url(object_key)
    assert download.method == "GET"
    assert download.headers == {}
    with urlopen(download.url, timeout=10) as response:
        assert response.status == 200
        assert response.headers["Content-Length"] == str(len(ORIGINAL_BYTES))
        assert response.headers["Content-Type"] == CONTENT_TYPE
        assert response.headers["ETag"] == (
            f'"{hashlib.md5(ORIGINAL_BYTES).hexdigest()}"'
        )
        assert response.read() == ORIGINAL_BYTES


@pytest.mark.integration
def test_replaying_upload_url_does_not_overwrite_original_bytes(
    storage_adapter: StorageAdapter,
    object_key: str,
    upload_url: PresignedURL,
    stored_object: None,
) -> None:
    assert len(ORIGINAL_BYTES) == len(DIFFERENT_SAME_LENGTH_BYTES)
    status, _ = _send_put(
        upload_url.url, upload_url.headers, DIFFERENT_SAME_LENGTH_BYTES
    )
    assert status in {400, 403, 409, 412}

    downloaded = io.BytesIO()
    storage_adapter.download_fileobj(object_key, downloaded)
    assert downloaded.getvalue() == ORIGINAL_BYTES


@pytest.mark.integration
def test_delete_removes_uploaded_object(
    storage_adapter: StorageAdapter,
    object_key: str,
    stored_object: None,
) -> None:
    storage_adapter.delete_object(object_key)
    with pytest.raises(ObjectNotFoundError):
        storage_adapter.head_object(object_key)


@pytest.mark.r2_smoke
@pytest.mark.skipif(
    os.getenv("RUN_R2_STORAGE_SMOKE") != "1",
    reason="Set RUN_R2_STORAGE_SMOKE=1 to opt in to the R2 smoke test.",
)
def test_r2_signed_length_and_conditional_overwrite() -> None:
    endpoint = os.getenv("R2_SMOKE_ENDPOINT", "")
    bucket = os.getenv("R2_SMOKE_BUCKET", "")
    access_key_id = os.getenv("R2_SMOKE_ACCESS_KEY_ID", "")
    secret_access_key = os.getenv("R2_SMOKE_SECRET_ACCESS_KEY", "")
    if not all((endpoint, bucket, access_key_id, secret_access_key)):
        pytest.fail("Set all R2_SMOKE_* settings before running this smoke test.")
    if not bucket.lower().endswith("-test"):
        pytest.fail("R2_SMOKE_BUCKET must be a dedicated bucket ending in '-test'.")

    settings = StorageSettings(
        endpoint=endpoint,
        bucket=bucket,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        region=os.getenv("R2_SMOKE_REGION", "auto"),
    )
    adapter = StorageAdapter(settings)
    object_key = f"r2-smoke/{uuid.uuid4().hex}.bin"
    content_type = "application/octet-stream"
    original = b"r2-smoke-first-payload"
    replacement = b"r2-smoke-other-payload"
    assert len(original) == len(replacement)

    try:
        upload = adapter.create_upload_url(
            object_key, content_type, size_bytes=len(original)
        )
        wrong_length_status, _ = _send_put(upload.url, upload.headers, original + b"x")
        assert wrong_length_status in {400, 403}

        status, _ = _send_put(upload.url, upload.headers, original)
        assert status in {200, 204}
        replay_status, _ = _send_put(upload.url, upload.headers, replacement)
        assert replay_status in {400, 403, 409, 412}

        stored = io.BytesIO()
        adapter.download_fileobj(object_key, stored)
        assert stored.getvalue() == original
    finally:
        adapter.delete_object(object_key)
