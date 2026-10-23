from collections.abc import Callable
from threading import Event, Thread


class LeaseLostError(Exception):
    """Raised when lease renewal fails while work is in progress."""


def run_with_lease_heartbeat(
    work: Callable[[], None],
    renew_lease: Callable[[], bool],
    *,
    interval_seconds: float,
) -> None:
    """Run work while renewing the lease on a background thread.

    ``renew_lease`` must open and commit its own short DB transaction. When it
    returns False, work is allowed to finish, then ``LeaseLostError`` is raised
    so the caller skips complete/fail ownership writes.
    """
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be a positive integer")

    stop = Event()
    lost = Event()

    def _heartbeat() -> None:
        while not stop.wait(interval_seconds):
            if not renew_lease():
                lost.set()
                return

    thread = Thread(
        target=_heartbeat,
        name="processing-job-lease-heartbeat",
        daemon=True,
    )
    thread.start()
    try:
        work()
    finally:
        stop.set()
        thread.join(timeout=max(1.0, float(interval_seconds)))

    if lost.is_set():
        raise LeaseLostError("Lost processing job lease during work")
