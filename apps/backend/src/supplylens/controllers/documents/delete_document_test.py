from unittest.mock import Mock
from uuid import UUID

import pytest

from supplylens.controllers.documents.delete_document import delete_document
from supplylens.port.persistence.documents import DocumentPersistence
from supplylens.port.storage.storage import ObjectNotFoundError, ObjectStorage

DOCUMENT_ID = UUID("12345678-1234-5678-1234-567812345678")
OBJECT_KEY = f"documents/{DOCUMENT_ID}/original.pdf"


def test_delete_document_commits_soft_delete_then_removes_storage_object() -> None:
    storage = Mock(spec=ObjectStorage)
    persistence = Mock(spec=DocumentPersistence)

    delete_document(storage, persistence, DOCUMENT_ID)

    storage.delete_object.assert_called_once_with(OBJECT_KEY)
    persistence.delete_document.assert_called_once_with(DOCUMENT_ID)
    persistence.commit.assert_called_once_with()


def test_delete_document_still_deletes_record_when_storage_object_is_missing() -> None:
    storage = Mock(spec=ObjectStorage)
    persistence = Mock(spec=DocumentPersistence)
    storage.delete_object.side_effect = ObjectNotFoundError("already deleted")

    delete_document(storage, persistence, DOCUMENT_ID)

    persistence.delete_document.assert_called_once_with(DOCUMENT_ID)
    persistence.commit.assert_called_once_with()


def test_delete_document_preserves_soft_delete_when_storage_delete_fails() -> None:
    storage = Mock(spec=ObjectStorage)
    persistence = Mock(spec=DocumentPersistence)
    storage.delete_object.side_effect = RuntimeError("synthetic storage failure")

    with pytest.raises(RuntimeError, match="synthetic storage failure"):
        delete_document(storage, persistence, DOCUMENT_ID)

    persistence.delete_document.assert_called_once_with(DOCUMENT_ID)
    persistence.commit.assert_called_once_with()
