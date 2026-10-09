class UserAlreadyExistsError(Exception):
    """User already exists."""


class UserPendingError(Exception):
    """User is waiting for approval."""


class InvalidEmailAddressError(Exception):
    """Invalid email address."""


class InvalidPasswordError(Exception):
    """Invalid password."""
