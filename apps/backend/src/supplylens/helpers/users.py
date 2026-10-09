from datetime import UTC, datetime

from supplylens.domain.users import UserStatus


def is_unexpired_pending(
    status: UserStatus,
    pending_expires_at: datetime | None,
    *,
    now: datetime | None = None,
) -> bool:
    """Return whether a pending account is still inside its approval window."""
    if status is not UserStatus.PENDING:
        return False
    if pending_expires_at is None:
        return True
    return _as_utc(pending_expires_at) > _as_utc(now or datetime.now(UTC))


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
