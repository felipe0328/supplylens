from dataclasses import FrozenInstanceError

import pytest

from supplylens.port.storage.storage import (
    ObjectInfo,
    ObjectNotFoundError,
    PresignedURL,
    StorageError,
    StorageUnavailableError,
)


def test_object_info_preserves_storage_metadata() -> None:
    info = ObjectInfo(
        key="documents/synthetic.pdf",
        size_bytes=512,
        content_type="application/pdf",
        etag='"synthetic-etag"',
    )

    assert info.key == "documents/synthetic.pdf"
    assert info.size_bytes == 512
    assert info.content_type == "application/pdf"
    assert info.etag == '"synthetic-etag"'


def test_object_info_allows_absent_optional_metadata() -> None:
    info = ObjectInfo("documents/unknown", 0, None, None)

    assert info.content_type is None
    assert info.etag is None


def test_presigned_url_carries_request_contract() -> None:
    headers = {"Content-Type": "application/pdf", "If-None-Match": "*"}
    signed = PresignedURL(
        url="https://storage.invalid/synthetic",
        method="PUT",
        headers=headers,
        expires_in_seconds=900,
    )

    assert signed.url == "https://storage.invalid/synthetic"
    assert signed.method == "PUT"
    assert signed.headers == headers
    assert signed.expires_in_seconds == 900


@pytest.mark.parametrize(
    ("value", "field"),
    [
        (ObjectInfo("key", 1, None, None), "size_bytes"),
        (PresignedURL("url", "GET", {}, 1), "expires_in_seconds"),
    ],
)
def test_storage_response_values_are_frozen(
    value: ObjectInfo | PresignedURL, field: str
) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(value, field, 2)


@pytest.mark.parametrize("error_type", [ObjectNotFoundError, StorageUnavailableError])
def test_storage_errors_share_the_port_base(error_type: type[StorageError]) -> None:
    with pytest.raises(StorageError) as raised:
        raise error_type("synthetic storage failure")

    assert type(raised.value) is error_type
