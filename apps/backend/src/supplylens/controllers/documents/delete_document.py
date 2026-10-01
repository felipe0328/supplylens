from uuid import UUID

from supplylens.port.persistence.documents import DocumentPersistence
from supplylens.port.storage.storage import ObjectNotFoundError, ObjectStorage

from .helpers import create_object_key


def delete_document(
    storage: ObjectStorage, persistence: DocumentPersistence, document_id: UUID
) -> None:
    object_key = create_object_key(document_id)

    try:
        storage.delete_object(object_key)
    except ObjectNotFoundError:
        pass  # Already deleted, or never uploaded.

    persistence.delete_document(document_id)
