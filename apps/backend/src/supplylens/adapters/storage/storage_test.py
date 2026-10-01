from __future__ import annotations

from io import BytesIO
from urllib.parse import parse_qs, urlsplit

import pytest
from botocore.exceptions import (
    ClientError,
    ConnectTimeoutError,
    EndpointConnectionError,
)

from supplylens.adapters.storage.storage import StorageAdapter
from supplylens.config import StorageSettings
from supplylens.port.storage.storage import (
    ObjectNotFoundError,
    StorageUnavailableError,
)


class FakeS3Client:
    def __init__(self) -> None:
        self.presign_result = "https://storage.invalid/signed-object"
        self.presign_calls: list[dict[str, object]] = []
        self.head_calls: list[dict[str, str]] = []
        self.download_calls: list[dict[str, object]] = []
        self.delete_calls: list[dict[str, str]] = []
        self.head_result: dict[str, object] = {
            "ContentLength": 512,
            "ContentType": "application/pdf",
            "ETag": '"etag-123"',
        }
        self.errors: dict[str, Exception] = {}

    def generate_presigned_url(
        self,
        ClientMethod: str,
        Params: dict[str, object],
        ExpiresIn: int,
        HttpMethod: str,
    ) -> str:
        self.presign_calls.append(
            {
                "ClientMethod": ClientMethod,
                "Params": Params,
                "ExpiresIn": ExpiresIn,
                "HttpMethod": HttpMethod,
            }
        )
        self._raise("presign")
        return self.presign_result

    def head_object(self, Bucket: str, Key: str) -> dict[str, object]:
        self.head_calls.append({"Bucket": Bucket, "Key": Key})
        self._raise("head")
        return self.head_result

    def download_fileobj(self, Bucket: str, Key: str, Fileobj: BytesIO) -> None:
        self.download_calls.append({"Bucket": Bucket, "Key": Key, "Fileobj": Fileobj})
        self._raise("download")
        Fileobj.write(b"synthetic pdf")

    def delete_object(self, Bucket: str, Key: str) -> None:
        self.delete_calls.append({"Bucket": Bucket, "Key": Key})
        self._raise("delete")

    def _raise(self, operation: str) -> None:
        error = self.errors.get(operation)
        if error is not None:
            raise error


@pytest.fixture
def storage_settings() -> StorageSettings:
    return StorageSettings(
        endpoint="http://localhost:9000",
        bucket="test-documents",
        access_key_id="synthetic-access-key",
        secret_access_key="synthetic-secret-key",
        region="us-east-1",
        upload_url_ttl_seconds=900,
        download_url_ttl_seconds=600,
        max_document_size_bytes=1024,
    )


@pytest.fixture
def storage_adapter(
    storage_settings: StorageSettings,
) -> tuple[StorageAdapter, FakeS3Client]:
    client = FakeS3Client()
    return StorageAdapter(settings=storage_settings, s3_client=client), client


def test_upload_url_returns_contract_and_signs_exact_parameters(
    storage_adapter: tuple[StorageAdapter, FakeS3Client],
) -> None:
    adapter, client = storage_adapter

    upload = adapter.create_upload_url(
        "documents/test/original.pdf", "application/pdf", size_bytes=512
    )

    assert upload.url == client.presign_result
    assert upload.method == "PUT"
    assert upload.expires_in_seconds == 900
    assert upload.headers == {"Content-Type": "application/pdf", "If-None-Match": "*"}
    assert client.presign_calls == [
        {
            "ClientMethod": "put_object",
            "Params": {
                "Bucket": "test-documents",
                "Key": "documents/test/original.pdf",
                "ContentType": "application/pdf",
                "ContentLength": 512,
                "IfNoneMatch": "*",
            },
            "ExpiresIn": 900,
            "HttpMethod": "PUT",
        }
    ]


def test_boto3_signature_includes_required_upload_headers(
    storage_settings: StorageSettings,
) -> None:
    adapter = StorageAdapter(settings=storage_settings)
    upload = adapter.create_upload_url(
        "documents/test/original.pdf", "application/pdf", size_bytes=512
    )

    signed_headers = parse_qs(urlsplit(upload.url).query)["X-Amz-SignedHeaders"][
        0
    ].split(";")
    assert "content-length" in signed_headers
    assert "content-type" in signed_headers
    assert "if-none-match" in signed_headers


def test_upload_url_allows_max_size_and_expiration_boundaries(
    storage_adapter: tuple[StorageAdapter, FakeS3Client],
) -> None:
    adapter, client = storage_adapter

    upload = adapter.create_upload_url(
        "documents/max.pdf", "application/pdf", size_bytes=1024, expiration=604800
    )

    assert upload.expires_in_seconds == 604800
    assert client.presign_calls[0]["ExpiresIn"] == 604800


@pytest.mark.parametrize("size_bytes", [0, -1, True, 1025])
def test_upload_url_rejects_invalid_or_over_limit_sizes(
    storage_adapter: tuple[StorageAdapter, FakeS3Client], size_bytes: int
) -> None:
    adapter, client = storage_adapter
    expected = "MAX_DOCUMENT_SIZE_BYTES" if size_bytes == 1025 else "positive integer"

    with pytest.raises(ValueError, match=expected):
        adapter.create_upload_url("documents/a.pdf", "application/pdf", size_bytes)
    assert client.presign_calls == []


@pytest.mark.parametrize("expiration", [0, -1, 604801, True, 1.5])
def test_upload_and_download_urls_reject_invalid_expiration(
    storage_adapter: tuple[StorageAdapter, FakeS3Client], expiration: object
) -> None:
    adapter, client = storage_adapter
    with pytest.raises(ValueError, match="expiration must be an integer"):
        adapter.create_upload_url(
            "documents/a.pdf",
            "application/pdf",
            10,
            expiration=expiration,  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="expiration must be an integer"):
        adapter.create_download_url("documents/a.pdf", expiration=expiration)  # type: ignore[arg-type]
    assert client.presign_calls == []


def test_download_url_returns_contract_and_accepts_minimum_expiration(
    storage_adapter: tuple[StorageAdapter, FakeS3Client],
) -> None:
    adapter, client = storage_adapter

    download = adapter.create_download_url("documents/test/original.pdf", expiration=1)

    assert download.url == client.presign_result
    assert download.method == "GET"
    assert download.headers == {}
    assert download.expires_in_seconds == 1
    assert client.presign_calls == [
        {
            "ClientMethod": "get_object",
            "Params": {
                "Bucket": "test-documents",
                "Key": "documents/test/original.pdf",
            },
            "ExpiresIn": 1,
            "HttpMethod": "GET",
        }
    ]


def test_download_url_uses_configured_default_expiration(
    storage_adapter: tuple[StorageAdapter, FakeS3Client],
) -> None:
    adapter, client = storage_adapter

    download = adapter.create_download_url("documents/test/original.pdf")

    assert download.expires_in_seconds == 600
    assert client.presign_calls[0]["ExpiresIn"] == 600


def test_head_object_returns_metadata_and_passes_bucket_and_key(
    storage_adapter: tuple[StorageAdapter, FakeS3Client],
) -> None:
    adapter, client = storage_adapter

    info = adapter.head_object("documents/test/original.pdf")

    assert info.key == "documents/test/original.pdf"
    assert info.size_bytes == 512
    assert info.content_type == "application/pdf"
    assert info.etag == '"etag-123"'
    assert client.head_calls == [
        {"Bucket": "test-documents", "Key": "documents/test/original.pdf"}
    ]


def test_head_object_defaults_missing_metadata(
    storage_adapter: tuple[StorageAdapter, FakeS3Client],
) -> None:
    adapter, client = storage_adapter
    client.head_result = {}
    info = adapter.head_object("documents/metadata-free")
    assert (info.size_bytes, info.content_type, info.etag) == (0, None, None)


def test_download_fileobj_and_delete_object_call_client(
    storage_adapter: tuple[StorageAdapter, FakeS3Client],
) -> None:
    adapter, client = storage_adapter
    target = BytesIO()

    adapter.download_fileobj("documents/test/original.pdf", target)
    adapter.delete_object("documents/test/original.pdf")

    assert target.getvalue() == b"synthetic pdf"
    assert client.download_calls == [
        {
            "Bucket": "test-documents",
            "Key": "documents/test/original.pdf",
            "Fileobj": target,
        }
    ]
    assert client.delete_calls == [
        {"Bucket": "test-documents", "Key": "documents/test/original.pdf"}
    ]


def _client_error(code: str, status: int) -> ClientError:
    return ClientError(
        {
            "Error": {"Code": code, "Message": "synthetic provider failure"},
            "ResponseMetadata": {"HTTPStatusCode": status},
        },
        "SyntheticOperation",
    )


@pytest.mark.parametrize(
    ("code", "status", "expected_error"),
    [
        ("NoSuchKey", 404, ObjectNotFoundError),
        ("UnexpectedCode", 404, ObjectNotFoundError),
        ("NoSuchBucket", 404, ClientError),
        ("SlowDown", 503, StorageUnavailableError),
        ("UnexpectedCode", 503, StorageUnavailableError),
        ("AccessDenied", 403, ClientError),
    ],
)
@pytest.mark.parametrize(
    "operation", ["upload_url", "download_url", "head", "download", "delete"]
)
def test_provider_errors_are_translated_or_preserved_with_cause(
    storage_adapter: tuple[StorageAdapter, FakeS3Client],
    code: str,
    status: int,
    expected_error: type[Exception],
    operation: str,
) -> None:
    adapter, client = storage_adapter
    provider_error = _client_error(code, status)
    provider_method = "presign" if operation.endswith("_url") else operation
    client.errors[provider_method] = provider_error

    def invoke() -> object:
        if operation == "upload_url":
            return adapter.create_upload_url("documents/a.pdf", "application/pdf", 10)
        if operation == "download_url":
            return adapter.create_download_url("documents/a.pdf")
        if operation == "head":
            return adapter.head_object("documents/a.pdf")
        if operation == "download":
            return adapter.download_fileobj("documents/a.pdf", BytesIO())
        return adapter.delete_object("documents/a.pdf")

    with pytest.raises(expected_error) as raised:
        invoke()
    if expected_error in (ObjectNotFoundError, StorageUnavailableError):
        assert raised.value.__cause__ is provider_error
    else:
        assert raised.value is provider_error


@pytest.mark.parametrize(
    "operation", ["upload_url", "download_url", "head", "download", "delete"]
)
@pytest.mark.parametrize("failure", ["timeout", "endpoint"])
def test_transport_errors_become_unavailable_with_cause(
    storage_adapter: tuple[StorageAdapter, FakeS3Client],
    operation: str,
    failure: str,
) -> None:
    adapter, client = storage_adapter
    provider_error: Exception
    if failure == "timeout":
        provider_error = ConnectTimeoutError(endpoint_url="http://storage.invalid")
    else:
        provider_error = EndpointConnectionError(endpoint_url="http://storage.invalid")
    provider_method = "presign" if operation.endswith("_url") else operation
    client.errors[provider_method] = provider_error

    with pytest.raises(StorageUnavailableError) as raised:
        if operation == "upload_url":
            adapter.create_upload_url("documents/a.pdf", "application/pdf", 10)
        elif operation == "download_url":
            adapter.create_download_url("documents/a.pdf")
        elif operation == "head":
            adapter.head_object("documents/a.pdf")
        elif operation == "download":
            adapter.download_fileobj("documents/a.pdf", BytesIO())
        else:
            adapter.delete_object("documents/a.pdf")
    assert raised.value.__cause__ is provider_error
