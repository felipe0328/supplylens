from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from supplylens.domain.documents import DocumentUploadStatus
from supplylens.models.document import Document as DocumentModel
from supplylens.port.persistence.documents import Document as AbstractDocument
from supplylens.port.persistence.documents import DocumentPersistence

from .mappers import map_model_to_abstraction


class DocumentPersistenceAdapter(DocumentPersistence):
    """Flush document writes; the caller owns transaction commit and rollback."""

    _session: Session

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_new_document(
        self,
        id: UUID,
        filename: str,
        size_bytes: int,
    ) -> AbstractDocument:
        new_document = DocumentModel(
            id=id,
            filename=filename,
            size_bytes=size_bytes,
        )
        self._session.add(new_document)
        self._session.flush()
        return map_model_to_abstraction(new_document)

    def delete_document(self, id: UUID) -> None:
        document = self._session.get(DocumentModel, id)
        if document is not None:
            document.deleted_at = func.now()
            self._session.flush()

    def get_document_data(self, id: UUID) -> AbstractDocument | None:
        document = self._session.scalar(
            select(DocumentModel).where(
                DocumentModel.id == id,
                DocumentModel.deleted_at.is_(None),
            )
        )
        if document is not None:
            return map_model_to_abstraction(document)
        return None

    def update_document_upload_status(
        self, id: UUID, new_status: DocumentUploadStatus
    ) -> AbstractDocument:
        document = self._session.get(DocumentModel, id)
        if document is None:
            raise ValueError(f"Document with ID {id} not found")
        previous_status = document.upload_status
        document.upload_status = new_status
        if (
            new_status == DocumentUploadStatus.UPLOADED
            and previous_status != DocumentUploadStatus.UPLOADED
        ):
            document.uploaded_at = func.now()
        self._session.flush()
        return map_model_to_abstraction(document)

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()
