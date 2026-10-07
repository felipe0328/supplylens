import pytest
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError
from argon2.profiles import CHEAPEST

from supplylens.tools.encryption import hash_password, verify_password


def test_hash_password_verifies_without_rehash() -> None:
    password = "synthetic-password"
    password_hash = hash_password(password)

    assert password_hash.startswith("$argon2id$")
    assert password_hash != password
    assert verify_password(password, password_hash) == (True, False)


def test_hash_password_uses_a_unique_salt() -> None:
    password = "synthetic-password"

    assert hash_password(password) != hash_password(password)


def test_verify_password_rejects_mismatch() -> None:
    password_hash = hash_password("synthetic-password")

    assert verify_password("other-password", password_hash) == (False, False)


def test_verify_password_reports_when_rehash_is_required() -> None:
    password = "synthetic-password"
    password_hash = PasswordHasher.from_parameters(CHEAPEST).hash(password)

    assert verify_password(password, password_hash) == (True, True)


def test_verify_password_rejects_invalid_hash() -> None:
    with pytest.raises(InvalidHashError):
        verify_password("synthetic-password", "not-an-argon2-hash")
