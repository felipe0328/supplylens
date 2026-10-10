from dataclasses import replace

import pytest

from supplylens.config import (
    AppEnvironment,
    JWTSettings,
    StorageSettings,
    get_app_environment,
    get_jwt_settings,
)


@pytest.fixture
def valid_storage_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("S3_ENDPOINT", "  https://storage.invalid/  ")
    monkeypatch.setenv("S3_BUCKET", "  synthetic-documents  ")
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "  synthetic-access-key  ")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "  synthetic-secret-key  ")
    for name in (
        "S3_REGION",
        "S3_UPLOAD_URL_TTL_SECONDS",
        "S3_DOWNLOAD_URL_TTL_SECONDS",
        "MAX_DOCUMENT_SIZE_BYTES",
    ):
        monkeypatch.delenv(name, raising=False)


def test_storage_settings_load_defaults_trim_strings_and_parse_values(
    valid_storage_environment: None,
) -> None:
    settings = StorageSettings.from_env()

    assert settings.endpoint == "https://storage.invalid"
    assert settings.bucket == "synthetic-documents"
    assert settings.access_key_id == "synthetic-access-key"
    assert settings.secret_access_key == "synthetic-secret-key"
    assert settings.region == "us-east-1"
    assert settings.upload_url_ttl_seconds == 900
    assert settings.download_url_ttl_seconds == 900
    assert settings.max_document_size_bytes == 26_214_400


def test_storage_settings_parse_overrides_and_trim_region(
    valid_storage_environment: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("S3_ENDPOINT", " http://localhost:9000/// ")
    monkeypatch.setenv("S3_REGION", " auto ")
    monkeypatch.setenv("S3_UPLOAD_URL_TTL_SECONDS", "1")
    monkeypatch.setenv("S3_DOWNLOAD_URL_TTL_SECONDS", "604800")
    monkeypatch.setenv("MAX_DOCUMENT_SIZE_BYTES", "2048")

    settings = StorageSettings.from_env()

    assert settings.endpoint == "http://localhost:9000"
    assert settings.region == "auto"
    assert settings.upload_url_ttl_seconds == 1
    assert settings.download_url_ttl_seconds == 604800
    assert settings.max_document_size_bytes == 2048


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("S3_ENDPOINT", "", "S3_ENDPOINT must not be blank"),
        ("S3_BUCKET", "  ", "S3_BUCKET must not be blank"),
        ("S3_ACCESS_KEY_ID", "", "S3_ACCESS_KEY_ID must not be blank"),
        ("S3_SECRET_ACCESS_KEY", "", "S3_SECRET_ACCESS_KEY must not be blank"),
        ("S3_REGION", "  ", "S3_REGION must not be blank"),
    ],
)
def test_storage_settings_reject_missing_required_values(
    valid_storage_environment: None,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
    message: str,
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=message):
        StorageSettings.from_env()


@pytest.mark.parametrize(
    "endpoint",
    ["relative/path", "ftp://storage.invalid", "http:///missing-host", " ", "https://"],
)
def test_storage_settings_reject_invalid_endpoint(
    valid_storage_environment: None,
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
) -> None:
    monkeypatch.setenv("S3_ENDPOINT", endpoint)
    with pytest.raises(ValueError, match="S3_ENDPOINT"):
        StorageSettings.from_env()


def test_storage_settings_reject_bucket_whitespace(
    valid_storage_environment: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("S3_BUCKET", "bucket name")
    with pytest.raises(ValueError, match="S3_BUCKET must not contain whitespace"):
        StorageSettings.from_env()


@pytest.mark.parametrize(
    ("variable", "value", "message"),
    [
        ("S3_UPLOAD_URL_TTL_SECONDS", "soon", "must be an integer"),
        ("S3_DOWNLOAD_URL_TTL_SECONDS", "1.5", "must be an integer"),
        ("S3_UPLOAD_URL_TTL_SECONDS", "0", "between 1 and 604800"),
        ("S3_DOWNLOAD_URL_TTL_SECONDS", "604801", "between 1 and 604800"),
        ("MAX_DOCUMENT_SIZE_BYTES", "large", "must be a positive integer"),
        ("MAX_DOCUMENT_SIZE_BYTES", "0", "must be a positive integer"),
        ("MAX_DOCUMENT_SIZE_BYTES", "-1", "must be a positive integer"),
    ],
)
def test_storage_settings_reject_malformed_or_out_of_range_numbers(
    valid_storage_environment: None,
    monkeypatch: pytest.MonkeyPatch,
    variable: str,
    value: str,
    message: str,
) -> None:
    monkeypatch.setenv(variable, value)
    with pytest.raises(ValueError, match=message):
        StorageSettings.from_env()


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("upload_url_ttl_seconds", "S3_UPLOAD_URL_TTL_SECONDS must be an integer"),
        (
            "max_document_size_bytes",
            "MAX_DOCUMENT_SIZE_BYTES must be a positive integer",
        ),
    ],
)
def test_storage_settings_reject_non_integer_constructor_values(
    valid_storage_environment: None,
    field: str,
    message: str,
) -> None:
    settings = StorageSettings.from_env()

    with pytest.raises(ValueError, match=message):
        replace(settings, **{field: True})


def test_application_environment_defaults_to_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    assert get_app_environment() is AppEnvironment.PRODUCTION


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (" DEVELOPMENT ", AppEnvironment.DEVELOPMENT),
        ("test", AppEnvironment.TESTING),
        ("Production", AppEnvironment.PRODUCTION),
    ],
)
def test_application_environment_trims_and_normalizes(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
    expected: AppEnvironment,
) -> None:
    monkeypatch.setenv("APP_ENV", value)
    assert get_app_environment() is expected


def test_application_environment_rejects_unknown_value_with_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    with pytest.raises(ValueError, match="APP_ENV must be") as raised:
        get_app_environment()
    assert isinstance(raised.value.__cause__, ValueError)


@pytest.fixture
def reset_jwt_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("supplylens.config.__jwt_settings", None)


def test_jwt_settings_load_a_trimmed_secret_and_default_ttl(
    reset_jwt_settings: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JWT_SECRET", "  synthetic-jwt-secret-with-32-characters  ")
    monkeypatch.delenv("JWT_ACCESS_TTL_SECONDS", raising=False)
    monkeypatch.delenv("JWT_REFRESH_TTL_SECONDS", raising=False)

    settings = get_jwt_settings()

    assert settings.secret == "synthetic-jwt-secret-with-32-characters"
    assert settings.access_ttl_seconds == 900
    assert settings.refresh_ttl_seconds == 604800
    assert get_jwt_settings() is settings


def test_jwt_settings_parse_a_custom_ttl(
    reset_jwt_settings: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JWT_SECRET", "synthetic-jwt-secret-with-32-characters")
    monkeypatch.setenv("JWT_ACCESS_TTL_SECONDS", "3600")

    assert get_jwt_settings().access_ttl_seconds == 3600


@pytest.mark.parametrize(
    ("secret", "ttl", "message"),
    [
        ("", "900", "JWT_SECRET must not be blank"),
        ("   ", "900", "JWT_SECRET must not be blank"),
        ("too-short", "900", "JWT_SECRET must be at least 32 characters"),
        ("synthetic-jwt-secret-with-32-characters", "soon", "must be an integer"),
        ("synthetic-jwt-secret-with-32-characters", "0", "between 1 and 3600"),
        ("synthetic-jwt-secret-with-32-characters", "3601", "between 1 and 3600"),
        (
            "synthetic-jwt-secret-with-32-characters",
            "604801",
            "between 1 and 3600",
        ),
    ],
)
def test_jwt_settings_reject_invalid_configuration(
    reset_jwt_settings: None,
    monkeypatch: pytest.MonkeyPatch,
    secret: str,
    ttl: str,
    message: str,
) -> None:
    monkeypatch.setenv("JWT_SECRET", secret)
    monkeypatch.setenv("JWT_ACCESS_TTL_SECONDS", ttl)

    with pytest.raises(ValueError, match=message):
        get_jwt_settings()


def test_jwt_settings_constructor_rejects_a_short_secret() -> None:
    with pytest.raises(ValueError, match="JWT_SECRET must be at least 32 characters"):
        JWTSettings(
            secret="too-short",
            access_ttl_seconds=900,
            refresh_ttl_seconds=604800,
        )
