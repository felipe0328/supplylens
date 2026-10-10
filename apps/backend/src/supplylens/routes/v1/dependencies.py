from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from supplylens.adapters.persistence.documents import DocumentPersistenceAdapter
from supplylens.adapters.persistence.processing_job import (
    ProcessingJobPersistenceAdapter,
)
from supplylens.adapters.persistence.refresh_tokens import (
    RefreshTokenPersistenceAdapter,
)
from supplylens.adapters.persistence.users import UserPersistenceAdapter
from supplylens.adapters.storage.storage import StorageAdapter
from supplylens.database.database import get_session
from supplylens.domain.auth import AccessPrincipal
from supplylens.domain.users import UserRole
from supplylens.port.persistence.documents import DocumentPersistence
from supplylens.port.persistence.processing_job import ProcessingJobPersistence
from supplylens.port.persistence.refresh_token import RefreshTokenPersistence
from supplylens.port.persistence.users import UserPersistence
from supplylens.port.storage.storage import ObjectStorage, StorageUnavailableError
from supplylens.tools.encode_decode import decode_jwt

security = HTTPBearer()

SessionDependency = Annotated[Session, Depends(get_session, scope="function")]


def get_user_persistence(session: SessionDependency) -> UserPersistence:
    return UserPersistenceAdapter(session=session)


def get_refresh_token_persistence(
    session: SessionDependency,
) -> RefreshTokenPersistence:
    return RefreshTokenPersistenceAdapter(session=session)


def get_document_persistence(session: SessionDependency) -> DocumentPersistence:
    return DocumentPersistenceAdapter(session=session)


def get_processing_job_persistence(
    session: SessionDependency,
) -> ProcessingJobPersistence:
    return ProcessingJobPersistenceAdapter(session=session)


def get_object_storage() -> ObjectStorage:
    try:
        return StorageAdapter()
    except ValueError as exc:
        raise StorageUnavailableError("Invalid object storage configuration.") from exc


def require_access_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> AccessPrincipal:
    try:
        decoded = decode_jwt(credentials.credentials)
        subject = decoded["sub"]
        role = decoded["role"]
        if not isinstance(subject, str) or not isinstance(role, str):
            raise ValueError
        return AccessPrincipal(user_id=UUID(subject), role=UserRole(role))
    except InvalidTokenError, KeyError, ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


def required_admin(
    principal: Annotated[AccessPrincipal, Depends(require_access_token)],
) -> AccessPrincipal:
    if principal.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )
    return principal
