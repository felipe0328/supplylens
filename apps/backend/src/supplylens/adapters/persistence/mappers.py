from supplylens.models.document import Document as ModelDocument
from supplylens.models.processing_job import ProcessingJob as ModelProcessingJob
from supplylens.models.refresh_token import RefreshToken as ModelRefreshToken
from supplylens.models.user import User as ModelUser
from supplylens.port.persistence.documents import Document as AbstractDocument
from supplylens.port.persistence.processing_job import (
    ProcessingJob as AbstractProcessingJob,
)
from supplylens.port.persistence.refresh_token import (
    RefreshToken as AbstractRefreshToken,
)
from supplylens.port.persistence.users import User as AbstractUser


def map_model_document_to_abstraction(
    model_document: ModelDocument,
) -> AbstractDocument:
    return AbstractDocument(
        id=model_document.id,
        filename=model_document.filename,
        size_bytes=model_document.size_bytes,
        document_type=model_document.document_type,
        page_count=model_document.page_count,
        upload_status=model_document.upload_status,
        processing_status=model_document.processing_status,
        created_at=model_document.created_at,
        uploaded_at=model_document.uploaded_at,
        processed_at=model_document.processed_at,
    )


def map_model_processing_job_to_abstraction(
    model_processing_job: ModelProcessingJob | None,
) -> AbstractProcessingJob | None:
    if model_processing_job is None:
        return None
    return AbstractProcessingJob(
        id=model_processing_job.id,
        document_uuid=model_processing_job.document_id,
        attempts=model_processing_job.attempts,
        status=model_processing_job.status,
        lease_owner=model_processing_job.lease_owner,
        lease_expires_at=model_processing_job.lease_expires_at,
        error_code=model_processing_job.error_code,
        error_message=model_processing_job.error_message,
        created_at=model_processing_job.created_at,
        started_at=model_processing_job.started_at,
        finished_at=model_processing_job.finished_at,
    )


def map_model_user_to_abstraction(
    model_user: ModelUser | None,
    accepted_by: ModelUser | None = None,
) -> AbstractUser | None:
    if model_user is None:
        return None

    return AbstractUser(
        id=model_user.id,
        email=model_user.email,
        password_hash=model_user.password_hash,
        role=model_user.role,
        status=model_user.status,
        accepted_by=map_model_user_to_abstraction(accepted_by),
        pending_expires_at=model_user.pending_expires_at,
        created_at=model_user.created_at,
        updated_at=model_user.updated_at,
        deleted_at=model_user.deleted_at,
    )


def map_model_refresh_token_to_abstraction(
    model_refresh_token: ModelRefreshToken | None,
) -> AbstractRefreshToken | None:
    if model_refresh_token is None:
        return None
    return AbstractRefreshToken(
        id=model_refresh_token.id,
        user_id=model_refresh_token.user_id,
        hashed_token=model_refresh_token.hashed_token,
        expires_at=model_refresh_token.expires_at,
        revoked_at=model_refresh_token.revoked_at,
        replaced_by=model_refresh_token.replaced_by,
    )
