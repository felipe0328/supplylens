import os
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv()


class AppEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TESTING = "test"
    PRODUCTION = "production"


def _required_trimmed(value: str, name: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise ValueError(f"{name} must not be blank.")
    return trimmed


def _ttl_seconds(value: str | int, name: str, *, maximum: int = 604800) -> int:
    if type(value) is not int and not isinstance(value, str):
        raise ValueError(f"{name} must be an integer.")
    try:
        seconds = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if not 1 <= seconds <= maximum:
        raise ValueError(f"{name} must be between 1 and {maximum} seconds.")
    return seconds


def _positive_int(value: str | int, name: str) -> int:
    if type(value) is not int and not isinstance(value, str):
        raise ValueError(f"{name} must be a positive integer.")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer.") from exc
    if number <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return number


@dataclass(frozen=True)
class StorageSettings:
    endpoint: str
    bucket: str
    access_key_id: str
    secret_access_key: str
    region: str = "us-east-1"
    upload_url_ttl_seconds: int = 900
    download_url_ttl_seconds: int = 900
    max_document_size_bytes: int = 26_214_400

    def __post_init__(self) -> None:
        endpoint = _required_trimmed(self.endpoint, "S3_ENDPOINT")
        parsed_endpoint = urlsplit(endpoint)
        if (
            parsed_endpoint.scheme not in {"http", "https"}
            or not parsed_endpoint.netloc
        ):
            raise ValueError("S3_ENDPOINT must be an absolute HTTP or HTTPS URL.")
        object.__setattr__(self, "endpoint", endpoint.rstrip("/"))
        bucket = _required_trimmed(self.bucket, "S3_BUCKET")
        if any(character.isspace() for character in bucket):
            raise ValueError("S3_BUCKET must not contain whitespace.")
        object.__setattr__(self, "bucket", bucket)
        object.__setattr__(
            self,
            "access_key_id",
            _required_trimmed(self.access_key_id, "S3_ACCESS_KEY_ID"),
        )
        object.__setattr__(
            self,
            "secret_access_key",
            _required_trimmed(self.secret_access_key, "S3_SECRET_ACCESS_KEY"),
        )
        object.__setattr__(self, "region", _required_trimmed(self.region, "S3_REGION"))
        object.__setattr__(
            self,
            "upload_url_ttl_seconds",
            _ttl_seconds(self.upload_url_ttl_seconds, "S3_UPLOAD_URL_TTL_SECONDS"),
        )
        object.__setattr__(
            self,
            "download_url_ttl_seconds",
            _ttl_seconds(self.download_url_ttl_seconds, "S3_DOWNLOAD_URL_TTL_SECONDS"),
        )
        object.__setattr__(
            self,
            "max_document_size_bytes",
            _positive_int(self.max_document_size_bytes, "MAX_DOCUMENT_SIZE_BYTES"),
        )

    @classmethod
    def from_env(cls) -> "StorageSettings":
        return cls(
            endpoint=os.getenv("S3_ENDPOINT", ""),
            bucket=os.getenv("S3_BUCKET", ""),
            access_key_id=os.getenv("S3_ACCESS_KEY_ID", ""),
            secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY", ""),
            region=os.getenv("S3_REGION", "us-east-1"),
            upload_url_ttl_seconds=_ttl_seconds(
                os.getenv("S3_UPLOAD_URL_TTL_SECONDS", "900"),
                "S3_UPLOAD_URL_TTL_SECONDS",
            ),
            download_url_ttl_seconds=_ttl_seconds(
                os.getenv("S3_DOWNLOAD_URL_TTL_SECONDS", "900"),
                "S3_DOWNLOAD_URL_TTL_SECONDS",
            ),
            max_document_size_bytes=_positive_int(
                os.getenv("MAX_DOCUMENT_SIZE_BYTES", "26214400"),
                "MAX_DOCUMENT_SIZE_BYTES",
            ),
        )


def get_app_environment() -> AppEnvironment:
    value = os.getenv("APP_ENV", AppEnvironment.PRODUCTION.value).strip().lower()
    try:
        return AppEnvironment(value)
    except ValueError as exc:
        raise ValueError(
            "APP_ENV must be 'development', 'test', or 'production'."
        ) from exc


@dataclass(frozen=True)
class JWTSettings:
    secret: str
    access_ttl_seconds: int
    refresh_ttl_seconds: int

    def __post_init__(self) -> None:
        secret = _required_trimmed(self.secret, "JWT_SECRET")
        if len(secret) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters.")
        object.__setattr__(self, "secret", secret)
        object.__setattr__(
            self,
            "access_ttl_seconds",
            _ttl_seconds(
                self.access_ttl_seconds,
                "JWT_ACCESS_TTL_SECONDS",
                maximum=3600,
            ),
        )
        object.__setattr__(
            self,
            "refresh_ttl_seconds",
            _ttl_seconds(
                self.refresh_ttl_seconds,
                "JWT_REFRESH_TTL_SECONDS",
                maximum=604800,
            ),
        )


__jwt_settings: JWTSettings | None = None


def get_jwt_settings() -> JWTSettings:
    global __jwt_settings
    if __jwt_settings is None:
        __jwt_settings = JWTSettings(
            secret=os.getenv("JWT_SECRET", ""),
            access_ttl_seconds=os.getenv("JWT_ACCESS_TTL_SECONDS", "900"),
            refresh_ttl_seconds=os.getenv("JWT_REFRESH_TTL_SECONDS", "604800"),
        )
    return __jwt_settings
