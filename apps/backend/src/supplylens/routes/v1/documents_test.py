from collections.abc import Iterator
from datetime import datetime
from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.session import SessionTransaction
from sqlalchemy.pool import StaticPool

from supplylens.adapters.persistence.documents import DocumentPersistenceAdapter
from supplylens.adapters.persistence.processing_job import (
    ProcessingJobPersistenceAdapter,
)
from supplylens.api import create_app
from supplylens.config import AppEnvironment
from supplylens.controllers.documents.create_upload_intent import (
    CreateUploadIntentCommandResult,
    UploadInstructions,
)
from supplylens.controllers.documents.exceptions import (
    DocumentInvalidContentTypeError,
    DocumentNotFoundError,
    DocumentNotUploadedError,
    InvalidJobProcessingID,
    StoreDocumentInvalidSizeError,
)
from supplylens.controllers.documents.get_document_url import (
    GetDocumentURLCommandResponse,
)
from supplylens.database import database
from supplylens.database.database import Base
from supplylens.domain.documents import DocumentProcessingStatus, DocumentUploadStatus
from supplylens.models.document import Document as ModelDocument
from supplylens.models.processing_job import ProcessingJob as ModelProcessingJob
from supplylens.port.persistence.documents import Document as StoredDocument
from supplylens.port.storage.storage import (
    ObjectInfo,
    ObjectStorage,
    StorageUnavailableError,
    UploadTooLargeError,
)
from supplylens.routes.v1 import documents
from supplylens.routes.v1.dependencies import (
    get_document_persistence,
    get_object_storage,
    get_processing_job_persistence,
)
from supplylens.routes.v1.documents import to_document_schema

DOCUMENT_ID = UUID("12345678-1234-5678-1234-567812345678")
UPLOAD_REQUEST = {
    "filename": "invoice.pdf",
    "content_type": "application/pdf",
    "size_bytes": 512,
}


@pytest.fixture
def upload_client(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, Mock]:
    app = create_app(AppEnvironment.TESTING)
    app.dependency_overrides[get_document_persistence] = lambda: Mock()
    app.dependency_overrides[get_object_storage] = lambda: Mock()
    controller = Mock()
    monkeypatch.setattr(documents, "create_upload_intent_controller", controller)
    return TestClient(app), controller


def test_create_upload_intent_returns_created(
    upload_client: tuple[TestClient, Mock],
) -> None:
    client, controller = upload_client
    controller.return_value = CreateUploadIntentCommandResult(
        id=DOCUMENT_ID,
        upload=UploadInstructions(
            url="https://storage.invalid/upload",
            method="PUT",
            headers={"Content-Type": "application/pdf"},
            expires_in_seconds=900,
        ),
    )

    response = client.post("/api/v1/documents/uploads", json=UPLOAD_REQUEST)

    assert response.status_code == 201
    assert response.json() == {
        "id": str(DOCUMENT_ID),
        "upload": {
            "url": "https://storage.invalid/upload",
            "method": "PUT",
            "headers": {"Content-Type": "application/pdf"},
            "expires_in_seconds": 900,
        },
    }


def test_create_upload_intent_normalizes_filename(
    upload_client: tuple[TestClient, Mock],
) -> None:
    client, controller = upload_client
    controller.return_value = CreateUploadIntentCommandResult(
        id=DOCUMENT_ID,
        upload=UploadInstructions(
            url="https://storage.invalid/upload",
            method="PUT",
            headers={"Content-Type": "application/pdf"},
            expires_in_seconds=900,
        ),
    )

    response = client.post(
        "/api/v1/documents/uploads",
        json={**UPLOAD_REQUEST, "filename": "  invoice.pdf  "},
    )

    assert response.status_code == 201
    assert controller.call_args.kwargs["req"].filename == "invoice.pdf"


@pytest.mark.parametrize("filename", [" ", "\t", "\n"])
def test_create_upload_intent_rejects_blank_filename(
    upload_client: tuple[TestClient, Mock], filename: str
) -> None:
    client, controller = upload_client

    response = client.post(
        "/api/v1/documents/uploads",
        json={**UPLOAD_REQUEST, "filename": filename},
    )

    assert response.status_code == 422
    controller.assert_not_called()


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (
            UploadTooLargeError("limit exceeded"),
            413,
            "Upload exceeds the maximum document size.",
        ),
        (
            StorageUnavailableError("storage timeout"),
            503,
            "Object storage is unavailable.",
        ),
    ],
)
def test_create_upload_intent_maps_expected_errors(
    upload_client: tuple[TestClient, Mock],
    error: Exception,
    expected_status: int,
    expected_detail: str,
) -> None:
    client, controller = upload_client
    controller.side_effect = error

    response = client.post("/api/v1/documents/uploads", json=UPLOAD_REQUEST)

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}


def test_create_upload_intent_does_not_treat_configuration_errors_as_client_errors(
    upload_client: tuple[TestClient, Mock],
) -> None:
    client, controller = upload_client
    controller.side_effect = ValueError("invalid storage configuration")

    with pytest.raises(ValueError, match="invalid storage configuration"):
        client.post("/api/v1/documents/uploads", json=UPLOAD_REQUEST)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/v1/documents/uploads"),
        ("post", f"/api/v1/documents/{DOCUMENT_ID}/complete"),
        ("post", f"/api/v1/documents/{DOCUMENT_ID}/download-url"),
        ("delete", f"/api/v1/documents/{DOCUMENT_ID}"),
    ],
)
def test_storage_configuration_errors_return_service_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
) -> None:
    app = create_app(AppEnvironment.TESTING)
    app.dependency_overrides[get_document_persistence] = lambda: Mock()
    app.dependency_overrides[get_processing_job_persistence] = lambda: Mock()
    monkeypatch.setattr(
        "supplylens.routes.v1.dependencies.StorageAdapter",
        Mock(side_effect=ValueError("invalid storage configuration")),
    )
    client = TestClient(app)

    response = client.request(
        method,
        path,
        json=UPLOAD_REQUEST if path.endswith("/uploads") else None,
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Object storage is unavailable."}


@pytest.fixture
def document_client(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[TestClient, dict[str, Mock]]:
    app = create_app(AppEnvironment.TESTING)
    app.dependency_overrides[get_document_persistence] = lambda: Mock()
    app.dependency_overrides[get_processing_job_persistence] = lambda: Mock()
    app.dependency_overrides[get_object_storage] = lambda: Mock()
    controllers = {
        "complete": Mock(),
        "get": Mock(),
        "download_url": Mock(),
        "delete": Mock(),
    }
    monkeypatch.setattr(
        documents, "report_upload_completed_controller", controllers["complete"]
    )
    monkeypatch.setattr(documents, "get_document_data_controller", controllers["get"])
    monkeypatch.setattr(
        documents, "get_document_url_controller", controllers["download_url"]
    )
    monkeypatch.setattr(documents, "delete_document_controller", controllers["delete"])
    return TestClient(app), controllers


def _stored_document() -> StoredDocument:
    return StoredDocument(
        id=DOCUMENT_ID,
        filename="invoice.pdf",
        size_bytes=512,
        document_type="application/pdf",
        page_count=2,
        upload_status=DocumentUploadStatus.UPLOADED,
        processing_status=DocumentProcessingStatus.PROCESSED,
        created_at=datetime(2026, 9, 30, 12, 0),
        uploaded_at=datetime(2026, 9, 30, 12, 5),
        processed_at=datetime(2026, 9, 30, 12, 10),
    )


def test_report_upload_completed_returns_mapped_document(
    document_client: tuple[TestClient, dict[str, Mock]],
) -> None:
    client, controllers = document_client
    controllers["complete"].return_value = Mock(document=_stored_document())

    response = client.post(f"/api/v1/documents/{DOCUMENT_ID}/complete")

    assert response.status_code == 200
    assert response.json() == {
        "document": {
            "id": str(DOCUMENT_ID),
            "filename": "invoice.pdf",
            "size_bytes": 512,
            "document_type": "application/pdf",
            "page_count": 2,
            "upload_status": "UPLOADED",
            "processing_status": "PROCESSED",
            "created_at": "2026-09-30T12:00:00",
            "uploaded_at": "2026-09-30T12:05:00",
            "processed_at": "2026-09-30T12:10:00",
        }
    }
    controllers["complete"].assert_called_once()


def test_document_openapi_lists_storage_failures_only_for_storage_operations() -> None:
    paths = create_app(AppEnvironment.TESTING).openapi()["paths"]

    assert "503" not in paths["/api/v1/documents/{id}"]["get"]["responses"]
    for path, method in (
        ("/api/v1/documents/uploads", "post"),
        ("/api/v1/documents/{id}/complete", "post"),
        ("/api/v1/documents/{id}/download-url", "post"),
        ("/api/v1/documents/{id}", "delete"),
    ):
        assert "503" in paths[path][method]["responses"]


def test_to_document_schema_copies_public_fields() -> None:
    stored = _stored_document()

    assert to_document_schema(stored).model_dump() == {
        "id": stored.id,
        "filename": stored.filename,
        "size_bytes": stored.size_bytes,
        "document_type": stored.document_type,
        "page_count": stored.page_count,
        "upload_status": stored.upload_status,
        "processing_status": stored.processing_status,
        "created_at": stored.created_at,
        "uploaded_at": stored.uploaded_at,
        "processed_at": stored.processed_at,
    }


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (DocumentNotFoundError("missing"), 404, "Document not found."),
        (
            StoreDocumentInvalidSizeError("wrong size"),
            422,
            "Uploaded document size does not match the declared size.",
        ),
        (
            DocumentInvalidContentTypeError("wrong type"),
            415,
            "Uploaded document must be a PDF.",
        ),
        (
            StorageUnavailableError("storage unavailable"),
            503,
            "Object storage is unavailable.",
        ),
        (InvalidJobProcessingID("wrong ID"), 500, "Invalid database id"),
    ],
)
def test_report_upload_completed_maps_controller_errors(
    document_client: tuple[TestClient, dict[str, Mock]],
    error: Exception,
    expected_status: int,
    expected_detail: str,
) -> None:
    client, controllers = document_client
    controllers["complete"].side_effect = error

    response = client.post(f"/api/v1/documents/{DOCUMENT_ID}/complete")

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}


def test_get_document_data_returns_mapped_document(
    document_client: tuple[TestClient, dict[str, Mock]],
) -> None:
    client, controllers = document_client
    controllers["get"].return_value = Mock(document=_stored_document())

    response = client.get(f"/api/v1/documents/{DOCUMENT_ID}")

    assert response.status_code == 200
    assert response.json()["document"]["filename"] == "invoice.pdf"
    assert response.json()["document"]["uploaded_at"] == "2026-09-30T12:05:00"


def test_get_document_data_maps_missing_document(
    document_client: tuple[TestClient, dict[str, Mock]],
) -> None:
    client, controllers = document_client
    controllers["get"].side_effect = DocumentNotFoundError("missing")

    response = client.get(f"/api/v1/documents/{DOCUMENT_ID}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found."}


def test_get_download_url_returns_url_and_expiration(
    document_client: tuple[TestClient, dict[str, Mock]],
) -> None:
    client, controllers = document_client
    controllers["download_url"].return_value = GetDocumentURLCommandResponse(
        id=DOCUMENT_ID,
        url="https://storage.invalid/download",
        expires_in_seconds=600,
    )

    response = client.post(f"/api/v1/documents/{DOCUMENT_ID}/download-url")

    assert response.status_code == 200
    assert response.json() == {
        "id": str(DOCUMENT_ID),
        "url": "https://storage.invalid/download",
        "expires_in_seconds": 600,
    }


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (DocumentNotFoundError("missing"), 404, "Document not found."),
        (
            DocumentNotUploadedError("not uploaded"),
            409,
            "Document has not been uploaded.",
        ),
        (
            StorageUnavailableError("storage unavailable"),
            503,
            "Object storage is unavailable.",
        ),
    ],
)
def test_get_download_url_maps_controller_errors(
    document_client: tuple[TestClient, dict[str, Mock]],
    error: Exception,
    expected_status: int,
    expected_detail: str,
) -> None:
    client, controllers = document_client
    controllers["download_url"].side_effect = error

    response = client.post(f"/api/v1/documents/{DOCUMENT_ID}/download-url")

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}


def test_delete_document_returns_no_content(
    document_client: tuple[TestClient, dict[str, Mock]],
) -> None:
    client, controllers = document_client

    response = client.delete(f"/api/v1/documents/{DOCUMENT_ID}")

    assert response.status_code == 204
    assert response.content == b""
    controllers["delete"].assert_called_once()


def test_delete_document_maps_storage_unavailable(
    document_client: tuple[TestClient, dict[str, Mock]],
) -> None:
    client, controllers = document_client
    controllers["delete"].side_effect = StorageUnavailableError("offline")

    response = client.delete(f"/api/v1/documents/{DOCUMENT_ID}")

    assert response.status_code == 503
    assert response.json() == {"detail": "Object storage is unavailable."}


@pytest.fixture
def completion_transaction_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[TestClient, Engine]]:
    # Exercise request transaction handling without external database/storage services.
    # SQLite does not exercise PostgreSQL's row-lock concurrency guarantees.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, autoflush=False)
        with factory() as session, session.begin():
            session.add(
                ModelDocument(id=DOCUMENT_ID, filename="synthetic.pdf", size_bytes=512)
            )
        monkeypatch.setattr(database, "SessionLocal", factory)
        app = create_app(AppEnvironment.TESTING)
        storage = Mock(spec=ObjectStorage)
        storage.head_object.return_value = ObjectInfo(
            f"documents/{DOCUMENT_ID}/original.pdf", 512, "application/pdf", None
        )
        app.dependency_overrides[get_object_storage] = lambda: storage
        with TestClient(app) as client:
            yield client, engine
    finally:
        engine.dispose()


def test_completion_commits_document_and_one_job_on_repeated_requests(
    completion_transaction_client: tuple[TestClient, Engine],
) -> None:
    client, engine = completion_transaction_client

    first = client.post(f"/api/v1/documents/{DOCUMENT_ID}/complete")
    second = client.post(f"/api/v1/documents/{DOCUMENT_ID}/complete")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    with Session(engine) as session:
        document = session.get(ModelDocument, DOCUMENT_ID)
        assert document is not None
        assert document.upload_status is DocumentUploadStatus.UPLOADED
        assert document.uploaded_at is not None
        job = session.scalar(select(ModelProcessingJob))
        assert job is not None
        assert job.document_id == DOCUMENT_ID
        assert session.scalar(select(func.count()).select_from(ModelProcessingJob)) == 1


@pytest.mark.parametrize("job_id", [0, -1])
def test_completion_invalid_job_id_rolls_back_document_and_job(
    completion_transaction_client: tuple[TestClient, Engine],
    monkeypatch: pytest.MonkeyPatch,
    job_id: int,
) -> None:
    client, engine = completion_transaction_client
    original_enqueue = ProcessingJobPersistenceAdapter.enqueue_new_job

    def enqueue_with_invalid_id(
        adapter: ProcessingJobPersistenceAdapter, document_uuid: UUID
    ) -> int:
        original_enqueue(adapter, document_uuid)
        return job_id

    monkeypatch.setattr(
        ProcessingJobPersistenceAdapter,
        "enqueue_new_job",
        enqueue_with_invalid_id,
    )

    response = client.post(f"/api/v1/documents/{DOCUMENT_ID}/complete")

    assert response.status_code == 500
    assert response.json() == {"detail": "Invalid database id"}
    with Session(engine) as session:
        document = session.get(ModelDocument, DOCUMENT_ID)
        assert document is not None
        assert document.upload_status is DocumentUploadStatus.PENDING
        assert document.uploaded_at is None
        assert session.scalar(select(func.count()).select_from(ModelProcessingJob)) == 0


def _stored_object(size_bytes: int, content_type: str) -> ObjectInfo:
    return ObjectInfo(
        f"documents/{DOCUMENT_ID}/original.pdf",
        size_bytes,
        content_type,
        None,
    )


def _completion_storage(
    client: TestClient,
    *,
    size_bytes: int,
    content_type: str,
    delete_error: Exception | None = None,
) -> Mock:
    storage = Mock(spec=ObjectStorage)
    storage.head_object.return_value = _stored_object(size_bytes, content_type)
    if delete_error is not None:
        storage.delete_object.side_effect = delete_error
    client.app.dependency_overrides[get_object_storage] = lambda: storage
    return storage


def _assert_document_failed(engine: Engine) -> None:
    with Session(engine) as session:
        document = session.get(ModelDocument, DOCUMENT_ID)
        assert document is not None
        assert document.upload_status is DocumentUploadStatus.FAILED
        assert document.uploaded_at is None
        assert session.scalar(select(func.count()).select_from(ModelProcessingJob)) == 0


@pytest.mark.parametrize(
    ("size_bytes", "content_type", "expected_status", "expected_detail"),
    [
        (
            511,
            "application/pdf",
            422,
            "Uploaded document size does not match the declared size.",
        ),
        (
            512,
            "application/octet-stream",
            415,
            "Uploaded document must be a PDF.",
        ),
    ],
)
def test_completion_mismatch_persists_failed_status(
    completion_transaction_client: tuple[TestClient, Engine],
    size_bytes: int,
    content_type: str,
    expected_status: int,
    expected_detail: str,
) -> None:
    client, engine = completion_transaction_client
    storage = _completion_storage(
        client, size_bytes=size_bytes, content_type=content_type
    )

    response = client.post(f"/api/v1/documents/{DOCUMENT_ID}/complete")

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}
    storage.delete_object.assert_called_once_with(
        f"documents/{DOCUMENT_ID}/original.pdf"
    )
    _assert_document_failed(engine)


@pytest.mark.parametrize(
    ("size_bytes", "content_type"),
    [
        (511, "application/pdf"),
        (512, "application/octet-stream"),
    ],
)
def test_completion_mismatch_persists_failed_status_when_deletion_fails(
    completion_transaction_client: tuple[TestClient, Engine],
    size_bytes: int,
    content_type: str,
) -> None:
    client, engine = completion_transaction_client
    _completion_storage(
        client,
        size_bytes=size_bytes,
        content_type=content_type,
        delete_error=StorageUnavailableError("synthetic storage outage"),
    )

    response = client.post(f"/api/v1/documents/{DOCUMENT_ID}/complete")

    assert response.status_code == 503
    assert response.json() == {"detail": "Object storage is unavailable."}
    _assert_document_failed(engine)


def test_completion_enqueue_failure_rolls_back_document_and_job(
    completion_transaction_client: tuple[TestClient, Engine],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, engine = completion_transaction_client
    original_enqueue = ProcessingJobPersistenceAdapter.enqueue_new_job

    def fail_after_enqueue(
        adapter: ProcessingJobPersistenceAdapter, document_uuid: UUID
    ) -> int:
        original_enqueue(adapter, document_uuid)
        raise RuntimeError("synthetic enqueue failure")

    monkeypatch.setattr(
        ProcessingJobPersistenceAdapter, "enqueue_new_job", fail_after_enqueue
    )

    with pytest.raises(RuntimeError, match="synthetic enqueue failure"):
        client.post(f"/api/v1/documents/{DOCUMENT_ID}/complete")

    with Session(engine) as session:
        document = session.get(ModelDocument, DOCUMENT_ID)
        assert document is not None
        assert document.upload_status is DocumentUploadStatus.PENDING
        assert document.uploaded_at is None
        assert session.scalar(select(func.count()).select_from(ModelProcessingJob)) == 0


def test_completion_passes_the_same_session_to_document_and_job_adapters(
    completion_transaction_client: tuple[TestClient, Engine],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[Session] = []
    original_document_init = DocumentPersistenceAdapter.__init__
    original_job_init = ProcessingJobPersistenceAdapter.__init__

    def document_init(self: DocumentPersistenceAdapter, session: Session) -> None:
        seen.append(session)
        original_document_init(self, session)

    def job_init(self: ProcessingJobPersistenceAdapter, session: Session) -> None:
        seen.append(session)
        original_job_init(self, session)

    monkeypatch.setattr(DocumentPersistenceAdapter, "__init__", document_init)
    monkeypatch.setattr(ProcessingJobPersistenceAdapter, "__init__", job_init)
    client, _engine = completion_transaction_client

    response = client.post(f"/api/v1/documents/{DOCUMENT_ID}/complete")

    assert response.status_code == 200
    assert len(seen) == 2
    assert seen[0] is seen[1]


def _fail_session_commit(self: SessionTransaction, _to_root: bool = False) -> None:
    raise RuntimeError("synthetic commit failure")


def test_completion_commit_failure_is_not_a_successful_response(
    completion_transaction_client: tuple[TestClient, Engine],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, engine = completion_transaction_client
    failing_client = TestClient(client.app, raise_server_exceptions=False)
    monkeypatch.setattr(SessionTransaction, "commit", _fail_session_commit)

    response = failing_client.post(f"/api/v1/documents/{DOCUMENT_ID}/complete")

    assert response.status_code not in {200, 415, 422}
    with Session(engine) as session:
        document = session.get(ModelDocument, DOCUMENT_ID)
        assert document is not None
        assert document.upload_status is DocumentUploadStatus.PENDING


def test_completion_commit_failure_after_mismatch_is_not_a_mismatch_response(
    completion_transaction_client: tuple[TestClient, Engine],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, engine = completion_transaction_client
    _completion_storage(client, size_bytes=511, content_type="application/pdf")
    failing_client = TestClient(client.app, raise_server_exceptions=False)
    monkeypatch.setattr(SessionTransaction, "commit", _fail_session_commit)

    response = failing_client.post(f"/api/v1/documents/{DOCUMENT_ID}/complete")

    assert response.status_code not in {200, 415, 422}
    with Session(engine) as session:
        document = session.get(ModelDocument, DOCUMENT_ID)
        assert document is not None
        assert document.upload_status is DocumentUploadStatus.PENDING


def test_storage_construction_failure_does_not_run_the_controller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    closed: list[Session] = []
    rolled_back: list[Session] = []
    original_close = Session.close

    def close(self: Session) -> None:
        closed.append(self)
        original_close(self)

    def record_rollback(session: Session) -> None:
        rolled_back.append(session)

    event.listen(Session, "after_rollback", record_rollback)
    try:
        Base.metadata.create_all(engine)
        monkeypatch.setattr(
            database,
            "SessionLocal",
            sessionmaker(bind=engine, autoflush=False),
        )
        monkeypatch.setattr(Session, "close", close)
        monkeypatch.setattr(
            "supplylens.routes.v1.dependencies.StorageAdapter",
            Mock(side_effect=ValueError("invalid storage configuration")),
        )
        controller = Mock()
        monkeypatch.setattr(documents, "report_upload_completed_controller", controller)
        client = TestClient(create_app(AppEnvironment.TESTING))

        response = client.post(f"/api/v1/documents/{DOCUMENT_ID}/complete")
    finally:
        event.remove(Session, "after_rollback", record_rollback)
        engine.dispose()

    assert response.status_code == 503
    assert response.json() == {"detail": "Object storage is unavailable."}
    controller.assert_not_called()
    assert rolled_back
    assert closed
    assert any(session in closed for session in rolled_back)
