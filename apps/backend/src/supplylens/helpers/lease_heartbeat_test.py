import time
from threading import Event

import pytest

from supplylens.helpers.lease_heartbeat import LeaseLostError, run_with_lease_heartbeat


def test_run_with_lease_heartbeat_completes_without_renewal_for_fast_work() -> None:
    renewals = 0

    def renew() -> bool:
        nonlocal renewals
        renewals += 1
        return True

    run_with_lease_heartbeat(lambda: None, renew, interval_seconds=1)

    assert renewals == 0


def test_run_with_lease_heartbeat_renews_while_work_runs() -> None:
    renewals = 0
    started = Event()

    def renew() -> bool:
        nonlocal renewals
        renewals += 1
        return True

    def work() -> None:
        started.set()
        time.sleep(0.35)

    run_with_lease_heartbeat(work, renew, interval_seconds=0.1)

    assert started.is_set()
    assert renewals >= 2


def test_run_with_lease_heartbeat_raises_when_renewal_fails() -> None:
    def renew() -> bool:
        return False

    def work() -> None:
        time.sleep(0.25)

    with pytest.raises(LeaseLostError, match="Lost processing job lease"):
        run_with_lease_heartbeat(work, renew, interval_seconds=0.1)


def test_run_with_lease_heartbeat_rejects_non_positive_interval() -> None:
    with pytest.raises(ValueError, match="positive"):
        run_with_lease_heartbeat(lambda: None, lambda: True, interval_seconds=0)
