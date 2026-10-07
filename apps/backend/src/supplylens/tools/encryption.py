from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

__hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return __hasher.hash(password)


def verify_password(password: str, hash: str) -> tuple[bool, bool]:
    """
    Verify a password against a hash and return a tuple containing a
    boolean indicating whether the password is correct and a
    boolean indicating whether the hash needs to be rehashed.
    """

    try:
        __hasher.verify(hash, password)
        return True, __hasher.check_needs_rehash(hash)
    except VerifyMismatchError:
        return False, False
