import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, make_url

from alembic import command

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEST_DATABASE_URL = (
    "postgresql+psycopg://supplylens:localdev@127.0.0.1:5434/supplylens_test"
)


def require_test_database_url() -> URL:
    database_url = make_url(os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL))
    if not database_url.database or not database_url.database.endswith("_test"):
        pytest.fail("TEST_DATABASE_URL must name a database ending in '_test'.")
    return database_url


def reset_public_schema(database_url: URL) -> None:
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
    finally:
        engine.dispose()


@pytest.fixture
def clean_test_database(monkeypatch: pytest.MonkeyPatch) -> Iterator[URL]:
    database_url = require_test_database_url()
    reset_public_schema(database_url)
    monkeypatch.setenv(
        "DATABASE_URL", database_url.render_as_string(hide_password=False)
    )

    try:
        yield database_url
    finally:
        reset_public_schema(database_url)


@pytest.mark.integration
def test_migrations_upgrade_and_downgrade_clean_postgres(
    clean_test_database: URL,
) -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    expected_head = ScriptDirectory.from_config(config).get_current_head()
    assert expected_head is not None

    command.upgrade(config, "head")

    engine = create_engine(clean_test_database)
    try:
        with engine.connect() as connection:
            revision = MigrationContext.configure(connection).get_current_revision()
        assert revision == expected_head
        assert set(inspect(engine).get_table_names()) == {
            "alembic_version",
            "documents",
        }

        command.downgrade(config, "base")

        with engine.connect() as connection:
            revision = MigrationContext.configure(connection).get_current_revision()
        assert revision is None
    finally:
        engine.dispose()


@pytest.mark.integration
def test_filename_constraint_migration_repairs_existing_blank_filenames(
    clean_test_database: URL,
) -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.upgrade(config, "178db1cb8a7c")

    document_id = "00000000-0000-0000-0000-000000000001"
    engine = create_engine(clean_test_database)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO documents (
                        id,
                        filename,
                        size_bytes,
                        upload_status,
                        processing_status
                    ) VALUES (
                        CAST(:document_id AS UUID),
                        '   ',
                        128,
                        'PENDING',
                        'PENDING'
                    )
                    """
                ),
                {"document_id": document_id},
            )

        command.upgrade(config, "head")

        with engine.connect() as connection:
            filename = connection.execute(
                text(
                    "SELECT filename FROM documents "
                    "WHERE id = CAST(:document_id AS UUID)"
                ),
                {"document_id": document_id},
            ).scalar_one()
        assert filename == f"document-{document_id}.pdf"
    finally:
        engine.dispose()
