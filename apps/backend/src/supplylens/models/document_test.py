import uuid
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from supplylens.database.database import Base
from supplylens.models.document import (
    Document,
    DocumentProcessingStatus,
    DocumentUploadStatus,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as database_session:
        yield database_session

    Base.metadata.drop_all(engine)
    engine.dispose()


def test_document_defaults_and_nullable_fields(session: Session) -> None:
    document = Document(
        filename="invoice.pdf",
        size_bytes=128,
        document_type="application/pdf",
    )
    session.add(document)
    session.flush()

    assert isinstance(document.id, uuid.UUID)
    assert document.upload_status is DocumentUploadStatus.PENDING
    assert document.processing_status is DocumentProcessingStatus.PENDING
    assert document.created_at is not None
    assert document.page_count is None
    assert document.uploaded_at is None
    assert document.processed_at is None


def test_document_defaults_apply_when_defaulted_fields_are_none(
    session: Session,
) -> None:
    document = Document(
        filename="invoice.pdf",
        size_bytes=128,
        document_type="application/pdf",
        upload_status=None,
        processing_status=None,
        created_at=None,
    )
    session.add(document)
    session.flush()

    assert document.upload_status is DocumentUploadStatus.PENDING
    assert document.processing_status is DocumentProcessingStatus.PENDING
    assert document.created_at is not None


@pytest.mark.parametrize("upload_status", list(DocumentUploadStatus))
@pytest.mark.parametrize("processing_status", list(DocumentProcessingStatus))
def test_document_persists_statuses_and_optional_values(
    session: Session,
    upload_status: DocumentUploadStatus,
    processing_status: DocumentProcessingStatus,
) -> None:
    uploaded_at = datetime(2026, 9, 30, 12, 0)
    processed_at = datetime(2026, 9, 30, 12, 5)
    document = Document(
        filename="invoice.pdf",
        size_bytes=128,
        document_type="application/pdf",
        page_count=2,
        upload_status=upload_status,
        processing_status=processing_status,
        uploaded_at=uploaded_at,
        processed_at=processed_at,
    )
    session.add(document)
    session.commit()

    persisted_document = session.get(Document, document.id)

    assert persisted_document is not None
    assert persisted_document.page_count == 2
    assert persisted_document.upload_status is upload_status
    assert persisted_document.processing_status is processing_status
    assert persisted_document.uploaded_at == uploaded_at
    assert persisted_document.processed_at == processed_at


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("filename", ""),
        ("size_bytes", -1),
        ("document_type", ""),
        ("page_count", -1),
    ],
)
def test_document_rejects_invalid_constraint_values(
    session: Session,
    field_name: str,
    invalid_value: str | int,
) -> None:
    document_values: dict[str, object] = {
        "filename": "invoice.pdf",
        "size_bytes": 128,
        "document_type": "application/pdf",
        "page_count": 1,
    }
    document_values[field_name] = invalid_value
    session.add(Document(**document_values))

    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("filename", None),
        ("size_bytes", None),
        ("document_type", None),
    ],
)
def test_document_rejects_null_required_values(
    session: Session,
    field_name: str,
    invalid_value: None,
) -> None:
    document_values: dict[str, object] = {
        "filename": "invoice.pdf",
        "size_bytes": 128,
        "document_type": "application/pdf",
    }
    document_values[field_name] = invalid_value
    session.add(Document(**document_values))

    with pytest.raises(IntegrityError):
        session.flush()
