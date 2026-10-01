from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import UUID

import pytest

from supplylens.controllers.documents.exceptions import (
    DocumentNotFoundError,
    DocumentNotUploadedError,
)
from supplylens.controllers.documents.get_document_url import get_document_url
from supplylens.domain.documents import DocumentProcessingStatus, DocumentUploadStatus
from supplylens.port.persistence.documents import Document, DocumentPersistence
from supplylens.port.storage.storage import ObjectStorage, PresignedURL

DOCUMENT_ID = UUID("12345678-1234-5678-1234-567812345678")


def _document(upload_status: DocumentUploadStatus) -> Document:
    return Document(
        id=DOCUMENT_ID,
        filename="invoice.pdf",
        size_bytes=512,
        document_type=None,
        page_count=None,
        upload_status=upload_status,
        processing_status=DocumentProcessingStatus.PENDING,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        uploaded_at=None,
        processed_at=None,
    )


def test_get_document_url_returns_signed_url_for_uploaded_document() -> None:
    storage = Mock(spec=ObjectStorage)
    persistence = Mock(spec=DocumentPersistence)
    persistence.get_document_data.return_value = _document(
        DocumentUploadStatus.UPLOADED
    )
    storage.create_download_url.return_value = PresignedURL(
        "https://storage.invalid/download", "GET", {}, 600
    )

    response = get_document_url(storage, persistence, DOCUMENT_ID)

    persistence.get_document_data.assert_called_once_with(DOCUMENT_ID)
    storage.create_download_url.assert_called_once_with(
        f"documents/{DOCUMENT_ID}/original.pdf"
    )
    assert response.id == DOCUMENT_ID
    assert response.url == "https://storage.invalid/download"
    assert response.expires_in_seconds == 600


def test_get_document_url_raises_when_document_does_not_exist() -> None:
    storage = Mock(spec=ObjectStorage)
    persistence = Mock(spec=DocumentPersistence)
    persistence.get_document_data.return_value = None

    with pytest.raises(DocumentNotFoundError, match=str(DOCUMENT_ID)):
        get_document_url(storage, persistence, DOCUMENT_ID)

    storage.create_download_url.assert_not_called()


@pytest.mark.parametrize(
    "status", [DocumentUploadStatus.PENDING, DocumentUploadStatus.FAILED]
)
def test_get_document_url_rejects_document_that_is_not_uploaded(
    status: DocumentUploadStatus,
) -> None:
    storage = Mock(spec=ObjectStorage)
    persistence = Mock(spec=DocumentPersistence)
    persistence.get_document_data.return_value = _document(status)

    with pytest.raises(DocumentNotUploadedError, match=str(DOCUMENT_ID)):
        get_document_url(storage, persistence, DOCUMENT_ID)

    storage.create_download_url.assert_not_called()
