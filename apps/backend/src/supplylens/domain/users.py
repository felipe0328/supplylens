import enum


class UserRole(enum.Enum):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"


class UserStatus(enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    DELETED = "DELETED"
