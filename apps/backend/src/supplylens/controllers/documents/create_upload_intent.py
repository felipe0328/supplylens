from dataclasses import dataclass
from uuid import UUID, uuid7

from supplylens.port.persistence.documents import DocumentPersistence
from supplylens.port.storage.storage import ObjectStorage, PresignedURL

from .exceptions import MismatchBetweenPersistenceAndStorageError
from .helpers import create_object_key


@dataclass(frozen=True)
class CreateUploadIntentCommand:
    filename: str
    content_type: str
    size_bytes: int


@dataclass(frozen=True)
class CreateUploadIntentCommandResult:
    id: UUID
    upload: UploadInstructions


@dataclass(frozen=True)
class UploadInstructions:
    url: str
    method: str
    headers: dict[str, str]
    expires_in_seconds: int


def create_upload_intent(
    storage: ObjectStorage,
    persistence: DocumentPersistence,
    req: CreateUploadIntentCommand,
) -> CreateUploadIntentCommandResult:
    new_uuid: UUID = uuid7()
    object_key = create_object_key(new_uuid)

    document = persistence.create_new_document(
        id=new_uuid,
        filename=req.filename,
        size_bytes=req.size_bytes,
    )

    if document.id != new_uuid:
        raise MismatchBetweenPersistenceAndStorageError(
            f"Document UUID mismatch: expected {new_uuid}, got {document.id}"
        )

    upload_url: PresignedURL = storage.create_upload_url(
        object_key=object_key,
        content_type=req.content_type,
        size_bytes=req.size_bytes,
    )

    return CreateUploadIntentCommandResult(
        id=new_uuid,
        upload=UploadInstructions(
            url=upload_url.url,
            method=upload_url.method,
            headers=upload_url.headers,
            expires_in_seconds=upload_url.expires_in_seconds,
        ),
    )
