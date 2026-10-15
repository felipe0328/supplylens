class UserAlreadyExistsError(Exception):
    """User already exists."""


class UserPendingError(Exception):
    """User is waiting for approval."""


class InvalidEmailAddressError(Exception):
    """Invalid email address."""


class InvalidPasswordError(Exception):
    """Invalid password."""


class InvalidCredentialsError(Exception):
    """The email and password did not match an account."""


class AccountNotAcceptedError(Exception):
    """The account exists but cannot start a session."""


class InvalidOrExpiredRefreshTokenError(Exception):
    """The refresh token is invalid or expired."""


class UserNotFoundError(Exception):
    """The requested user does not exist."""


class UserNotAwaitingApprovalError(Exception):
    """The user is not inside an open pending approval window."""


class ApprovalForbiddenError(Exception):
    """The caller cannot approve or reject users."""
