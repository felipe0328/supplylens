from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import UUID

import pytest

from supplylens.controllers.documents.exceptions import DocumentNotFoundError
from supplylens.controllers.documents.get_document_data import get_document_data
from supplylens.domain.documents import DocumentProcessingStatus, DocumentUploadStatus
from supplylens.port.persistence.documents import Document as PersistedDocument
from supplylens.port.persistence.documents import DocumentPersistence

DOCUMENT_ID = UUID("12345678-1234-5678-1234-567812345678")
CREATED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)
UPLOADED_AT = datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc)


def test_get_document_data_returns_persistence_fields() -> None:
    persistence = Mock(spec=DocumentPersistence)
    persisted = PersistedDocument(
        id=DOCUMENT_ID,
        filename="invoice.pdf",
        size_bytes=512,
        document_type="invoice",
        page_count=2,
        upload_status=DocumentUploadStatus.UPLOADED,
        processing_status=DocumentProcessingStatus.PENDING,
        created_at=CREATED_AT,
        uploaded_at=UPLOADED_AT,
        processed_at=None,
    )
    persistence.get_document_data.return_value = persisted

    response = get_document_data(persistence, DOCUMENT_ID)

    persistence.get_document_data.assert_called_once_with(id=DOCUMENT_ID)
    assert response.document.id == persisted.id
    assert response.document.filename == persisted.filename
    assert response.document.size_bytes == persisted.size_bytes
    assert response.document.document_type == persisted.document_type
    assert response.document.page_count == persisted.page_count
    assert response.document.upload_status is persisted.upload_status
    assert response.document.processing_status is persisted.processing_status
    assert response.document.created_at == persisted.created_at
    assert response.document.uploaded_at == persisted.uploaded_at
    assert response.document.processed_at == persisted.processed_at


def test_get_document_data_raises_when_persistence_has_no_document() -> None:
    persistence = Mock(spec=DocumentPersistence)
    persistence.get_document_data.return_value = None

    with pytest.raises(DocumentNotFoundError, match=str(DOCUMENT_ID)):
        get_document_data(persistence, DOCUMENT_ID)
