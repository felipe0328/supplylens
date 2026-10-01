from __future__ import annotations

from typing import TYPE_CHECKING, BinaryIO

import boto3
from botocore.config import Config
from botocore.exceptions import (
    ClientError,
    ConnectionClosedError,
    ConnectTimeoutError,
    EndpointConnectionError,
    HTTPClientError,
    ReadTimeoutError,
)

from supplylens.config import StorageSettings
from supplylens.port.storage.storage import (
    ObjectInfo,
    ObjectNotFoundError,
    ObjectStorage,
    PresignedURL,
    StorageUnavailableError,
)

if TYPE_CHECKING:
    from types_boto3_s3.client import S3Client
    from types_boto3_s3.type_defs import HeadObjectOutputTypeDef


_MISSING_OBJECT_CODES = {"404", "NoSuchKey", "NoSuchObject", "NotFound"}
_UNAVAILABLE_CODES = {
    "InternalError",
    "RequestTimeout",
    "RequestTimeoutException",
    "ServiceUnavailable",
    "SlowDown",
}


class StorageAdapter(ObjectStorage):
    def __init__(
        self,
        settings: StorageSettings | None = None,
        s3_client: S3Client | None = None,
    ) -> None:
        self._settings = (
            settings if settings is not None else StorageSettings.from_env()
        )
        self._client = s3_client
        if self._client is None:
            self._client = boto3.client(
                "s3",
                aws_access_key_id=self._settings.access_key_id,
                aws_secret_access_key=self._settings.secret_access_key,
                endpoint_url=self._settings.endpoint,
                region_name=self._settings.region,
                config=Config(signature_version="s3v4"),
            )

    @staticmethod
    def _validate_expiration(expiration: int) -> int:
        if type(expiration) is not int or not 1 <= expiration <= 604800:
            raise ValueError("expiration must be an integer from 1 to 604800 seconds.")
        return expiration

    @staticmethod
    def _translate_storage_error(error: ClientError) -> None:
        response = error.response
        code = str(response.get("Error", {}).get("Code", ""))
        status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if code in _MISSING_OBJECT_CODES or (status == 404 and code != "NoSuchBucket"):
            raise ObjectNotFoundError("The requested object was not found.") from error
        if code in _UNAVAILABLE_CODES or (isinstance(status, int) and status >= 500):
            raise StorageUnavailableError("Object storage is unavailable.") from error

    @staticmethod
    def _raise_unavailable_error(
        error: ConnectTimeoutError
        | ConnectionClosedError
        | EndpointConnectionError
        | HTTPClientError
        | ReadTimeoutError,
    ) -> None:
        raise StorageUnavailableError("Object storage is unavailable.") from error

    def create_upload_url(
        self,
        object_key: str,
        content_type: str,
        size_bytes: int,
        expiration: int | None = None,
    ) -> PresignedURL:
        if type(size_bytes) is not int or size_bytes <= 0:
            raise ValueError("size_bytes must be a positive integer.")
        if size_bytes > self._settings.max_document_size_bytes:
            raise ValueError(
                "Upload exceeds MAX_DOCUMENT_SIZE_BYTES "
                f"({self._settings.max_document_size_bytes} bytes)."
            )
        expires_in = self._validate_expiration(
            self._settings.upload_url_ttl_seconds if expiration is None else expiration
        )
        try:
            response = self._client.generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": self._settings.bucket,
                    "Key": object_key,
                    "ContentType": content_type,
                    "ContentLength": size_bytes,
                    "IfNoneMatch": "*",
                },
                ExpiresIn=expires_in,
                HttpMethod="PUT",
            )
        except ClientError as error:
            self._translate_storage_error(error)
            raise
        except (
            ConnectTimeoutError,
            ConnectionClosedError,
            EndpointConnectionError,
            HTTPClientError,
            ReadTimeoutError,
        ) as error:
            self._raise_unavailable_error(error)

        return PresignedURL(
            url=response,
            method="PUT",
            headers={"Content-Type": content_type, "If-None-Match": "*"},
            expires_in_seconds=expires_in,
        )

    def head_object(self, object_key: str) -> ObjectInfo:
        try:
            response: HeadObjectOutputTypeDef = self._client.head_object(
                Bucket=self._settings.bucket,
                Key=object_key,
            )
        except ClientError as error:
            self._translate_storage_error(error)
            raise
        except (
            ConnectTimeoutError,
            ConnectionClosedError,
            EndpointConnectionError,
            HTTPClientError,
            ReadTimeoutError,
        ) as error:
            self._raise_unavailable_error(error)

        return ObjectInfo(
            key=object_key,
            size_bytes=response.get("ContentLength", 0),
            content_type=response.get("ContentType"),
            etag=response.get("ETag"),
        )

    def download_fileobj(self, object_key: str, target: BinaryIO) -> None:
        try:
            self._client.download_fileobj(
                Bucket=self._settings.bucket,
                Key=object_key,
                Fileobj=target,
            )
        except ClientError as error:
            self._translate_storage_error(error)
            raise
        except (
            ConnectTimeoutError,
            ConnectionClosedError,
            EndpointConnectionError,
            HTTPClientError,
            ReadTimeoutError,
        ) as error:
            self._raise_unavailable_error(error)

    def create_download_url(
        self, object_key: str, expiration: int | None = None
    ) -> PresignedURL:
        expires_in = self._validate_expiration(
            self._settings.download_url_ttl_seconds
            if expiration is None
            else expiration
        )
        try:
            response = self._client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": self._settings.bucket, "Key": object_key},
                ExpiresIn=expires_in,
                HttpMethod="GET",
            )
        except ClientError as error:
            self._translate_storage_error(error)
            raise
        except (
            ConnectTimeoutError,
            ConnectionClosedError,
            EndpointConnectionError,
            HTTPClientError,
            ReadTimeoutError,
        ) as error:
            self._raise_unavailable_error(error)

        return PresignedURL(
            url=response,
            method="GET",
            headers={},
            expires_in_seconds=expires_in,
        )

    def delete_object(self, object_key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._settings.bucket, Key=object_key)
        except ClientError as error:
            self._translate_storage_error(error)
            raise
        except (
            ConnectTimeoutError,
            ConnectionClosedError,
            EndpointConnectionError,
            HTTPClientError,
            ReadTimeoutError,
        ) as error:
            self._raise_unavailable_error(error)
