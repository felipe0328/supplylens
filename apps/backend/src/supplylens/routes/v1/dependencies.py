from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from supplylens.adapters.persistence.documents import DocumentPersistenceAdapter
from supplylens.adapters.persistence.processing_job import (
    ProcessingJobPersistenceAdapter,
)
from supplylens.adapters.persistence.users import UserPersistenceAdapter
from supplylens.adapters.storage.storage import StorageAdapter
from supplylens.database.database import get_session
from supplylens.port.persistence.documents import DocumentPersistence
from supplylens.port.persistence.processing_job import ProcessingJobPersistence
from supplylens.port.persistence.users import UserPersistence
from supplylens.port.storage.storage import ObjectStorage, StorageUnavailableError

SessionDependency = Annotated[Session, Depends(get_session, scope="function")]


def get_user_persistence(session: SessionDependency) -> UserPersistence:
    return UserPersistenceAdapter(session=session)


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
