from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import UUID

import pytest

from supplylens.controllers.documents.exceptions import (
    DocumentInvalidContentTypeError,
    DocumentNotFoundError,
    StoreDocumentInvalidSizeError,
)
from supplylens.controllers.documents.report_upload_completed import (
    report_upload_completed,
)
from supplylens.domain.documents import DocumentProcessingStatus, DocumentUploadStatus
from supplylens.port.persistence.documents import Document, DocumentPersistence
from supplylens.port.storage.storage import (
    ObjectInfo,
    ObjectNotFoundError,
    ObjectStorage,
)

DOCUMENT_ID = UUID("12345678-1234-5678-1234-567812345678")
OBJECT_KEY = f"documents/{DOCUMENT_ID}/original.pdf"
CREATED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _document() -> Document:
    return Document(
        id=DOCUMENT_ID,
        filename="invoice.pdf",
        size_bytes=512,
        document_type=None,
        page_count=None,
        upload_status=DocumentUploadStatus.PENDING,
        processing_status=DocumentProcessingStatus.PENDING,
        created_at=CREATED_AT,
        uploaded_at=None,
        processed_at=None,
    )


def test_report_upload_completed_validates_object_and_updates_status() -> None:
    storage = Mock(spec=ObjectStorage)
    persistence = Mock(spec=DocumentPersistence)
    storage.head_object.return_value = ObjectInfo(
        key=OBJECT_KEY,
        size_bytes=512,
        content_type="application/pdf",
        etag='"synthetic-etag"',
    )
    persistence.get_document_data.return_value = _document()
    updated = replace(_document(), upload_status=DocumentUploadStatus.UPLOADED)
    persistence.update_document_upload_status.return_value = updated

    response = report_upload_completed(storage, persistence, DOCUMENT_ID)

    storage.head_object.assert_called_once_with(OBJECT_KEY)
    persistence.get_document_data.assert_called_once_with(DOCUMENT_ID)
    persistence.update_document_upload_status.assert_called_once_with(
        id=DOCUMENT_ID, new_status=DocumentUploadStatus.UPLOADED
    )
    assert response.document.id == updated.id
    assert response.document.filename == updated.filename
    assert response.document.size_bytes == updated.size_bytes
    assert response.document.upload_status is DocumentUploadStatus.UPLOADED


def test_report_upload_completed_raises_when_object_is_missing() -> None:
    storage = Mock(spec=ObjectStorage)
    persistence = Mock(spec=DocumentPersistence)
    persistence.get_document_data.return_value = _document()
    storage.head_object.side_effect = ObjectNotFoundError("not uploaded")

    with pytest.raises(DocumentNotFoundError, match="object storage"):
        report_upload_completed(storage, persistence, DOCUMENT_ID)

    persistence.get_document_data.assert_called_once_with(DOCUMENT_ID)
    persistence.update_document_upload_status.assert_not_called()


def test_report_upload_completed_raises_when_persistence_record_is_missing() -> None:
    storage = Mock(spec=ObjectStorage)
    persistence = Mock(spec=DocumentPersistence)
    persistence.get_document_data.return_value = None

    with pytest.raises(DocumentNotFoundError, match=str(DOCUMENT_ID)):
        report_upload_completed(storage, persistence, DOCUMENT_ID)

    storage.head_object.assert_not_called()
    persistence.update_document_upload_status.assert_not_called()


@pytest.mark.parametrize(
    ("size_bytes", "content_type", "expected_error"),
    [
        (511, "application/pdf", StoreDocumentInvalidSizeError),
        (512, "application/octet-stream", DocumentInvalidContentTypeError),
    ],
)
def test_report_upload_completed_rejects_invalid_storage_metadata(
    size_bytes: int,
    content_type: str,
    expected_error: type[Exception],
) -> None:
    storage = Mock(spec=ObjectStorage)
    persistence = Mock(spec=DocumentPersistence)
    storage.head_object.return_value = ObjectInfo(
        key=OBJECT_KEY,
        size_bytes=size_bytes,
        content_type=content_type,
        etag=None,
    )
    persistence.get_document_data.return_value = _document()

    with pytest.raises(expected_error):
        report_upload_completed(storage, persistence, DOCUMENT_ID)

    persistence.update_document_upload_status.assert_not_called()
