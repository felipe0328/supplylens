from uuid import UUID


def create_object_key(document_id: UUID) -> str:
    return f"documents/{document_id}/original.pdf"
