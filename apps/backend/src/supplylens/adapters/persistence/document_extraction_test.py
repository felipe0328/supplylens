from collections.abc import Iterator
from datetime import datetime
from uuid import UUID

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from supplylens.adapters.persistence.document_extraction import (
    DocumentExtractionPersistenceAdapter,
)
from supplylens.database.database import Base
from supplylens.domain.document_extraction import DocumentExtractionOutcome
from supplylens.models.document import Document
from supplylens.models.document_extraction import (
    DocumentExtraction as DocumentExtractionModel,
)
from supplylens.models.processing_job import ProcessingJob
from supplylens.port.persistence.document_extraction import DocumentExtraction

DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000001")
OTHER_DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000002")


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(engine)
        with Session(engine, autoflush=False) as database_session:
            database_session.add(
                Document(id=DOCUMENT_ID, filename="synthetic.pdf", size_bytes=128)
            )
            database_session.add(
                Document(id=OTHER_DOCUMENT_ID, filename="other.pdf", size_bytes=64)
            )
            database_session.commit()
            yield database_session
    finally:
        engine.dispose()


@pytest.fixture
def processing_job_id(session: Session) -> int:
    job = ProcessingJob(document_id=DOCUMENT_ID)
    session.add(job)
    session.flush()
    return job.id


def test_save_inserts_extraction_and_leaves_commit_to_caller(
    session: Session, processing_job_id: int
) -> None:
    adapter = DocumentExtractionPersistenceAdapter(session)
    payload = {"pages": [{"page_number": 1, "text": "line"}]}

    saved = adapter.save_extraction_outcome(
        document_id=DOCUMENT_ID,
        processing_job_id=processing_job_id,
        outcome=DocumentExtractionOutcome.EXTRACTED,
        extraction=payload,
    )

    assert isinstance(saved, DocumentExtraction)
    assert isinstance(saved.id, UUID)
    assert saved.document_id == DOCUMENT_ID
    assert saved.processing_job_id == processing_job_id
    assert saved.outcome is DocumentExtractionOutcome.EXTRACTED
    assert saved.extraction == payload
    assert isinstance(saved.created_at, datetime)
    assert (
        session.scalar(
            select(DocumentExtractionModel).where(
                DocumentExtractionModel.processing_job_id == processing_job_id
            )
        )
        is not None
    )

    session.rollback()

    assert adapter.get_by_processing_job_id(processing_job_id) is None


def test_save_commits_when_caller_commits(
    session: Session, processing_job_id: int
) -> None:
    adapter = DocumentExtractionPersistenceAdapter(session)
    saved = adapter.save_extraction_outcome(
        document_id=DOCUMENT_ID,
        processing_job_id=processing_job_id,
        outcome=DocumentExtractionOutcome.EXTRACTED,
        extraction={"pages": []},
    )

    session.commit()

    with Session(session.get_bind()) as verification_session:
        verification_adapter = DocumentExtractionPersistenceAdapter(
            verification_session
        )
        loaded = verification_adapter.get_by_processing_job_id(processing_job_id)

    assert loaded is not None
    assert loaded.id == saved.id
    assert loaded.extraction == {"pages": []}


def test_get_by_processing_job_id_returns_none_when_missing(session: Session) -> None:
    adapter = DocumentExtractionPersistenceAdapter(session)

    assert adapter.get_by_processing_job_id(999_999) is None


def test_save_upserts_by_processing_job_id_preserving_id_and_created_at(
    session: Session, processing_job_id: int
) -> None:
    adapter = DocumentExtractionPersistenceAdapter(session)
    first = adapter.save_extraction_outcome(
        document_id=DOCUMENT_ID,
        processing_job_id=processing_job_id,
        outcome=DocumentExtractionOutcome.EXTRACTED,
        extraction={"pages": [{"page_number": 1, "text": "v1"}]},
    )
    session.commit()

    second = adapter.save_extraction_outcome(
        document_id=DOCUMENT_ID,
        processing_job_id=processing_job_id,
        outcome=DocumentExtractionOutcome.UNSUPPORTED_IMAGEN_ONLY,
        extraction={"reason": "no_selectable_text"},
    )
    session.commit()

    assert second.id == first.id
    assert second.created_at == first.created_at
    assert second.outcome is DocumentExtractionOutcome.UNSUPPORTED_IMAGEN_ONLY
    assert second.extraction == {"reason": "no_selectable_text"}

    rows = session.scalars(select(DocumentExtractionModel)).all()
    assert len(rows) == 1


def test_save_upsert_can_update_document_id(
    session: Session, processing_job_id: int
) -> None:
    adapter = DocumentExtractionPersistenceAdapter(session)
    adapter.save_extraction_outcome(
        document_id=DOCUMENT_ID,
        processing_job_id=processing_job_id,
        outcome=DocumentExtractionOutcome.EXTRACTED,
        extraction={"pages": []},
    )

    updated = adapter.save_extraction_outcome(
        document_id=OTHER_DOCUMENT_ID,
        processing_job_id=processing_job_id,
        outcome=DocumentExtractionOutcome.EXTRACTED,
        extraction={"pages": [{"page_number": 1}]},
    )

    assert updated.document_id == OTHER_DOCUMENT_ID
    assert updated.extraction == {"pages": [{"page_number": 1}]}


@pytest.mark.parametrize("outcome", list(DocumentExtractionOutcome))
def test_save_persists_all_outcomes(
    session: Session, processing_job_id: int, outcome: DocumentExtractionOutcome
) -> None:
    adapter = DocumentExtractionPersistenceAdapter(session)

    saved = adapter.save_extraction_outcome(
        document_id=DOCUMENT_ID,
        processing_job_id=processing_job_id,
        outcome=outcome,
        extraction={"outcome": outcome.value},
    )

    assert saved.outcome is outcome
    assert adapter.get_by_processing_job_id(processing_job_id) == saved
