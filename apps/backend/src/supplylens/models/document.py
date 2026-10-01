import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from supplylens.database.database import Base
from supplylens.domain.documents import DocumentProcessingStatus, DocumentUploadStatus


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    filename: Mapped[str]
    size_bytes: Mapped[int]
    document_type: Mapped[str | None]
    page_count: Mapped[int | None]

    upload_status: Mapped[DocumentUploadStatus] = mapped_column(
        default=DocumentUploadStatus.PENDING
    )
    processing_status: Mapped[DocumentProcessingStatus] = mapped_column(
        default=DocumentProcessingStatus.PENDING
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("filename <> ''", name="ck_document_filename_not_empty"),
        CheckConstraint("size_bytes >= 0", name="ck_document_size_bytes_positive"),
        CheckConstraint("document_type <> ''", name="ck_document_type_not_empty"),
        CheckConstraint("page_count >= 0", name="ck_document_page_count_positive"),
    )
