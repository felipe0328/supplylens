from uuid import UUID

from supplylens.controllers.documents.helpers import create_object_key


def test_create_object_key_builds_document_original_path() -> None:
    document_id = UUID("12345678-1234-5678-1234-567812345678")

    assert create_object_key(document_id) == (
        "documents/12345678-1234-5678-1234-567812345678/original.pdf"
    )
