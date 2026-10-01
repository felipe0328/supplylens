from datetime import datetime
from typing import Generator
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from supplylens.adapters.persistence.documents import DocumentPersistenceAdapter
from supplylens.database.database import Base
from supplylens.domain.documents import DocumentProcessingStatus, DocumentUploadStatus
from supplylens.models.document import Document


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine, autoflush=False) as database_session:
            yield database_session
    finally:
        engine.dispose()


def test_create_returns_defaults_and_can_be_rolled_back(session: Session) -> None:
    document_id = uuid4()
    adapter = DocumentPersistenceAdapter(session)

    document = adapter.create_new_document(document_id, "invoice.pdf", 128)

    assert document.id == document_id
    assert document.filename == "invoice.pdf"
    assert document.size_bytes == 128
    assert document.upload_status is DocumentUploadStatus.PENDING
    assert document.processing_status is DocumentProcessingStatus.PENDING
    assert isinstance(document.created_at, datetime)
    assert document.document_type is None
    assert document.page_count is None
    assert document.uploaded_at is None
    assert document.processed_at is None
    assert session.get(Document, document_id) is not None

    session.rollback()

    assert session.get(Document, document_id) is None


def test_get_returns_document_data(session: Session) -> None:
    document_id = uuid4()
    adapter = DocumentPersistenceAdapter(session)
    created_document = adapter.create_new_document(document_id, "invoice.pdf", 128)

    assert adapter.get_document_data(document_id) == created_document


def test_update_returns_new_status_and_can_be_rolled_back(session: Session) -> None:
    document_id = uuid4()
    adapter = DocumentPersistenceAdapter(session)
    adapter.create_new_document(document_id, "invoice.pdf", 128)
    session.commit()

    updated_document = adapter.update_document_upload_status(
        document_id, DocumentUploadStatus.UPLOADED
    )

    assert updated_document.upload_status is DocumentUploadStatus.UPLOADED
    session.expire_all()
    assert (
        adapter.get_document_data(document_id).upload_status
        is DocumentUploadStatus.UPLOADED
    )

    session.rollback()

    assert (
        adapter.get_document_data(document_id).upload_status
        is DocumentUploadStatus.PENDING
    )


def test_delete_flushes_and_can_be_rolled_back(session: Session) -> None:
    document_id = uuid4()
    adapter = DocumentPersistenceAdapter(session)
    adapter.create_new_document(document_id, "invoice.pdf", 128)
    session.commit()

    adapter.delete_document(document_id)

    assert adapter.get_document_data(document_id) is None

    session.rollback()

    assert adapter.get_document_data(document_id) is not None


def test_get_and_delete_missing_document(session: Session) -> None:
    document_id = uuid4()
    adapter = DocumentPersistenceAdapter(session)

    assert adapter.get_document_data(document_id) is None
    adapter.delete_document(document_id)
    assert adapter.get_document_data(document_id) is None


def test_update_missing_document_raises(session: Session) -> None:
    document_id = uuid4()
    adapter = DocumentPersistenceAdapter(session)

    with pytest.raises(ValueError, match=f"Document with ID {document_id} not found"):
        adapter.update_document_upload_status(
            document_id, DocumentUploadStatus.UPLOADED
        )


def test_explicit_commit_persists_document(session: Session) -> None:
    document_id = uuid4()
    adapter = DocumentPersistenceAdapter(session)
    adapter.create_new_document(document_id, "invoice.pdf", 128)

    adapter.commit()

    with Session(session.get_bind()) as verification_session:
        document = verification_session.get(Document, document_id)
        assert document is not None
        assert document.filename == "invoice.pdf"


def test_explicit_rollback_discards_document(session: Session) -> None:
    document_id = uuid4()
    adapter = DocumentPersistenceAdapter(session)
    adapter.create_new_document(document_id, "invoice.pdf", 128)

    adapter.rollback()

    assert adapter.get_document_data(document_id) is None
