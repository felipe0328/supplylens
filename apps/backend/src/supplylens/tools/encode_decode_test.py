from datetime import UTC, datetime, timedelta

import jwt
import pytest

from supplylens.config import JWTSettings
from supplylens.tools.encode_decode import decode_jwt, encode_jwt

JWT_SECRET = "synthetic-jwt-secret-with-32-characters"


@pytest.fixture
def jwt_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = JWTSettings(secret=JWT_SECRET, access_ttl_seconds=900)
    monkeypatch.setattr(
        "supplylens.tools.encode_decode.get_jwt_settings",
        lambda: settings,
    )


def _payload(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "sub": "12345678-1234-5678-1234-567812345678",
        "role": "OPERATOR",
        "exp": datetime.now(UTC) + timedelta(minutes=15),
    }
    values.update(overrides)
    return values


def test_encode_jwt_round_trips_required_claims(jwt_settings: None) -> None:
    token = encode_jwt(_payload())

    decoded = decode_jwt(token)

    assert decoded["sub"] == "12345678-1234-5678-1234-567812345678"
    assert decoded["role"] == "OPERATOR"
    assert isinstance(decoded["exp"], int)


def test_decode_jwt_rejects_an_expired_token(jwt_settings: None) -> None:
    token = encode_jwt(_payload(exp=datetime.now(UTC) - timedelta(seconds=5)))

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_jwt(token)


@pytest.mark.parametrize("claim", ["exp", "sub", "role"])
def test_decode_jwt_requires_exp_sub_and_role(jwt_settings: None, claim: str) -> None:
    payload = _payload()
    del payload[claim]
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    with pytest.raises(jwt.MissingRequiredClaimError):
        decode_jwt(token)


def test_decode_jwt_rejects_a_different_algorithm(jwt_settings: None) -> None:
    token = jwt.encode(_payload(), JWT_SECRET, algorithm="HS384")

    with pytest.raises(jwt.InvalidAlgorithmError):
        decode_jwt(token)


def test_decode_jwt_rejects_a_different_secret(jwt_settings: None) -> None:
    token = jwt.encode(
        _payload(),
        "another-synthetic-secret-32-characters",
        algorithm="HS256",
    )

    with pytest.raises(jwt.InvalidSignatureError):
        decode_jwt(token)
