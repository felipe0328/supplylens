from datetime import datetime
from uuid import UUID, uuid7

from sqlalchemy import DateTime, ForeignKey, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from supplylens.database.database import Base
from supplylens.domain.document_extraction import DocumentExtractionOutcome


class DocumentExtraction(Base):
    __tablename__ = "document_extractions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    document_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("documents.id"), index=True
    )
    processing_job_id: Mapped[int] = mapped_column(
        ForeignKey("processing_jobs.id"), unique=True
    )
    outcome: Mapped[DocumentExtractionOutcome]
    extraction: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
