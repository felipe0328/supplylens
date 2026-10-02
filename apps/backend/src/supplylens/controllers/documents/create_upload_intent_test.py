from datetime import datetime
from unittest.mock import Mock, patch
from uuid import UUID

import pytest

from supplylens.controllers.documents.create_upload_intent import (
    CreateUploadIntentCommand,
    create_upload_intent,
)
from supplylens.controllers.documents.exceptions import (
    MismatchBetweenPersistenceAndStorageError,
)
from supplylens.domain.documents import DocumentProcessingStatus, DocumentUploadStatus
from supplylens.port.persistence.documents import Document, DocumentPersistence
from supplylens.port.storage.storage import ObjectStorage, PresignedURL

DOCUMENT_ID = UUID("12345678-1234-5678-1234-567812345678")


def test_create_upload_intent_requests_upload_and_persists_document() -> None:
    storage = Mock(spec=ObjectStorage)
    persistence = Mock(spec=DocumentPersistence)
    storage.create_upload_url.return_value = PresignedURL(
        url="https://storage.invalid/upload",
        method="PUT",
        headers={"Content-Type": "application/pdf"},
        expires_in_seconds=900,
    )
    persistence.create_new_document.return_value = Document(
        id=DOCUMENT_ID,
        filename="invoice.pdf",
        size_bytes=512,
        document_type=None,
        page_count=None,
        upload_status=DocumentUploadStatus.PENDING,
        processing_status=DocumentProcessingStatus.PENDING,
        created_at=datetime(2026, 1, 1),
        uploaded_at=None,
        processed_at=None,
    )
    command = CreateUploadIntentCommand(
        filename="invoice.pdf", content_type="application/pdf", size_bytes=512
    )

    with patch(
        "supplylens.controllers.documents.create_upload_intent.uuid7",
        return_value=DOCUMENT_ID,
    ):
        result = create_upload_intent(storage, persistence, command)

    object_key = f"documents/{DOCUMENT_ID}/original.pdf"
    storage.create_upload_url.assert_called_once_with(
        object_key=object_key,
        content_type="application/pdf",
        size_bytes=512,
    )
    persistence.create_new_document.assert_called_once_with(
        id=DOCUMENT_ID, filename="invoice.pdf", size_bytes=512
    )
    assert result.id == DOCUMENT_ID
    assert result.upload.url == "https://storage.invalid/upload"
    assert result.upload.method == "PUT"
    assert result.upload.headers == {"Content-Type": "application/pdf"}
    assert result.upload.expires_in_seconds == 900


def test_create_upload_intent_rejects_persistence_id_mismatch() -> None:
    storage = Mock(spec=ObjectStorage)
    persistence = Mock(spec=DocumentPersistence)
    storage.create_upload_url.return_value = PresignedURL(
        "https://storage.invalid/upload", "PUT", {}, 900
    )
    persistence.create_new_document.return_value = Mock(id=UUID(int=2))
    command = CreateUploadIntentCommand("invoice.pdf", "application/pdf", 512)

    with (
        patch(
            "supplylens.controllers.documents.create_upload_intent.uuid7",
            return_value=DOCUMENT_ID,
        ),
        pytest.raises(MismatchBetweenPersistenceAndStorageError),
    ):
        create_upload_intent(storage, persistence, command)


def test_create_upload_intent_persists_before_storage_signing() -> None:
    storage = Mock(spec=ObjectStorage)
    persistence = Mock(spec=DocumentPersistence)
    storage.create_upload_url.side_effect = RuntimeError("synthetic storage failure")
    persistence.create_new_document.return_value = Document(
        id=DOCUMENT_ID,
        filename="invoice.pdf",
        size_bytes=512,
        document_type=None,
        page_count=None,
        upload_status=DocumentUploadStatus.PENDING,
        processing_status=DocumentProcessingStatus.PENDING,
        created_at=datetime(2026, 1, 1),
        uploaded_at=None,
        processed_at=None,
    )
    command = CreateUploadIntentCommand("invoice.pdf", "application/pdf", 512)

    with (
        patch(
            "supplylens.controllers.documents.create_upload_intent.uuid7",
            return_value=DOCUMENT_ID,
        ),
        pytest.raises(RuntimeError, match="synthetic storage failure"),
    ):
        create_upload_intent(storage, persistence, command)

    persistence.create_new_document.assert_called_once_with(
        id=DOCUMENT_ID, filename="invoice.pdf", size_bytes=512
    )
