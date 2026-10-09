class UserAlreadyExistsError(Exception):
    """User already exists."""


class UserPendingError(Exception):
    """User is waiting for approval."""


class InvalidEmailAddressError(Exception):
    """Invalid email address."""


class InvalidPasswordError(Exception):
    """Invalid password."""


class UserNotFoundError(Exception):
    """User not found."""


class InvalidCredentialsError(Exception):
    """Invalid credentials."""
