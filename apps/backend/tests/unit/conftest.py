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
    dispose_if_possible(database.SessionEngine)
    database.SessionEngine = None
    database.SessionLocal = None

    try:
        yield
    finally:
        dispose_if_possible(database.SessionEngine)
        database.SessionEngine = None
        database.SessionLocal = None
