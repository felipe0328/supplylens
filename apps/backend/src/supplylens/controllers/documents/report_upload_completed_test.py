from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import Mock, call
from uuid import UUID

import pytest

from supplylens.controllers.documents.exceptions import (
    DocumentInvalidContentTypeError,
    DocumentNotFoundError,
    InvalidJobProcessingID,
    StoreDocumentInvalidSizeError,
)
from supplylens.controllers.documents.report_upload_completed import (
    report_upload_completed,
)
from supplylens.domain.documents import DocumentProcessingStatus, DocumentUploadStatus
from supplylens.port.persistence.documents import Document, DocumentPersistence
from supplylens.port.persistence.processing_job import ProcessingJobPersistence
from supplylens.port.storage.storage import (
    ObjectInfo,
    ObjectNotFoundError,
    ObjectStorage,
    StorageUnavailableError,
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


@pytest.fixture
def job_persistence() -> Mock:
    persistence = Mock(spec=ProcessingJobPersistence)
    persistence.enqueue_new_job.return_value = 42
    return persistence


def test_report_upload_completed_validates_object_and_updates_status(
    job_persistence: Mock,
) -> None:
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
    operations = Mock()
    operations.attach_mock(storage, "storage")
    operations.attach_mock(persistence, "documents")
    operations.attach_mock(job_persistence, "jobs")

    response = report_upload_completed(
        storage, persistence, job_persistence, DOCUMENT_ID
    )

    storage.head_object.assert_called_once_with(OBJECT_KEY)
    persistence.get_document_data.assert_called_once_with(DOCUMENT_ID)
    persistence.update_document_upload_status.assert_called_once_with(
        id=DOCUMENT_ID, new_status=DocumentUploadStatus.UPLOADED
    )
    assert response.document.id == updated.id
    assert response.document.filename == updated.filename
    assert response.document.size_bytes == updated.size_bytes
    assert response.document.upload_status is DocumentUploadStatus.UPLOADED
    job_persistence.enqueue_new_job.assert_called_once_with(DOCUMENT_ID)
    assert operations.mock_calls == [
        call.storage.head_object(OBJECT_KEY),
        call.documents.get_document_data(DOCUMENT_ID),
        call.documents.update_document_upload_status(
            id=DOCUMENT_ID, new_status=DocumentUploadStatus.UPLOADED
        ),
        call.jobs.enqueue_new_job(DOCUMENT_ID),
    ]


def test_report_upload_completed_raises_when_object_is_missing(
    job_persistence: Mock,
) -> None:
    storage = Mock(spec=ObjectStorage)
    persistence = Mock(spec=DocumentPersistence)
    storage.head_object.side_effect = ObjectNotFoundError("not uploaded")

    with pytest.raises(DocumentNotFoundError, match="object storage"):
        report_upload_completed(storage, persistence, job_persistence, DOCUMENT_ID)

    persistence.get_document_data.assert_not_called()
    persistence.update_document_upload_status.assert_not_called()
    job_persistence.enqueue_new_job.assert_not_called()


def test_report_upload_completed_raises_when_persistence_record_is_missing(
    job_persistence: Mock,
) -> None:
    storage = Mock(spec=ObjectStorage)
    persistence = Mock(spec=DocumentPersistence)
    storage.head_object.return_value = ObjectInfo(
        OBJECT_KEY, 512, "application/pdf", None
    )
    persistence.get_document_data.return_value = None

    with pytest.raises(DocumentNotFoundError, match="object storage"):
        report_upload_completed(storage, persistence, job_persistence, DOCUMENT_ID)

    persistence.update_document_upload_status.assert_not_called()
    job_persistence.enqueue_new_job.assert_not_called()


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
    job_persistence: Mock,
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
        report_upload_completed(storage, persistence, job_persistence, DOCUMENT_ID)

    persistence.update_document_upload_status.assert_called_once_with(
        id=DOCUMENT_ID, new_status=DocumentUploadStatus.FAILED
    )
    persistence.commit.assert_not_called()
    storage.delete_object.assert_called_once_with(OBJECT_KEY)
    job_persistence.enqueue_new_job.assert_not_called()


@pytest.fixture
def completion_dependencies(job_persistence: Mock) -> tuple[Mock, Mock, Mock]:
    storage = Mock(spec=ObjectStorage)
    storage.head_object.return_value = ObjectInfo(
        OBJECT_KEY, 512, "application/pdf", None
    )
    persistence = Mock(spec=DocumentPersistence)
    persistence.get_document_data.return_value = _document()
    persistence.update_document_upload_status.return_value = replace(
        _document(), upload_status=DocumentUploadStatus.UPLOADED
    )
    return storage, persistence, job_persistence


@pytest.mark.parametrize("job_id", [0, -1])
def test_report_upload_completed_rejects_invalid_job_id(
    completion_dependencies: tuple[Mock, Mock, Mock], job_id: int
) -> None:
    storage, persistence, jobs = completion_dependencies
    jobs.enqueue_new_job.return_value = job_id

    with pytest.raises(InvalidJobProcessingID, match=f"wrong job id: {job_id}"):
        report_upload_completed(storage, persistence, jobs, DOCUMENT_ID)

    jobs.enqueue_new_job.assert_called_once_with(DOCUMENT_ID)
    persistence.commit.assert_not_called()
    storage.delete_object.assert_not_called()


def test_report_upload_completed_propagates_enqueue_failure(
    completion_dependencies: tuple[Mock, Mock, Mock],
) -> None:
    storage, persistence, jobs = completion_dependencies
    error = RuntimeError("job insert failed")
    jobs.enqueue_new_job.side_effect = error

    with pytest.raises(RuntimeError) as raised:
        report_upload_completed(storage, persistence, jobs, DOCUMENT_ID)

    assert raised.value is error
    persistence.commit.assert_not_called()
    storage.delete_object.assert_not_called()


def test_report_upload_completed_does_not_enqueue_when_status_update_fails(
    completion_dependencies: tuple[Mock, Mock, Mock],
) -> None:
    storage, persistence, jobs = completion_dependencies
    persistence.update_document_upload_status.side_effect = RuntimeError(
        "update failed"
    )

    with pytest.raises(RuntimeError, match="update failed"):
        report_upload_completed(storage, persistence, jobs, DOCUMENT_ID)

    jobs.enqueue_new_job.assert_not_called()


def test_report_upload_completed_does_not_enqueue_when_storage_is_unavailable(
    completion_dependencies: tuple[Mock, Mock, Mock],
) -> None:
    storage, persistence, jobs = completion_dependencies
    storage.head_object.side_effect = StorageUnavailableError("unavailable")

    with pytest.raises(StorageUnavailableError, match="unavailable"):
        report_upload_completed(storage, persistence, jobs, DOCUMENT_ID)

    persistence.get_document_data.assert_not_called()
    jobs.enqueue_new_job.assert_not_called()


def test_report_upload_completed_preserves_uploaded_document_metadata(
    completion_dependencies: tuple[Mock, Mock, Mock],
) -> None:
    storage, persistence, jobs = completion_dependencies
    uploaded = replace(
        _document(),
        document_type="application/pdf",
        page_count=3,
        upload_status=DocumentUploadStatus.UPLOADED,
        processing_status=DocumentProcessingStatus.PROCESSED,
        uploaded_at=CREATED_AT,
        processed_at=CREATED_AT,
    )
    persistence.get_document_data.return_value = uploaded
    persistence.update_document_upload_status.return_value = uploaded

    response = report_upload_completed(storage, persistence, jobs, DOCUMENT_ID)

    assert response.document.id == uploaded.id
    assert response.document.document_type == uploaded.document_type
    assert response.document.page_count == uploaded.page_count
    assert response.document.processing_status is uploaded.processing_status
    assert response.document.created_at == uploaded.created_at
    assert response.document.uploaded_at == uploaded.uploaded_at
    assert response.document.processed_at == uploaded.processed_at
    jobs.enqueue_new_job.assert_called_once_with(DOCUMENT_ID)
