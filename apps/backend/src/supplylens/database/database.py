import os
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


load_dotenv()  # Load environment variables from .env file

SessionEngine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if database_url is None or not database_url.strip():
        raise ValueError("DATABASE_URL environment variable is not set.")
    return database_url.strip()


def create_session() -> None:
    database_url = get_database_url()
    engine = create_engine(database_url)
    session_factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    global SessionEngine, SessionLocal
    SessionEngine = engine
    SessionLocal = session_factory


def get_session() -> Generator[Session, None, None]:
    """Commit on successful completion, roll back on failure, and close the session."""
    if SessionLocal is None:
        create_session()

    session_factory = SessionLocal
    if session_factory is None:
        raise RuntimeError("Database session factory was not initialized.")

    with session_factory() as session, session.begin():
        yield session


def health_check() -> bool:
    try:
        if SessionEngine is None:
            create_session()

        engine = SessionEngine
        if engine is None:
            raise RuntimeError("Database engine was not initialized.")

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError("Database health check failed.") from exc
