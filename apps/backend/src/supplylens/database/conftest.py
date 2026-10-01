# Pytest automatically loads files named conftest.py during test discovery.
# Fixtures defined here are available to tests in this directory and below,
# so test files do not need to import them directly.
# See pytest's fixture documentation:
# https://docs.pytest.org/en/stable/how-to/fixtures.html
from collections.abc import Iterator
from typing import Any

import pytest

from supplylens.database import database


def dispose_if_possible(engine: Any) -> None:
    dispose = getattr(engine, "dispose", None)
    if callable(dispose):
        dispose()


@pytest.fixture(autouse=True)
def reset_database_state() -> Iterator[None]:
    # Run this for every test in this directory tree, without requiring an import.
    # Dispose of any previous engine and clear cached objects before the test starts.
    dispose_if_possible(database.SessionEngine)
    database.SessionEngine = None
    database.SessionLocal = None

    try:
        # Pytest runs the test while this fixture is paused at yield.
        yield
    finally:
        # After the test, even if it fails, dispose of its engine and clear the
        # cached objects so its database state cannot affect the next test.
        dispose_if_possible(database.SessionEngine)
        database.SessionEngine = None
        database.SessionLocal = None
