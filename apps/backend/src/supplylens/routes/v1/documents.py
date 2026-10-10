from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse

from supplylens.controllers.documents.create_upload_intent import (
    CreateUploadIntentCommand,
)
from supplylens.controllers.documents.create_upload_intent import (
    create_upload_intent as create_upload_intent_controller,
)
from supplylens.controllers.documents.delete_document import (
    delete_document as delete_document_controller,
)
from supplylens.controllers.documents.exceptions import (
    DocumentInvalidContentTypeError,
    DocumentNotFoundError,
    DocumentNotUploadedError,
    InvalidJobProcessingID,
    StoreDocumentInvalidSizeError,
)
from supplylens.controllers.documents.get_document_data import (
    get_document_data as get_document_data_controller,
)
from supplylens.controllers.documents.get_document_url import (
    get_document_url as get_document_url_controller,
)
from supplylens.controllers.documents.report_upload_completed import (
    ReportUploadCompletedRejection,
)
from supplylens.controllers.documents.report_upload_completed import (
    report_upload_completed as report_upload_completed_controller,
)
from supplylens.port.persistence.documents import Document as StoredDocument
from supplylens.port.persistence.documents import DocumentPersistence
from supplylens.port.persistence.processing_job import ProcessingJobPersistence
from supplylens.port.storage.storage import (
    ObjectStorage,
    StorageUnavailableError,
    UploadTooLargeError,
)
from supplylens.schemas.documents import (
    CreateUploadIntentRequest,
    CreateUploadIntentResponse,
    Document,
    GetDocumentDataResponse,
    GetDocumentURLResponse,
    ReportUploadCompletedResponse,
    UploadInstructions,
)

from .dependencies import (
    get_document_persistence,
    get_object_storage,
    get_processing_job_persistence,
)
from .errors import error_responses, http_error_response

documents_router = APIRouter(prefix="/documents", tags=["Documents"])


def to_document_schema(document: StoredDocument) -> Document:
    return Document(
        id=document.id,
        filename=document.filename,
        size_bytes=document.size_bytes,
        document_type=document.document_type,
        page_count=document.page_count,
        upload_status=document.upload_status,
        processing_status=document.processing_status,
        created_at=document.created_at,
        uploaded_at=document.uploaded_at,
        processed_at=document.processed_at,
    )


@documents_router.post(
    "/uploads",
    status_code=status.HTTP_201_CREATED,
    summary="Create a PDF upload intent",
    responses=error_responses(
        UploadTooLargeError,
        StorageUnavailableError,
        validation=True,
    ),
)
def create_upload_intent(
    request: CreateUploadIntentRequest,
    persistence: Annotated[DocumentPersistence, Depends(get_document_persistence)],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
) -> CreateUploadIntentResponse:
    """Creates a pending document record and returns a short-lived object storage
    URL. Send the PDF bytes to that URL using the returned HTTP method and
    headers, then call the upload completion endpoint with the returned ID.
    Only PDF files within the configured maximum size are accepted.
    """
    upload_intent = create_upload_intent_controller(
        storage=storage,
        persistence=persistence,
        req=CreateUploadIntentCommand(
            filename=request.filename,
            content_type=request.content_type,
            size_bytes=request.size_bytes,
        ),
    )
    return CreateUploadIntentResponse(
        id=upload_intent.id,
        upload=UploadInstructions(
            url=upload_intent.upload.url,
            method=upload_intent.upload.method,
            headers=upload_intent.upload.headers,
            expires_in_seconds=upload_intent.upload.expires_in_seconds,
        ),
    )


@documents_router.post(
    "/{id}/complete",
    response_model=ReportUploadCompletedResponse,
    summary="Verify completion of a PDF upload",
    responses=error_responses(
        DocumentNotFoundError,
        DocumentInvalidContentTypeError,
        StoreDocumentInvalidSizeError,
        StorageUnavailableError,
        InvalidJobProcessingID,
        validation=True,
    ),
)
def report_upload_completed(
    id: UUID,
    document_persistence: Annotated[
        DocumentPersistence, Depends(get_document_persistence)
    ],
    job_processing_persistence: Annotated[
        ProcessingJobPersistence, Depends(get_processing_job_persistence)
    ],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
) -> ReportUploadCompletedResponse | JSONResponse:
    """Verifies that the PDF exists in object storage and matches the declared
    size and media type, then marks the document as uploaded. A size mismatch
    returns 422 Unprocessable Entity.
    """
    outcome = report_upload_completed_controller(
        document_persistence=document_persistence,
        storage=storage,
        id=id,
        job_processing_persistence=job_processing_persistence,
    )
    if isinstance(outcome, ReportUploadCompletedRejection):
        return http_error_response(outcome.error)
    return ReportUploadCompletedResponse(document=to_document_schema(outcome.document))


@documents_router.get(
    "/{id}",
    summary="Get document metadata",
    description="Returns document metadata and its upload and processing states.",
    responses=error_responses(DocumentNotFoundError),
)
def get_document_data(
    id: UUID,
    persistence: Annotated[DocumentPersistence, Depends(get_document_persistence)],
) -> GetDocumentDataResponse:
    document_data = get_document_data_controller(persistence=persistence, id=id)
    return GetDocumentDataResponse(document=to_document_schema(document_data.document))


@documents_router.post(
    "/{id}/download-url",
    summary="Create a PDF download URL",
    responses=error_responses(
        DocumentNotFoundError,
        DocumentNotUploadedError,
        StorageUnavailableError,
    ),
)
def get_document_url(
    id: UUID,
    persistence: Annotated[DocumentPersistence, Depends(get_document_persistence)],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
) -> GetDocumentURLResponse:
    """Returns a short-lived URL for downloading an uploaded PDF. The document
    must exist and its upload must have been completed.
    """
    document_url = get_document_url_controller(
        id=id, persistence=persistence, storage=storage
    )
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
    responses=error_responses(StorageUnavailableError),
)
def delete_document(
    id: UUID,
    persistence: Annotated[DocumentPersistence, Depends(get_document_persistence)],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
) -> None:
    """Deletes the document record and its stored PDF, if present. Returns no
    content after deletion.
    """
    delete_document_controller(id=id, persistence=persistence, storage=storage)
