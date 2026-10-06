from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from supplylens.database.database import Base
from supplylens.domain.processing_job import ProcessingJobState


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), index=True)
    attempts: Mapped[int] = mapped_column(default=1)
    status: Mapped[ProcessingJobState] = mapped_column(
        default=ProcessingJobState.PENDING
    )
    lease_owner: Mapped[str | None]
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[int | None]
    error_message: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("attempts >= 0 ", name="ck_attempts_positive"),
        CheckConstraint(
            "(lease_owner IS NULL) = (lease_expires_at IS NULL)",
            name="ck_processing_job_lease_fields_paired",
        ),
    )
