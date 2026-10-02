from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from supplylens.adapters.persistence.documents import DocumentPersistenceAdapter
from supplylens.adapters.storage.storage import StorageAdapter

## Controllers Imports
from supplylens.controllers.documents import (
    CreateUploadIntentCommand,
    CreateUploadIntentCommandResult,
    GetDocumentDataCommandResponse,
    GetDocumentURLCommandResponse,
    ReportUploadCompletedCommandResponse,
)
from supplylens.controllers.documents import (
    create_upload_intent as create_upload_intent_controller,
)
from supplylens.controllers.documents import (
    delete_document as delete_document_controller,
)
from supplylens.controllers.documents import (
    get_document_data as get_document_data_controller,
)
from supplylens.controllers.documents import (
    get_document_url as get_document_url_controller,
)
from supplylens.controllers.documents import (
    report_upload_completed as report_upload_completed_controller,
)
from supplylens.controllers.documents.exceptions import (
    DocumentInvalidContentTypeError,
    DocumentNotFoundError,
    DocumentNotUploadedError,
    StoreDocumentInvalidSizeError,
)

## Schemas Imports
from supplylens.database.database import get_session
from supplylens.port.storage.storage import StorageUnavailableError, UploadTooLargeError
from supplylens.schemas.common import ErrorResponse
from supplylens.schemas.documents import (
    CreateUploadIntentRequest,
    CreateUploadIntentResponse,
    GetDocumentDataResponse,
    GetDocumentURLResponse,
    ReportUploadCompletedResponse,
    UploadInstructions,
)

from .mappers import map_controller_document_to_schema_document

documents_router = APIRouter(prefix="/documents", tags=["Documents"])

_STORAGE_UNAVAILABLE_RESPONSE = {
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "model": ErrorResponse,
        "description": "Object storage is unavailable.",
    }
}
_VALIDATION_ERROR_SCHEMA = {"$ref": "#/components/schemas/HTTPValidationError"}


def _document_http_error(error: Exception) -> HTTPException:
    if isinstance(error, DocumentNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    if isinstance(error, DocumentNotUploadedError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document has not been uploaded.",
        )
    if isinstance(error, StoreDocumentInvalidSizeError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded document size does not match the declared size.",
        )
    if isinstance(error, DocumentInvalidContentTypeError):
        return HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Uploaded document must be a PDF.",
        )
    if isinstance(error, UploadTooLargeError):
        return HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Upload exceeds the maximum document size.",
        )
    if isinstance(error, StorageUnavailableError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Object storage is unavailable.",
        )
    raise TypeError(f"No HTTP mapping for {type(error).__name__}")


def _create_storage_adapter() -> StorageAdapter:
    try:
        return StorageAdapter()
    except ValueError as exc:
        unavailable = StorageUnavailableError("Invalid object storage configuration.")
        raise _document_http_error(unavailable) from exc


@documents_router.post(
    "/uploads",
    status_code=status.HTTP_201_CREATED,
    summary="Create a PDF upload intent",
    description=(
        "Creates a pending document record and returns a short-lived object storage "
        "URL. Send the PDF bytes to that URL using the returned HTTP method and "
        "headers, then call the upload completion endpoint with the returned ID. "
        "Only PDF files within the configured maximum size are accepted."
    ),
    responses={
        **_STORAGE_UNAVAILABLE_RESPONSE,
        status.HTTP_413_CONTENT_TOO_LARGE: {
            "model": ErrorResponse,
            "description": "The declared file size exceeds the configured limit.",
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": (
                "The request body is invalid, including an unsupported content "
                "type or invalid size."
            ),
            "content": {"application/json": {"schema": _VALIDATION_ERROR_SCHEMA}},
        },
    },
)
def create_upload_intent(
    req: CreateUploadIntentRequest,
    session: Annotated[Session, Depends(get_session, scope="function")],
) -> CreateUploadIntentResponse:
    persistence = DocumentPersistenceAdapter(session=session)
    storage = _create_storage_adapter()

    try:
        upload_intent_response: CreateUploadIntentCommandResult = (
            create_upload_intent_controller(
                storage=storage,
                persistence=persistence,
                req=CreateUploadIntentCommand(
                    filename=req.filename,
                    content_type=req.content_type,
                    size_bytes=req.size_bytes,
                ),
            )
        )
    except (UploadTooLargeError, StorageUnavailableError) as exc:
        raise _document_http_error(exc) from exc

    return CreateUploadIntentResponse(
        id=upload_intent_response.id,
        upload=UploadInstructions(
            url=upload_intent_response.upload.url,
            method=upload_intent_response.upload.method,
            headers=upload_intent_response.upload.headers,
            expires_in_seconds=upload_intent_response.upload.expires_in_seconds,
        ),
    )


@documents_router.post(
    "/{id}/complete",
    summary="Verify completion of a PDF upload",
    description=(
        "Verifies that the PDF exists in object storage and matches the declared "
        "size and media type, then marks the document as uploaded. A size mismatch "
        "returns 422 Unprocessable Entity."
    ),
    responses={
        **_STORAGE_UNAVAILABLE_RESPONSE,
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "The document or uploaded object was not found.",
        },
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {
            "model": ErrorResponse,
            "description": "The stored object is not a PDF.",
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": (
                "The upload size does not match the declared size, or the request "
                "path is invalid."
            ),
            "content": {
                "application/json": {
                    "schema": {
                        "oneOf": [
                            {"$ref": "#/components/schemas/ErrorResponse"},
                            _VALIDATION_ERROR_SCHEMA,
                        ]
                    }
                }
            },
        },
    },
)
def report_upload_completed(
    id: UUID,
    session: Annotated[Session, Depends(get_session, scope="function")],
) -> ReportUploadCompletedResponse:
    persistence = DocumentPersistenceAdapter(session=session)
    storage = _create_storage_adapter()
    try:
        upload_completed: ReportUploadCompletedCommandResponse = (
            report_upload_completed_controller(
                persistence=persistence, storage=storage, id=id
            )
        )
    except (
        DocumentNotFoundError,
        StoreDocumentInvalidSizeError,
        DocumentInvalidContentTypeError,
        StorageUnavailableError,
    ) as exc:
        raise _document_http_error(exc) from exc
    return ReportUploadCompletedResponse(
        document=map_controller_document_to_schema_document(upload_completed.document)
    )


@documents_router.get(
    "/{id}",
    summary="Get document metadata",
    description="Returns document metadata and its upload and processing states.",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "The document was not found.",
        }
    },
)
def get_document_data(
    id: UUID, session: Annotated[Session, Depends(get_session, scope="function")]
) -> GetDocumentDataResponse:
    persistence = DocumentPersistenceAdapter(session=session)
    try:
        document_data: GetDocumentDataCommandResponse = get_document_data_controller(
            persistence=persistence, id=id
        )
    except DocumentNotFoundError as exc:
        raise _document_http_error(exc) from exc

    return GetDocumentDataResponse(
        document=map_controller_document_to_schema_document(document_data.document)
    )


@documents_router.post(
    "/{id}/download-url",
    summary="Create a PDF download URL",
    description=(
        "Returns a short-lived URL for downloading an uploaded PDF. The document "
        "must exist and its upload must have been completed."
    ),
    responses={
        **_STORAGE_UNAVAILABLE_RESPONSE,
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "The document was not found.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "The document has not been uploaded yet.",
        },
    },
)
def get_document_url(
    id: UUID, session: Annotated[Session, Depends(get_session, scope="function")]
) -> GetDocumentURLResponse:
    persistence = DocumentPersistenceAdapter(session=session)
    storage = _create_storage_adapter()
    try:
        document_url: GetDocumentURLCommandResponse = get_document_url_controller(
            id=id, persistence=persistence, storage=storage
        )
    except (
        DocumentNotFoundError,
        DocumentNotUploadedError,
        StorageUnavailableError,
    ) as exc:
        raise _document_http_error(exc) from exc
    return GetDocumentURLResponse(
        id=document_url.id,
        url=document_url.url,
        expires_in_seconds=document_url.expires_in_seconds,
    )


@documents_router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a document",
    description=(
        "Deletes the document record and its stored PDF, if present. Returns no "
        "content after deletion."
    ),
    responses=_STORAGE_UNAVAILABLE_RESPONSE,
)
def delete_document(
    id: UUID, session: Annotated[Session, Depends(get_session, scope="function")]
) -> None:
    persistence = DocumentPersistenceAdapter(session=session)
    storage = _create_storage_adapter()
    try:
        delete_document_controller(id=id, persistence=persistence, storage=storage)
    except StorageUnavailableError as exc:
        raise _document_http_error(exc) from exc
    return
