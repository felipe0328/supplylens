from supplylens.domain.users import UserStatus

TOKEN_TYPE = "Bearer"

INVALID_CREDENTIALS = "Invalid email or password."
INVALID_REFRESH_TOKEN = "Invalid or expired refresh token."

EMAIL_PENDING = "This email is already waiting for approval."
ACCOUNT_ALREADY_EXISTS = "An account with this email already exists. Log in instead."

ACCOUNT_WAITING_FOR_APPROVAL = "This account is waiting for approval."
ACCOUNT_NOT_APPROVED = "This account was not approved."
REGISTRATION_EXPIRED = "This registration expired. Register again."
ACCOUNT_NOT_AVAILABLE = "This account is not available."

ACCOUNT_STATUS_MESSAGES = {
    UserStatus.PENDING: ACCOUNT_WAITING_FOR_APPROVAL,
    UserStatus.REJECTED: ACCOUNT_NOT_APPROVED,
    UserStatus.EXPIRED: REGISTRATION_EXPIRED,
    UserStatus.DELETED: ACCOUNT_NOT_AVAILABLE,
}
