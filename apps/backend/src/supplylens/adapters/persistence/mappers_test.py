from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from uuid import UUID

import pytest

from supplylens.adapters.persistence.mappers import (
    map_model_document_to_abstraction,
    map_model_processing_job_to_abstraction,
)
from supplylens.domain.documents import DocumentProcessingStatus, DocumentUploadStatus
from supplylens.domain.processing_job import ProcessingJobState
from supplylens.models.document import Document as ModelDocument
from supplylens.models.processing_job import ProcessingJob as ModelProcessingJob
from supplylens.port.persistence.documents import Document
from supplylens.port.persistence.processing_job import ProcessingJob

DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000001")
CREATED_AT = datetime(2026, 1, 1, tzinfo=UTC)
STARTED_AT = datetime(2026, 1, 1, 0, 1, tzinfo=UTC)
FINISHED_AT = datetime(2026, 1, 1, 0, 2, tzinfo=UTC)


@pytest.mark.parametrize("with_optional_values", [False, True])
def test_document_mapper_preserves_all_fields(with_optional_values: bool) -> None:
    expected = Document(
        id=DOCUMENT_ID,
        filename="synthetic.pdf",
        size_bytes=512,
        document_type="application/pdf" if with_optional_values else None,
        page_count=3 if with_optional_values else None,
        upload_status=DocumentUploadStatus.UPLOADED,
        processing_status=DocumentProcessingStatus.PROCESSED,
        created_at=CREATED_AT,
        uploaded_at=STARTED_AT if with_optional_values else None,
        processed_at=FINISHED_AT if with_optional_values else None,
    )
    model = ModelDocument(
        id=expected.id,
        filename=expected.filename,
        size_bytes=expected.size_bytes,
        document_type=expected.document_type,
        page_count=expected.page_count,
        upload_status=expected.upload_status,
        processing_status=expected.processing_status,
        created_at=expected.created_at,
        uploaded_at=expected.uploaded_at,
        processed_at=expected.processed_at,
    )

    assert map_model_document_to_abstraction(model) == expected


def test_processing_job_mapper_returns_none_for_missing_model() -> None:
    assert map_model_processing_job_to_abstraction(None) is None


@pytest.mark.parametrize("status", list(ProcessingJobState))
@pytest.mark.parametrize("with_optional_values", [False, True])
def test_processing_job_mapper_preserves_all_fields(
    status: ProcessingJobState, with_optional_values: bool
) -> None:
    expected = ProcessingJob(
        id=42,
        document_uuid=DOCUMENT_ID,
        attempts=3,
        status=status,
        lease_owner="synthetic-worker" if with_optional_values else None,
        lease_expires_at=FINISHED_AT if with_optional_values else None,
        error_code=17 if with_optional_values else None,
        error_message="Synthetic failure" if with_optional_values else None,
        created_at=CREATED_AT,
        started_at=STARTED_AT if with_optional_values else None,
        finished_at=FINISHED_AT if with_optional_values else None,
    )
    model = ModelProcessingJob(
        id=expected.id,
        document_id=expected.document_uuid,
        attempts=expected.attempts,
        status=expected.status,
        lease_owner=expected.lease_owner,
        lease_expires_at=expected.lease_expires_at,
        error_code=expected.error_code,
        error_message=expected.error_message,
        created_at=expected.created_at,
        started_at=expected.started_at,
        finished_at=expected.finished_at,
    )

    mapped = map_model_processing_job_to_abstraction(model)

    assert mapped == expected
    assert isinstance(mapped, ProcessingJob)
    with pytest.raises(FrozenInstanceError):
        mapped.attempts = 99
    model.attempts = 4
    assert mapped.attempts == 3
