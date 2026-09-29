import os
from typing import Generator
from sqlalchemy import create_engine, Engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from dotenv import load_dotenv


class Base(DeclarativeBase):
    pass


load_dotenv()  # Load environment variables from .env file

SessionEngine: Engine = None
SessionLocal: sessionmaker[Session] = None


def get_database_url() -> str:
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable is not set.")
    DATABASE_URL = DATABASE_URL.strip()  # Remove any leading/trailing whitespace
    return DATABASE_URL


def create_session() -> None:
    try:
        DATABASE_URL: str = get_database_url()
        global SessionLocal, SessionEngine

        SessionEngine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=SessionEngine)
    except Exception as e:
        raise RuntimeError(f"Failed to create database session: {e}")


def get_session() -> Generator[Session, None, None]:
    if SessionLocal is None:
        create_session()

    with SessionLocal() as session:
        yield session


def health_check() -> bool:
    try:
        if SessionLocal is None:
            create_session()

        with SessionEngine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as e:
        raise RuntimeError(f"Database health check failed: {e}")
