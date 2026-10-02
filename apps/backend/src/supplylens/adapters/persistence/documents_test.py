from datetime import datetime
from typing import Generator
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from supplylens.adapters.persistence.documents import DocumentPersistenceAdapter
from supplylens.database.database import Base
from supplylens.domain.documents import DocumentProcessingStatus, DocumentUploadStatus
from supplylens.models.document import Document
from supplylens.port.persistence.documents import Document as AbstractDocument


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


def test_first_uploaded_transition_sets_uploaded_at(session: Session) -> None:
    document_id = uuid4()
    adapter = DocumentPersistenceAdapter(session)
    adapter.create_new_document(document_id, "invoice.pdf", 128)
    adapter.commit()

    updated_document = adapter.update_document_upload_status(
        document_id, DocumentUploadStatus.UPLOADED
    )

    assert updated_document.uploaded_at is not None


def test_repeated_uploaded_transition_preserves_uploaded_at(session: Session) -> None:
    document_id = uuid4()
    adapter = DocumentPersistenceAdapter(session)
    adapter.create_new_document(document_id, "invoice.pdf", 128)
    first_update = adapter.update_document_upload_status(
        document_id, DocumentUploadStatus.UPLOADED
    )
    original_uploaded_at = first_update.uploaded_at

    second_update = adapter.update_document_upload_status(
        document_id, DocumentUploadStatus.UPLOADED
    )

    assert second_update.uploaded_at == original_uploaded_at


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


@pytest.mark.parametrize(
    ("filename", "size_bytes"),
    [("", 128), ("invoice.pdf", -1)],
)
def test_create_rejects_invalid_values_and_allows_rollback(
    session: Session, filename: str, size_bytes: int
) -> None:
    document_id = UUID("00000000-0000-0000-0000-000000000001")
    adapter = DocumentPersistenceAdapter(session)

    with pytest.raises(IntegrityError):
        adapter.create_new_document(document_id, filename, size_bytes)

    adapter.rollback()

    assert adapter.get_document_data(document_id) is None
    document = adapter.create_new_document(document_id, "valid-invoice.pdf", 128)
    assert document.filename == "valid-invoice.pdf"


def test_duplicate_id_failure_rolls_back_all_pending_documents(
    session: Session,
) -> None:
    existing_id = UUID("00000000-0000-0000-0000-000000000001")
    pending_id = UUID("00000000-0000-0000-0000-000000000002")
    adapter = DocumentPersistenceAdapter(session)
    adapter.create_new_document(existing_id, "existing.pdf", 128)
    adapter.commit()
    adapter.create_new_document(pending_id, "pending.pdf", 256)

    with pytest.raises(IntegrityError):
        adapter.create_new_document(existing_id, "duplicate.pdf", 512)

    adapter.rollback()

    assert adapter.get_document_data(pending_id) is None
    existing_document = adapter.get_document_data(existing_id)
    assert existing_document is not None
    assert existing_document.filename == "existing.pdf"
    assert existing_document.size_bytes == 128


def test_get_maps_complete_document_metadata(session: Session) -> None:
    document_id = UUID("00000000-0000-0000-0000-000000000001")
    created_at = datetime(2026, 9, 30, 12, 0)
    uploaded_at = datetime(2026, 9, 30, 12, 5)
    processed_at = datetime(2026, 9, 30, 12, 10)
    session.add(
        Document(
            id=document_id,
            filename="invoice.pdf",
            size_bytes=512,
            document_type="application/pdf",
            page_count=2,
            upload_status=DocumentUploadStatus.UPLOADED,
            processing_status=DocumentProcessingStatus.PROCESSED,
            created_at=created_at,
            uploaded_at=uploaded_at,
            processed_at=processed_at,
        )
    )
    session.commit()
    adapter = DocumentPersistenceAdapter(session)

    document = adapter.get_document_data(document_id)

    assert document == AbstractDocument(
        id=document_id,
        filename="invoice.pdf",
        size_bytes=512,
        document_type="application/pdf",
        page_count=2,
        upload_status=DocumentUploadStatus.UPLOADED,
        processing_status=DocumentProcessingStatus.PROCESSED,
        created_at=created_at,
        uploaded_at=uploaded_at,
        processed_at=processed_at,
    )


def test_committed_update_persists_status_and_preserves_document_data(
    session: Session,
) -> None:
    document_id = UUID("00000000-0000-0000-0000-000000000001")
    adapter = DocumentPersistenceAdapter(session)
    created_document = adapter.create_new_document(document_id, "invoice.pdf", 128)
    adapter.commit()

    updated_document = adapter.update_document_upload_status(
        document_id, DocumentUploadStatus.FAILED
    )
    adapter.commit()

    assert updated_document.filename == created_document.filename
    assert updated_document.size_bytes == created_document.size_bytes
    assert updated_document.created_at == created_document.created_at
    assert updated_document.uploaded_at is None
    assert updated_document.processing_status is DocumentProcessingStatus.PENDING
    with Session(session.get_bind()) as verification_session:
        persisted_document = DocumentPersistenceAdapter(
            verification_session
        ).get_document_data(document_id)
        assert persisted_document == updated_document


def test_committed_delete_removes_only_requested_document(session: Session) -> None:
    deleted_id = UUID("00000000-0000-0000-0000-000000000001")
    retained_id = UUID("00000000-0000-0000-0000-000000000002")
    adapter = DocumentPersistenceAdapter(session)
    adapter.create_new_document(deleted_id, "deleted.pdf", 128)
    adapter.create_new_document(retained_id, "retained.pdf", 256)
    adapter.commit()

    adapter.delete_document(deleted_id)
    adapter.commit()

    with Session(session.get_bind()) as verification_session:
        verification_adapter = DocumentPersistenceAdapter(verification_session)
        assert verification_adapter.get_document_data(deleted_id) is None
        retained_document = verification_adapter.get_document_data(retained_id)
        assert retained_document is not None
        assert retained_document.filename == "retained.pdf"
