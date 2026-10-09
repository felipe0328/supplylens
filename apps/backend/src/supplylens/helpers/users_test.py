from datetime import UTC, datetime, timedelta, timezone

import pytest

from supplylens.domain.users import UserStatus
from supplylens.helpers.users import is_unexpired_pending

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "status",
    [
        UserStatus.ACCEPTED,
        UserStatus.REJECTED,
        UserStatus.EXPIRED,
        UserStatus.DELETED,
    ],
)
def test_is_unexpired_pending_is_false_for_other_statuses(status: UserStatus) -> None:
    assert is_unexpired_pending(status, NOW + timedelta(hours=1), now=NOW) is False


def test_is_unexpired_pending_treats_a_missing_expiry_as_open() -> None:
    assert is_unexpired_pending(UserStatus.PENDING, None, now=NOW) is True


def test_is_unexpired_pending_accepts_a_future_window() -> None:
    assert (
        is_unexpired_pending(UserStatus.PENDING, NOW + timedelta(seconds=1), now=NOW)
        is True
    )


def test_is_unexpired_pending_rejects_an_elapsed_window() -> None:
    assert (
        is_unexpired_pending(UserStatus.PENDING, NOW - timedelta(seconds=1), now=NOW)
        is False
    )


def test_is_unexpired_pending_treats_the_exact_expiry_as_elapsed() -> None:
    assert is_unexpired_pending(UserStatus.PENDING, NOW, now=NOW) is False


def test_is_unexpired_pending_treats_naive_timestamps_as_utc() -> None:
    naive_future = (NOW + timedelta(hours=1)).replace(tzinfo=None)
    naive_now = NOW.replace(tzinfo=None)

    assert is_unexpired_pending(UserStatus.PENDING, naive_future, now=naive_now) is True


def test_is_unexpired_pending_compares_non_utc_timestamps_in_utc() -> None:
    eastern = timezone(timedelta(hours=-5))
    expiry = datetime(2026, 10, 8, 8, 0, tzinfo=eastern)
    now = datetime(2026, 10, 8, 7, 30, tzinfo=eastern)

    assert is_unexpired_pending(UserStatus.PENDING, expiry, now=now) is True
