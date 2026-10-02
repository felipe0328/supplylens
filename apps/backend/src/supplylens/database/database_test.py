from contextlib import contextmanager
from typing import Generator
from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from supplylens.adapters.persistence.documents import DocumentPersistenceAdapter
from supplylens.database import database
from supplylens.domain.documents import DocumentUploadStatus
from supplylens.models.document import Document


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


def test_get_database_url_rejects_whitespace_only_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "   ")

    with pytest.raises(
        ValueError,
        match="DATABASE_URL environment variable is not set",
    ):
        database.get_database_url()


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

    database.__create_session()

    create_engine.assert_called_once_with("postgresql://example")
    sessionmaker.assert_called_once_with(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    assert database.SessionEngine is engine
    assert database.SessionLocal is factory


def test_create_session_preserves_configuration_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_to_get_url() -> str:
        raise ValueError("missing URL")

    monkeypatch.setattr(database, "get_database_url", fail_to_get_url)

    with pytest.raises(ValueError, match="missing URL"):
        database.__create_session()


def test_get_session_creates_factory_lazily(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = MagicMock(spec=Session)
    session_context = MagicMock()
    session_context.__enter__.return_value = session
    factory = Mock(return_value=session_context)

    def create_session() -> None:
        database.SessionLocal = factory

    monkeypatch.setattr(database, "SessionLocal", None)
    monkeypatch.setattr(database, "__create_session", create_session)

    assert list(database.get_session()) == [session]
    factory.assert_called_once_with()
    session_context.__exit__.assert_called_once()
    session.begin.assert_called_once_with()
    session.begin.return_value.__exit__.assert_called_once_with(None, None, None)


def test_get_session_rejects_uninitialized_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(database, "SessionLocal", None)
    monkeypatch.setattr(database, "__create_session", lambda: None)

    with pytest.raises(RuntimeError, match="factory was not initialized"):
        next(database.get_session())


def test_health_check_executes_readiness_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = Mock()
    connection_context = MagicMock()
    connection_context.__enter__.return_value = connection
    engine = Mock()
    engine.connect.return_value = connection_context
    monkeypatch.setattr(database, "SessionEngine", engine)

    assert database.health_check() is True

    statement = connection.execute.call_args.args[0]
    assert str(statement) == "SELECT 1"


def test_health_check_creates_engine_lazily(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = Mock()
    connection_context = MagicMock()
    connection_context.__enter__.return_value = connection
    engine = Mock()
    engine.connect.return_value = connection_context

    def create_session() -> None:
        database.SessionEngine = engine

    monkeypatch.setattr(database, "SessionEngine", None)
    monkeypatch.setattr(database, "__create_session", create_session)

    assert database.health_check() is True


def test_health_check_preserves_configuration_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def create_session() -> None:
        raise ValueError("missing URL")

    monkeypatch.setattr(database, "SessionEngine", None)
    monkeypatch.setattr(database, "__create_session", create_session)

    with pytest.raises(ValueError, match="missing URL"):
        database.health_check()


def test_health_check_wraps_connection_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = Mock()
    engine.connect.side_effect = OSError("connection refused")
    monkeypatch.setattr(database, "SessionEngine", engine)

    with pytest.raises(RuntimeError, match="Database health check failed"):
        database.health_check()


def test_health_check_rejects_uninitialized_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(database, "SessionEngine", None)
    monkeypatch.setattr(database, "__create_session", lambda: None)

    with pytest.raises(RuntimeError, match="Database health check failed"):
        database.health_check()


@pytest.fixture
def transaction_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[Engine, None, None]:
    engine = create_engine("sqlite://")
    database.Base.metadata.create_all(engine)
    monkeypatch.setattr(
        database, "SessionLocal", sessionmaker(bind=engine, autoflush=False)
    )
    try:
        yield engine
    finally:
        engine.dispose()


def test_get_session_commits_document_operations_on_success(
    transaction_engine: Engine,
) -> None:
    document_id = uuid4()

    with contextmanager(database.get_session)() as session:
        adapter = DocumentPersistenceAdapter(session)
        adapter.create_new_document(document_id, "invoice.pdf", 128)
        adapter.update_document_upload_status(
            document_id, DocumentUploadStatus.UPLOADED
        )

    with Session(transaction_engine) as verification_session:
        document = verification_session.get(Document, document_id)
        assert document is not None
        assert document.upload_status is DocumentUploadStatus.UPLOADED


def test_get_session_rolls_back_document_operations_on_failure(
    transaction_engine: Engine,
) -> None:
    document_id = uuid4()

    with pytest.raises(RuntimeError, match="operation failed"):
        with contextmanager(database.get_session)() as session:
            DocumentPersistenceAdapter(session).create_new_document(
                document_id, "invoice.pdf", 128
            )
            raise RuntimeError("operation failed")

    with Session(transaction_engine) as verification_session:
        assert verification_session.get(Document, document_id) is None


def test_get_session_rolls_back_when_commit_fails(
    transaction_engine: Engine,
) -> None:
    document_id = uuid4()
    invalid_document_id = uuid4()

    with pytest.raises(IntegrityError):
        with contextmanager(database.get_session)() as session:
            DocumentPersistenceAdapter(session).create_new_document(
                document_id, "invoice.pdf", 128
            )
            session.add(Document(id=invalid_document_id, filename="", size_bytes=128))

    with Session(transaction_engine) as verification_session:
        assert verification_session.get(Document, document_id) is None
        assert verification_session.get(Document, invalid_document_id) is None


def test_get_session_rolls_back_when_generator_is_closed(
    transaction_engine: Engine,
) -> None:
    document_id = uuid4()
    dependency = database.get_session()
    session = next(dependency)
    DocumentPersistenceAdapter(session).create_new_document(
        document_id, "invoice.pdf", 128
    )

    dependency.close()

    with Session(transaction_engine) as verification_session:
        assert verification_session.get(Document, document_id) is None
