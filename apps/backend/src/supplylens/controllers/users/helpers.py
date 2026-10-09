from email_validator import EmailNotValidError, validate_email

from .exceptions import InvalidEmailAddressError, InvalidPasswordError


def validate_email_address(email: str) -> str:
    try:
        validated_email = validate_email(email, check_deliverability=False)
        return validated_email.normalized.lower()
    except EmailNotValidError as e:
        raise InvalidEmailAddressError(f"Invalid email address: {e}") from e


def validate_password(password: str) -> str:
    if len(password) < 8:
        raise InvalidPasswordError("Password must be at least 8 characters long")
    if len(password) > 128:
        raise InvalidPasswordError("Password must be no more than 128 characters long")
    if not any(char.isdigit() for char in password):
        raise InvalidPasswordError("Password must contain at least one digit")
    if not any(char.isalpha() for char in password):
        raise InvalidPasswordError("Password must contain at least one letter")
    if not any(char.isupper() for char in password):
        raise InvalidPasswordError(
            "Password must contain at least one uppercase letter"
        )
    if not any(char.islower() for char in password):
        raise InvalidPasswordError(
            "Password must contain at least one lowercase letter"
        )
    return password
