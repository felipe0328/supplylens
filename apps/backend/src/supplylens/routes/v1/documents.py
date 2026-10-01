from uuid import UUID

from fastapi import APIRouter, Response, status

from supplylens.schemas.documents import (
    CreateUploadIntentRequest,
    CreateUploadIntentResponse,
    GetDocumentDataResponse,
    GetDocumentURLResponse,
    ReportUploadCompletedRequest,
    ReportUploadCompletedResponse,
)

documents_router = APIRouter(prefix="/documents", tags=["Documents"])


@documents_router.post("/uploads")
def create_upload_intent(
    req: CreateUploadIntentRequest,
) -> CreateUploadIntentResponse:
    return {}


@documents_router.post("/{id}/complete")
def report_upload_completed(
    id: UUID, req: ReportUploadCompletedRequest | None = None
) -> ReportUploadCompletedResponse:
    return {}


@documents_router.get("/{id}")
def get_document_data(id: UUID) -> GetDocumentDataResponse:
    return {}


@documents_router.post("/{id}/download-url")
def get_document_url(id: UUID) -> GetDocumentURLResponse:
    return {}


@documents_router.delete(
    "/{id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response
)
def delete_document(id: UUID) -> None:
    return
