import pytest

from supplylens.controllers.users.exceptions import (
    InvalidEmailAddressError,
    InvalidPasswordError,
)
from supplylens.controllers.users.validation import (
    validate_email_address,
    validate_password,
)


def test_validate_email_address_returns_lowercase_normalized_address() -> None:
    assert validate_email_address("Operator@Example.com") == "operator@example.com"


def test_validate_email_address_rejects_invalid_address() -> None:
    with pytest.raises(InvalidEmailAddressError):
        validate_email_address("not-an-email")


@pytest.mark.parametrize(
    "password",
    [
        "short1A",
        "nouppercase1",
        "NOLOWERCASE1",
        "NoDigitsHere",
        "abcdefgh",
    ],
)
def test_validate_password_rejects_weak_passwords(password: str) -> None:
    with pytest.raises(InvalidPasswordError):
        validate_password(password)


def test_validate_password_accepts_a_mixed_password() -> None:
    assert validate_password("Synthetic1") == "Synthetic1"


def test_validate_password_rejects_a_password_longer_than_128_characters() -> None:
    with pytest.raises(InvalidPasswordError, match="128"):
        validate_password(f"A1{'a' * 127}")


def test_validate_password_rejects_a_password_without_a_letter() -> None:
    with pytest.raises(InvalidPasswordError, match="letter"):
        validate_password("12345678")
