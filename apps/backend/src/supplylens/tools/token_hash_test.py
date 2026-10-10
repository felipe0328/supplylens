import hashlib

from supplylens.tools.token_hash import hash_token


def test_hash_token_is_stable_sha256() -> None:
    token = "synthetic-refresh-token"

    assert hash_token(token) == hashlib.sha256(token.encode()).hexdigest()
    assert hash_token(token) != token
