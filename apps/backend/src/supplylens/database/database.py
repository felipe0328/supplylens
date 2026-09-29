import os
from typing import Generator
from sqlalchemy import create_engine, Engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from dotenv import load_dotenv


class Base(DeclarativeBase):
    pass


load_dotenv()  # Load environment variables from .env file
DATABASE_URL: str = os.getenv("DATABASE_URL").strip()
engine: Engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def health_check() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
