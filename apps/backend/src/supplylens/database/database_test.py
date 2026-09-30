from unittest.mock import MagicMock, Mock

import pytest

from supplylens.database import database


def test_get_database_url_requires_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(
        ValueError,
        match="DATABASE_URL environment variable is not set",
    ):
        database.get_database_url()


def test_get_database_url_strips_whitespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "  postgresql://example  ")

    assert database.get_database_url() == "postgresql://example"


def test_create_session_builds_lazy_engine_and_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = object()
    factory = object()
    create_engine = Mock(return_value=engine)
    sessionmaker = Mock(return_value=factory)
    monkeypatch.setattr(database, "get_database_url", lambda: "postgresql://example")
    monkeypatch.setattr(database, "create_engine", create_engine)
    monkeypatch.setattr(database, "sessionmaker", sessionmaker)

    database.create_session()

    create_engine.assert_called_once_with("postgresql://example")
    sessionmaker.assert_called_once_with(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    assert database.SessionEngine is engine
    assert database.SessionLocal is factory


def test_create_session_wraps_configuration_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_to_get_url() -> str:
        raise ValueError("missing URL")

    monkeypatch.setattr(database, "get_database_url", fail_to_get_url)

    with pytest.raises(
        RuntimeError,
        match="Failed to create database session: missing URL",
    ):
        database.create_session()


def test_get_session_creates_factory_lazily(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = object()
    session_context = MagicMock()
    session_context.__enter__.return_value = session
    factory = Mock(return_value=session_context)

    def create_session() -> None:
        database.SessionLocal = factory

    monkeypatch.setattr(database, "SessionLocal", None)
    monkeypatch.setattr(database, "create_session", create_session)

    assert list(database.get_session()) == [session]
    factory.assert_called_once_with()
    session_context.__exit__.assert_called_once()


def test_health_check_executes_readiness_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = Mock()
    connection_context = MagicMock()
    connection_context.__enter__.return_value = connection
    engine = Mock()
    engine.connect.return_value = connection_context
    monkeypatch.setattr(database, "SessionLocal", object())
    monkeypatch.setattr(database, "SessionEngine", engine)

    assert database.health_check() is True

    statement = connection.execute.call_args.args[0]
    assert str(statement) == "SELECT 1"


def test_health_check_creates_session_lazily(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = Mock()
    connection_context = MagicMock()
    connection_context.__enter__.return_value = connection
    engine = Mock()
    engine.connect.return_value = connection_context

    def create_session() -> None:
        database.SessionLocal = object()
        database.SessionEngine = engine

    monkeypatch.setattr(database, "SessionLocal", None)
    monkeypatch.setattr(database, "SessionEngine", None)
    monkeypatch.setattr(database, "create_session", create_session)

    assert database.health_check() is True


def test_health_check_wraps_connection_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = Mock()
    engine.connect.side_effect = OSError("connection refused")
    monkeypatch.setattr(database, "SessionLocal", object())
    monkeypatch.setattr(database, "SessionEngine", engine)

    with pytest.raises(
        RuntimeError,
        match="Database health check failed: connection refused",
    ):
        database.health_check()
