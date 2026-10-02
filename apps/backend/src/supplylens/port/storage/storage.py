from dataclasses import dataclass
from typing import BinaryIO, Protocol


class StorageError(Exception):
    """Base error for object storage operations."""


class ObjectNotFoundError(StorageError):
    """The requested object does not exist in storage."""


class StorageUnavailableError(StorageError):
    """Storage could not be reached or could not complete the operation."""


class UploadTooLargeError(ValueError):
    """The declared upload size exceeds the configured document limit."""


@dataclass(frozen=True)
class ObjectInfo:
    key: str
    size_bytes: int
    content_type: str | None
    etag: str | None


@dataclass(frozen=True)
class PresignedURL:
    url: str
    method: str
    headers: dict[str, str]
    expires_in_seconds: int


class ObjectStorage(Protocol):
    def create_upload_url(
        self,
        object_key: str,
        content_type: str,
        size_bytes: int,
        expiration: int | None = None,
    ) -> PresignedURL: ...

    def head_object(self, object_key: str) -> ObjectInfo: ...

    def download_fileobj(self, object_key: str, target: BinaryIO) -> None: ...

    def create_download_url(
        self,
        object_key: str,
        expiration: int | None = None,
    ) -> PresignedURL: ...

    def delete_object(self, object_key: str) -> None: ...
