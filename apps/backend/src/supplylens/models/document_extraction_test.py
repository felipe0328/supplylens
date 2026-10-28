from collections.abc import Iterator
from uuid import UUID

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from supplylens.database.database import Base
from supplylens.domain.document_extraction import DocumentExtractionOutcome
from supplylens.models.document import Document
from supplylens.models.document_extraction import DocumentExtraction
from supplylens.models.processing_job import ProcessingJob


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(engine)

        with Session(engine) as database_session:
            yield database_session
    finally:
        engine.dispose()


@pytest.fixture
def document_id(session: Session) -> UUID:
    document = Document(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        filename="synthetic.pdf",
        size_bytes=128,
    )
    session.add(document)
    session.flush()
    return document.id


@pytest.fixture
def processing_job_id(session: Session, document_id: UUID) -> int:
    job = ProcessingJob(document_id=document_id)
    session.add(job)
    session.flush()
    return job.id


def test_document_extraction_persists_defaults_and_json(
    session: Session, document_id: UUID, processing_job_id: int
) -> None:
    payload = {
        "provenance": "digital_parser",
        "pages": [{"page_number": 1, "text": "line", "tables": []}],
    }
    extraction = DocumentExtraction(
        document_id=document_id,
        processing_job_id=processing_job_id,
        outcome=DocumentExtractionOutcome.EXTRACTED,
        extraction=payload,
    )
    session.add(extraction)
    session.flush()
    extraction_id = extraction.id
    session.commit()
    session.expunge_all()

    persisted = session.get(DocumentExtraction, extraction_id)

    assert persisted is not None
    assert isinstance(persisted.id, UUID)
    assert persisted.document_id == document_id
    assert persisted.processing_job_id == processing_job_id
    assert persisted.outcome is DocumentExtractionOutcome.EXTRACTED
    assert persisted.extraction == payload
    assert persisted.created_at is not None


@pytest.mark.parametrize("outcome", list(DocumentExtractionOutcome))
def test_document_extraction_persists_outcomes(
    session: Session,
    document_id: UUID,
    processing_job_id: int,
    outcome: DocumentExtractionOutcome,
) -> None:
    extraction = DocumentExtraction(
        document_id=document_id,
        processing_job_id=processing_job_id,
        outcome=outcome,
        extraction={"reason": "synthetic"},
    )
    session.add(extraction)
    session.flush()
    extraction_id = extraction.id
    session.commit()
    session.expunge_all()

    persisted = session.get(DocumentExtraction, extraction_id)

    assert persisted is not None
    assert persisted.outcome is outcome


def test_document_extraction_rejects_duplicate_processing_job_id(
    session: Session, document_id: UUID, processing_job_id: int
) -> None:
    session.add(
        DocumentExtraction(
            document_id=document_id,
            processing_job_id=processing_job_id,
            outcome=DocumentExtractionOutcome.EXTRACTED,
            extraction={"pages": []},
        )
    )
    session.flush()

    session.add(
        DocumentExtraction(
            document_id=document_id,
            processing_job_id=processing_job_id,
            outcome=DocumentExtractionOutcome.UNSUPPORTED_IMAGEN_ONLY,
            extraction={"reason": "no_selectable_text"},
        )
    )

    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize(
    "invalid_document_id",
    [None, UUID("00000000-0000-0000-0000-000000000099")],
)
def test_document_extraction_rejects_missing_or_unknown_document(
    session: Session,
    processing_job_id: int,
    invalid_document_id: UUID | None,
) -> None:
    session.add(
        DocumentExtraction(
            document_id=invalid_document_id,
            processing_job_id=processing_job_id,
            outcome=DocumentExtractionOutcome.EXTRACTED,
            extraction={},
        )
    )

    with pytest.raises(IntegrityError):
        session.flush()


def test_document_extraction_rejects_unknown_processing_job(
    session: Session, document_id: UUID
) -> None:
    session.add(
        DocumentExtraction(
            document_id=document_id,
            processing_job_id=999_999,
            outcome=DocumentExtractionOutcome.EXTRACTED,
            extraction={},
        )
    )

    with pytest.raises(IntegrityError):
        session.flush()


def test_document_extraction_has_document_id_index_and_unique_job(
    session: Session,
) -> None:
    indexes = inspect(session.get_bind()).get_indexes("document_extractions")
    unique_constraints = inspect(session.get_bind()).get_unique_constraints(
        "document_extractions"
    )

    assert any(
        index["column_names"] == ["document_id"] and not index["unique"]
        for index in indexes
    )
    assert any(
        constraint["column_names"] == ["processing_job_id"]
        for constraint in unique_constraints
    ) or any(
        index["column_names"] == ["processing_job_id"] and index["unique"]
        for index in indexes
    )
