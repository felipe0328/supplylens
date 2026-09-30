# SupplyLens — Document Upload, Object Storage, and Processing Architecture

**Status:** Proposed MVP architecture
**Last reviewed:** 2026-09-29
**Scope:** React frontend → direct object-storage upload → FastAPI metadata/lifecycle API → PostgreSQL → asynchronous PDF processing → structured data + document chunks/embeddings.

---

## 1. Purpose

SupplyLens receives supplier documents, primarily PDFs such as invoices, bills, and purchase documents. The application must:

1. Accept a document from the React frontend or another client/listener.
2. Store the original PDF safely without using PostgreSQL as blob storage.
3. Persist metadata and lifecycle state in PostgreSQL.
4. Process the PDF asynchronously after upload.
5. Extract structured business information into relational tables.
6. Extract searchable text chunks and, later, embeddings for semantic retrieval.
7. Preserve the original PDF so it can be reprocessed when parsers improve.
8. Keep the MVP deployable at **$0/month while usage remains inside free tiers**.
9. Make local development behave as similarly as possible to production.

The key architectural decision is that **PostgreSQL stores metadata and extracted data; object storage stores the original binary document**.

---

## 2. High-level architecture

### Production

```text
┌───────────────┐
│ React frontend│
└───────┬───────┘
        │
        │ 1. POST /api/v1/documents/uploads
        ▼
┌───────────────┐
│    FastAPI    │
│               │
│ - authorize   │
│ - create UUID │
│ - DB metadata │
│ - sign PUT URL│
└───┬───────────┘
    │
    │ 2. returns document_id + presigned PUT URL
    ▼
┌───────────────┐
│ React frontend│
└───────┬───────┘
        │
        │ 3. PUT PDF directly
        ▼
┌────────────────────────┐
│ Cloudflare R2           │
│ private object storage  │
└────────────────────────┘
        ▲
        │
        │ 4. HEAD / GET using server credentials
┌───────┴───────┐
│    FastAPI    │
└───────┬───────┘
        │
        │ 5. mark upload complete + queue work
        ▼
┌──────────────────┐
│ PostgreSQL       │
│                  │
│ metadata         │
│ processing state │
│ extracted data   │
│ pgvector chunks  │
└────────▲─────────┘
         │
         │
┌────────┴─────────┐
│ Python worker    │
│                  │
│ downloads PDF    │
│ validates PDF    │
│ extracts text    │
│ normalizes data  │
│ creates chunks   │
│ creates embedding│
└────────┬─────────┘
         │
         └────────────── GET original PDF ──────────────► R2
```

### Local development

The same S3-compatible interface is used, but Cloudflare R2 is replaced by local MinIO:

```text
Production                          Development

React                               React
  │                                   │
  │ presigned PUT                     │ presigned PUT
  ▼                                   ▼
Cloudflare R2                       MinIO
  ▲                                   ▲
  │ S3-compatible API                 │ S3-compatible API
  │                                   │
FastAPI                             FastAPI
  │                                   │
  ▼                                   ▼
PostgreSQL + pgvector              PostgreSQL + pgvector
```

Application/domain code must not depend directly on R2 or MinIO. It depends on an **object-storage abstraction backed by an S3-compatible implementation**.

---

## 3. Why the PDF should not be stored in PostgreSQL

Do **not** store the PDF itself in a `bytea` column for this project.

PostgreSQL should contain:

- document identity;
- object-storage location;
- metadata;
- checksums;
- upload/processing state;
- extraction results;
- normalized business entities;
- text chunks;
- embeddings.

Object storage should contain:

- the immutable original PDF;
- optionally, later, derived artifacts such as an OCR-normalized PDF or extracted images.

This gives us:

- smaller database backups;
- simpler file streaming;
- direct browser uploads;
- less API bandwidth;
- lower memory pressure in FastAPI;
- independent storage scaling;
- ability to reprocess the original document;
- portability between S3-compatible providers.

---

## 4. Production object storage: Cloudflare R2

### 4.1 Choice

Use **Cloudflare R2 Standard storage** for production.

Reasons:

- S3-compatible API;
- supported by `boto3`;
- presigned `PUT` and `GET` URLs;
- browser can upload directly to R2;
- no need to proxy PDF bytes through FastAPI;
- suitable free tier for the SupplyLens MVP;
- free internet egress for standard R2 usage.

### 4.2 Current free-tier budget

As verified on 2026-09-29, R2 Standard currently includes per month:

- **10 GB-month of storage**
- **1,000,000 Class A operations**
- **10,000,000 Class B operations**
- **free egress**

The free tier is **not a hard spending cap**. SupplyLens should therefore impose its own quota before approaching the provider limit.

Recommended MVP configuration:

```env
STORAGE_SOFT_LIMIT_BYTES=7516192768     # 7 GiB warning
STORAGE_HARD_LIMIT_BYTES=8589934592     # 8 GiB application hard-stop
MAX_DOCUMENT_SIZE_BYTES=26214400        # 25 MiB per PDF
```

Keeping the application below approximately 8 GiB creates room for temporary/derived objects and prevents normal operation from getting too close to the 10 GB-month storage allowance.

> Pricing can change. Re-check the Cloudflare R2 pricing page before production launch.

### 4.3 Bucket

Production bucket:

```text
supplylens-documents
```

The bucket must remain **private**.

Do not expose it as a public bucket and do not store public object URLs in PostgreSQL.

### 4.4 Object keys

Do not use the user-provided filename as the object key.

Use the application-generated `document_id`:

```text
documents/{document_id}/original.pdf
```

Example:

```text
documents/f7e76bd8-4d62-49bb-ae18-b24d6879cc99/original.pdf
```

Future derived artifacts can live under the same prefix:

```text
documents/{document_id}/original.pdf
documents/{document_id}/derived/ocr.pdf
documents/{document_id}/derived/pages/0001.png
```

For a future multi-tenant version:

```text
tenants/{tenant_id}/documents/{document_id}/original.pdf
```

The database, not the object key, is the authoritative source for the original filename.

---

## 5. Local object storage: MinIO

### 5.1 Why MinIO

For local development, run **MinIO** in Docker.

MinIO provides an S3-compatible API, which means the same `boto3` storage adapter can be used locally and in production.

This gives us a real E2E upload path:

```text
Browser → presigned URL → object storage
```

instead of replacing storage with a local filesystem mock.

### 5.2 Local ports

Recommended:

```text
MinIO S3 API:       http://localhost:9000
MinIO Web Console:  http://localhost:9001
```

### 5.3 Docker Compose infrastructure

Example `compose.yaml`:

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg17
    environment:
      POSTGRES_DB: supplylens
      POSTGRES_USER: supplylens
      POSTGRES_PASSWORD: supplylens
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U supplylens -d supplylens"]
      interval: 5s
      timeout: 5s
      retries: 10

  minio:
    image: quay.io/minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: supplylens
      MINIO_ROOT_PASSWORD: supplylens-dev-password
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data

volumes:
  postgres_data:
  minio_data:
```

For reproducible CI, replace `latest` with a tested/pinned MinIO release once the initial development environment is working.

Start infrastructure:

```bash
docker compose up -d postgres minio
```

### 5.4 Local bucket bootstrap

Create the same logical bucket name locally:

```text
supplylens-documents
```

A small Python bootstrap script is preferable because it can create the bucket and configure browser CORS using the same S3 API used by the application.

Example:

```python
# scripts/init_storage.py

import boto3
from botocore.exceptions import ClientError

BUCKET = "supplylens-documents"

s3 = boto3.client(
    "s3",
    endpoint_url="http://localhost:9000",
    aws_access_key_id="supplylens",
    aws_secret_access_key="supplylens-dev-password",
    region_name="us-east-1",
)

try:
    s3.head_bucket(Bucket=BUCKET)
except ClientError:
    s3.create_bucket(Bucket=BUCKET)

s3.put_bucket_cors(
    Bucket=BUCKET,
    CORSConfiguration={
        "CORSRules": [
            {
                "AllowedOrigins": ["http://localhost:5173"],
                "AllowedMethods": ["GET", "PUT", "HEAD"],
                "AllowedHeaders": ["*"],
                "ExposeHeaders": ["ETag"],
                "MaxAgeSeconds": 3600,
            }
        ]
    },
)

print(f"Bucket {BUCKET!r} is ready")
```

Run:

```bash
python scripts/init_storage.py
```

If the frontend runs on a different origin, update `AllowedOrigins`.

---

## 6. Important local-development detail: internal vs public endpoint

This is easy to get wrong.

If FastAPI itself runs in Docker, it can reach MinIO with:

```text
http://minio:9000
```

The browser cannot resolve the Docker hostname `minio`.

The browser must use:

```text
http://localhost:9000
```

A presigned URL contains a cryptographic signature tied to the request. Do not generate a URL with `minio:9000` and then replace the hostname with `localhost:9000`; that can invalidate the signature.

Use **two endpoint settings** locally:

```env
S3_INTERNAL_ENDPOINT=http://minio:9000
S3_PUBLIC_ENDPOINT=http://localhost:9000
```

Use:

- `S3_INTERNAL_ENDPOINT` for FastAPI/worker operations such as `HEAD`, `GET`, and `DELETE`;
- `S3_PUBLIC_ENDPOINT` when generating browser-facing presigned URLs.

If FastAPI runs directly on the host instead of Docker, both can be:

```env
S3_INTERNAL_ENDPOINT=http://localhost:9000
S3_PUBLIC_ENDPOINT=http://localhost:9000
```

In production both settings normally point to the Cloudflare R2 S3 endpoint.

---

## 7. Environment configuration

### 7.1 Local `.env`

```env
APP_ENV=development

DATABASE_URL=postgresql+psycopg://supplylens:supplylens@localhost:5432/supplylens

S3_PROVIDER=minio
S3_BUCKET=supplylens-documents
S3_REGION=us-east-1

S3_INTERNAL_ENDPOINT=http://localhost:9000
S3_PUBLIC_ENDPOINT=http://localhost:9000

S3_ACCESS_KEY_ID=supplylens
S3_SECRET_ACCESS_KEY=supplylens-dev-password

S3_UPLOAD_URL_TTL_SECONDS=900

MAX_DOCUMENT_SIZE_BYTES=26214400
STORAGE_HARD_LIMIT_BYTES=8589934592
```

If API and worker are Dockerized:

```env
S3_INTERNAL_ENDPOINT=http://minio:9000
S3_PUBLIC_ENDPOINT=http://localhost:9000
```

### 7.2 Production `.env`

```env
APP_ENV=production

DATABASE_URL=...

S3_PROVIDER=r2
S3_BUCKET=supplylens-documents
S3_REGION=auto

S3_INTERNAL_ENDPOINT=https://<CLOUDFLARE_ACCOUNT_ID>.r2.cloudflarestorage.com
S3_PUBLIC_ENDPOINT=https://<CLOUDFLARE_ACCOUNT_ID>.r2.cloudflarestorage.com

S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...

S3_UPLOAD_URL_TTL_SECONDS=900

MAX_DOCUMENT_SIZE_BYTES=26214400
STORAGE_HARD_LIMIT_BYTES=8589934592
```

Never expose `S3_ACCESS_KEY_ID` or `S3_SECRET_ACCESS_KEY` to React.

Only the backend signs URLs.

---

## 8. Storage abstraction

Business/application code should not import R2-specific or MinIO-specific SDKs.

Define an interface:

```python
from dataclasses import dataclass
from typing import BinaryIO, Protocol


@dataclass(frozen=True)
class ObjectInfo:
    key: str
    size_bytes: int
    content_type: str | None
    etag: str | None


@dataclass(frozen=True)
class PresignedUpload:
    url: str
    method: str
    headers: dict[str, str]
    expires_in_seconds: int


class ObjectStorage(Protocol):
    def create_upload_url(
        self,
        *,
        object_key: str,
        content_type: str,
        expires_in_seconds: int,
    ) -> PresignedUpload:
        ...

    def head_object(self, *, object_key: str) -> ObjectInfo:
        ...

    def download_fileobj(
        self,
        *,
        object_key: str,
        target: BinaryIO,
    ) -> None:
        ...

    def create_download_url(
        self,
        *,
        object_key: str,
        expires_in_seconds: int,
    ) -> str:
        ...

    def delete_object(self, *, object_key: str) -> None:
        ...
```

Implementation:

```text
ObjectStorage
     ▲
     │
S3ObjectStorage
     │
     ├── MinIO locally
     └── Cloudflare R2 in production
```

The only environment-specific behavior should be configuration.

### 8.1 Two S3 clients locally

It is useful for `S3ObjectStorage` to contain two boto3 clients:

```text
internal_client
    Used by FastAPI and workers to call storage.

signing_client
    Used only to generate browser-facing presigned URLs.
```

The clients can use different endpoint URLs locally but the same credentials and bucket.

Pseudo-implementation:

```python
import boto3
from botocore.config import Config


class S3ObjectStorage:
    def __init__(self, settings):
        common = {
            "aws_access_key_id": settings.s3_access_key_id,
            "aws_secret_access_key": settings.s3_secret_access_key,
            "region_name": settings.s3_region,
            "config": Config(signature_version="s3v4"),
        }

        self._bucket = settings.s3_bucket

        self._internal = boto3.client(
            "s3",
            endpoint_url=settings.s3_internal_endpoint,
            **common,
        )

        self._signer = boto3.client(
            "s3",
            endpoint_url=settings.s3_public_endpoint,
            **common,
        )

    def create_upload_url(
        self,
        *,
        object_key: str,
        content_type: str,
        expires_in_seconds: int,
    ) -> PresignedUpload:
        url = self._signer.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": self._bucket,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in_seconds,
        )

        return PresignedUpload(
            url=url,
            method="PUT",
            headers={"Content-Type": content_type},
            expires_in_seconds=expires_in_seconds,
        )
```

The React client must send the headers returned by FastAPI exactly as specified.

---

## 9. API design

### 9.1 Do not use `GET /document/upload`

The upload initiation endpoint changes application state by creating a document/upload intent.

Use:

```http
POST /api/v1/documents/uploads
```

Plural nouns are used consistently.

### 9.2 Step 1 — create upload intent

#### Request

```http
POST /api/v1/documents/uploads
Content-Type: application/json
```

```json
{
  "filename": "supplier-invoice-2026-09.pdf",
  "content_type": "application/pdf",
  "size_bytes": 845221
}
```

Optional future field:

```json
{
  "sha256": "..."
}
```

Do not require SHA-256 for the first implementation. The worker can calculate the authoritative checksum after downloading the uploaded file.

#### Backend validation

Before creating the upload:

1. Authenticate/authorize the caller when authentication exists.
2. Reject empty filename.
3. Require declared `content_type` to be `application/pdf`.
4. Require `size_bytes > 0`.
5. Reject declared size larger than `MAX_DOCUMENT_SIZE_BYTES`.
6. Check the application's storage quota.
7. Generate `document_id` as UUID.
8. Construct the object key from `document_id`.
9. Insert the `documents` row in `PENDING` state.
10. Generate a short-lived presigned `PUT` URL.
11. Return the upload information.

Do not trust the filename extension as proof that the content is a PDF.

#### Response

```http
201 Created
```

```json
{
  "document_id": "f7e76bd8-4d62-49bb-ae18-b24d6879cc99",
  "upload": {
    "url": "http://localhost:9000/...",
    "method": "PUT",
    "headers": {
      "Content-Type": "application/pdf"
    },
    "expires_in_seconds": 900
  }
}
```

The presigned URL is a temporary bearer capability. Do not log the complete URL in application logs.

### 9.3 Step 2 — frontend uploads directly to object storage

React sends the PDF bytes directly to MinIO/R2:

```typescript
const uploadResponse = await fetch(upload.url, {
  method: upload.method,
  headers: upload.headers,
  body: file,
});

if (!uploadResponse.ok) {
  throw new Error(`Upload failed: ${uploadResponse.status}`);
}
```

FastAPI does not receive the file bytes.

This avoids:

```text
Browser → FastAPI → R2
```

and instead uses:

```text
Browser → R2
```

The API remains responsible for authorization, object naming, lifecycle state, validation, and processing orchestration.

### 9.4 Step 3 — client reports completion

After the object-storage `PUT` succeeds:

```http
POST /api/v1/documents/{document_id}/complete
```

Example:

```http
POST /api/v1/documents/f7e76bd8-4d62-49bb-ae18-b24d6879cc99/complete
```

Body can initially be empty:

```json
{}
```

Optionally, the client can send the ETag returned by object storage for observability:

```json
{
  "client_etag": "\"...\""
}
```

Do not trust this as proof of upload.

### 9.5 Backend completion verification

The API performs an authoritative `HEAD` operation against MinIO/R2:

```python
result = storage.head_object(object_key=document.object_key)
```

Verify:

- object exists;
- actual size is greater than zero;
- actual size is at or below `MAX_DOCUMENT_SIZE_BYTES`;
- actual size equals the initially declared size;
- object key belongs to this document;
- expected MIME metadata is present where applicable.

If the object is oversized or invalid, mark the upload as failed and delete it.

Important: `Content-Type` is metadata supplied during upload. It is **not sufficient to prove the bytes are a valid PDF**. Actual content validation occurs in the worker.

If verification succeeds:

```text
upload_status = UPLOADED
processing_status = PENDING
uploaded_at = now()
actual_size_bytes = HEAD.ContentLength
storage_etag = HEAD.ETag
```

Then make the document available to the processing worker.

### 9.6 Completion must be idempotent

Calling:

```http
POST /api/v1/documents/{id}/complete
```

multiple times should not create duplicate processing jobs.

If the document is already `UPLOADED`, `PROCESSING`, or `READY`, return the current document state.

Recommended response:

```json
{
  "id": "f7e76bd8-4d62-49bb-ae18-b24d6879cc99",
  "upload_status": "UPLOADED",
  "processing_status": "PENDING"
}
```

### 9.7 Get document state

```http
GET /api/v1/documents/{document_id}
```

Example response:

```json
{
  "id": "f7e76bd8-4d62-49bb-ae18-b24d6879cc99",
  "original_filename": "supplier-invoice-2026-09.pdf",
  "size_bytes": 845221,
  "upload_status": "UPLOADED",
  "processing_status": "PROCESSING",
  "document_type": null,
  "page_count": null,
  "created_at": "2026-09-29T23:00:00Z",
  "uploaded_at": "2026-09-29T23:00:08Z",
  "processed_at": null
}
```

The frontend can poll this endpoint initially.

Later, if desired, processing progress can be delivered with SSE/WebSocket, but that is unnecessary for the first version.

### 9.8 Generate a download/view URL

Keep the bucket private.

Use:

```http
POST /api/v1/documents/{document_id}/download-url
```

Response:

```json
{
  "url": "https://...presigned...",
  "expires_in_seconds": 300
}
```

Use short expiry values for read URLs.

### 9.9 Optional retry endpoint

If the upload URL expires before the upload starts:

```http
POST /api/v1/documents/{document_id}/upload-url
```

Only allow this while the document is still in an uploadable state.

It returns a new presigned URL for the same object key.

This endpoint is optional for the first implementation.

---

## 10. Complete upload sequence

```text
React                       FastAPI                    PostgreSQL                  R2 / MinIO
  │                            │                           │                           │
  │ POST /documents/uploads    │                           │                           │
  ├───────────────────────────►│                           │                           │
  │                            │ create document UUID      │                           │
  │                            │ INSERT PENDING            │                           │
  │                            ├──────────────────────────►│                           │
  │                            │                           │                           │
  │                            │ generate presigned PUT URL                            │
  │                            │───────────────────────────────────────────────────────┐
  │                            │                                                       │
  │ document_id + upload URL   │◄──────────────────────────────────────────────────────┘
  │◄───────────────────────────┤
  │                            │
  │ PUT PDF directly
  ├──────────────────────────────────────────────────────────────────────────────────►│
  │                                                                                   │
  │ 200 OK / ETag                                                                     │
  │◄──────────────────────────────────────────────────────────────────────────────────┤
  │                            │                                                       │
  │ POST /documents/{id}/complete                                                     │
  ├───────────────────────────►│                                                       │
  │                            │ HEAD object                                           │
  │                            ├──────────────────────────────────────────────────────►│
  │                            │ size/type/etag                                        │
  │                            │◄──────────────────────────────────────────────────────┤
  │                            │                                                       │
  │                            │ UPDATE UPLOADED/PENDING │                              │
  │                            ├──────────────────────────►│                            │
  │                            │                           │                            │
  │ status                     │                           │                            │
  │◄───────────────────────────┤                           │                            │
```

---

## 11. Database design

### 11.1 `documents`

`documents` represents the source document and its lifecycle.

Recommended schema:

```sql
CREATE TYPE document_upload_status AS ENUM (
    'PENDING',
    'UPLOADED',
    'FAILED'
);

CREATE TYPE document_processing_status AS ENUM (
    'NOT_STARTED',
    'PENDING',
    'PROCESSING',
    'READY',
    'FAILED'
);

CREATE TABLE documents (
    id UUID PRIMARY KEY,

    original_filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    declared_size_bytes BIGINT NOT NULL,
    actual_size_bytes BIGINT,

    storage_provider TEXT NOT NULL,
    storage_bucket TEXT NOT NULL,
    object_key TEXT NOT NULL UNIQUE,
    storage_etag TEXT,

    sha256 CHAR(64),

    upload_status document_upload_status NOT NULL DEFAULT 'PENDING',
    processing_status document_processing_status NOT NULL DEFAULT 'NOT_STARTED',

    document_type TEXT,
    page_count INTEGER,

    parser_version TEXT,
    processing_error TEXT,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    uploaded_by UUID,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    uploaded_at TIMESTAMPTZ,
    processing_started_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,

    CHECK (declared_size_bytes > 0),
    CHECK (actual_size_bytes IS NULL OR actual_size_bytes > 0)
);

CREATE INDEX idx_documents_upload_status
    ON documents(upload_status);

CREATE INDEX idx_documents_processing_status
    ON documents(processing_status);

CREATE INDEX idx_documents_sha256
    ON documents(sha256)
    WHERE sha256 IS NOT NULL;
```

`uploaded_by` should reference the users table when authentication/user management is introduced.

### 11.2 Why both declared and actual size

The React client declares `size_bytes` before upload.

That is useful for:

- immediate client validation;
- refusing obviously oversized files;
- quota calculation.

It is not authoritative.

After direct upload, FastAPI gets the actual object size using `HEAD` and saves it in `actual_size_bytes`.

A mismatch should fail completion.

### 11.3 Why store bucket + object key instead of URL

Store:

```text
storage_provider = "r2"
storage_bucket   = "supplylens-documents"
object_key       = "documents/<uuid>/original.pdf"
```

Do not store:

```text
https://....r2.cloudflarestorage.com/...?...signature...
```

Presigned URLs expire and are credentials/capabilities, not persistent document identity.

This also allows:

```text
MinIO → R2
R2 → S3
```

without changing business entities.

### 11.4 Checksum

`sha256` is used for:

- integrity tracking;
- duplicate detection;
- reproducible processing;
- identifying documents independent of filename.

Because the backend does not receive the bytes during direct upload, the initial `sha256` can be `NULL`.

The processing worker should compute it while reading the original PDF:

```python
sha256 = hashlib.sha256()
while chunk := file.read(1024 * 1024):
    sha256.update(chunk)
```

Then save:

```text
documents.sha256
```

Do not automatically reject duplicates until the desired product behavior is defined. A supplier may legitimately send the same document more than once.

At first, duplicate detection can simply generate a warning.

---

## 12. Document processing data

Do not put extracted business data directly into `documents`.

The document is a source artifact. Extraction is a separate concern.

Recommended conceptual model:

```text
documents
   │
   ├──── document_processing_runs
   │
   ├──── document_extractions
   │
   ├──── document_chunks
   │
   └──── normalized business entities
             │
             ├── suppliers
             ├── purchases/invoices
             └── purchase_items
```

### 12.1 `document_processing_runs`

Keeping processing runs separately makes parser evolution observable.

```sql
CREATE TABLE document_processing_runs (
    id UUID PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES documents(id),

    parser_version TEXT NOT NULL,
    status TEXT NOT NULL,

    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,

    error_code TEXT,
    error_message TEXT,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_processing_runs_document_id
    ON document_processing_runs(document_id);
```

This allows the same original PDF to be reprocessed with:

```text
parser v1
parser v2
parser v3
```

without losing auditability.

### 12.2 `document_extractions`

Before user review/confirmation, extracted values are drafts.

A flexible staging table is useful:

```sql
CREATE TABLE document_extractions (
    id UUID PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES documents(id),
    processing_run_id UUID NOT NULL REFERENCES document_processing_runs(id),

    extraction JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Example staged extraction:

```json
{
  "supplier": {
    "name": "Example Supplier Inc."
  },
  "invoice_number": "INV-1049",
  "currency": "USD",
  "invoice_date": "2026-09-22",
  "totals": {
    "subtotal": 800.00,
    "shipping": 40.00,
    "tax": 0.00,
    "total": 840.00
  },
  "items": [
    {
      "description": "Example Product",
      "sku": "ABC-123",
      "quantity": 4,
      "unit_price": 200.00
    }
  ]
}
```

This JSON is **not the final source of truth for business analytics**.

After a user reviews/confirms the data, save it into normalized domain tables.

### 12.3 Confirmed business data

Later domain tables can look conceptually like:

```text
suppliers
purchases
purchase_items
```

For example:

```text
purchases.document_id → documents.id
```

This lets SupplyLens answer deterministic business questions with SQL rather than asking an LLM to infer numbers from raw chunks.

Principle:

> Use relational/confirmed data for arithmetic, reporting, provider totals, investments, product costs, and analytics.

---

## 13. Document chunks and vector search

The original PDF is stored in object storage.

The worker extracts text and creates chunks.

Recommended table:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE document_chunks (
    id UUID PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES documents(id),
    processing_run_id UUID NOT NULL REFERENCES document_processing_runs(id),

    chunk_index INTEGER NOT NULL,

    page_start INTEGER,
    page_end INTEGER,

    content TEXT NOT NULL,

    -- Replace N with the dimension required by the chosen embedding model.
    embedding vector(N),

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (processing_run_id, chunk_index)
);
```

Do not choose `N` until the embedding model is selected.

Useful metadata:

```json
{
  "section": "line_items",
  "source": "pdf_text",
  "bounding_boxes_available": false
}
```

The vector index can be added after enough data exists to justify it.

### Retrieval rule

Use chunks/embeddings when the user asks questions such as:

```text
"What does this invoice say about shipping?"
"Did the supplier mention a payment condition?"
"Find documents that mention a minimum order."
```

Use normalized relational tables for questions such as:

```text
"How much did we spend with supplier X?"
"What was the total cost of product Y?"
"Which supplier received the most investment this quarter?"
```

This avoids using vector search for data that SQL can answer exactly.

---

## 14. Worker lifecycle

### 14.1 The worker does not receive the PDF from the user again

After upload completion, the worker receives:

```text
document_id
```

It loads the `documents` row and then fetches:

```text
storage_bucket + object_key
```

from object storage.

### 14.2 Processing sequence

Recommended first implementation:

```text
1. Claim pending document.
2. Mark PROCESSING.
3. Download/stream original PDF from object storage.
4. Calculate SHA-256.
5. Validate actual PDF content.
6. Count pages.
7. Determine digital-text vs scanned PDF.
8. Extract text.
9. Extract structured candidate data.
10. Save document_extractions.
11. Create text chunks.
12. Generate/store embeddings when embedding support is enabled.
13. Mark READY.
```

On failure:

```text
processing_status = FAILED
processing_error = sanitized error
```

Keep the original object untouched.

### 14.3 PDF validation

Do not rely only on:

```text
filename == "*.pdf"
Content-Type == "application/pdf"
```

The worker should inspect the bytes and verify the file is actually parseable as a PDF.

This prevents malformed or mislabeled files from entering the extraction pipeline.

### 14.4 Keep original immutable

Never overwrite:

```text
documents/{document_id}/original.pdf
```

If OCR or PDF optimization is introduced later, create a derived object:

```text
documents/{document_id}/derived/ocr.pdf
```

Processing should always be reproducible from the original source.

---

## 15. Processing orchestration without adding Redis/RabbitMQ

For the MVP, avoid another infrastructure dependency unless necessary.

A zero-cost-friendly option is a **PostgreSQL-backed worker queue**.

The API changes the document to:

```text
processing_status = PENDING
```

A worker polls for work and claims one item transactionally:

```sql
SELECT id
FROM documents
WHERE processing_status = 'PENDING'
ORDER BY uploaded_at
FOR UPDATE SKIP LOCKED
LIMIT 1;
```

Then:

```sql
UPDATE documents
SET
    processing_status = 'PROCESSING',
    processing_started_at = now()
WHERE id = :document_id;
```

Benefits:

- no Redis required;
- no RabbitMQ required;
- PostgreSQL is already required;
- `SKIP LOCKED` permits multiple workers later;
- processing is durable across API restarts.

Do not use FastAPI `BackgroundTasks` as the durable processing system for important document work. A process restart can lose in-memory/background execution state.

A proper external queue can be introduced later if scale requires it.

---

## 16. React implementation

Recommended UI states:

```text
SELECTED
   │
   ▼
REQUESTING_UPLOAD_URL
   │
   ▼
UPLOADING
   │
   ▼
CONFIRMING
   │
   ▼
PROCESSING
   │
   ├──► READY
   └──► FAILED
```

Pseudo-code:

```typescript
async function uploadDocument(file: File) {
  if (file.type !== "application/pdf") {
    throw new Error("Only PDF files are supported");
  }

  const createResponse = await api.post("/api/v1/documents/uploads", {
    filename: file.name,
    content_type: file.type,
    size_bytes: file.size,
  });

  const { document_id, upload } = createResponse.data;

  const putResponse = await fetch(upload.url, {
    method: upload.method,
    headers: upload.headers,
    body: file,
  });

  if (!putResponse.ok) {
    throw new Error(`Object upload failed (${putResponse.status})`);
  }

  await api.post(`/api/v1/documents/${document_id}/complete`, {});

  return document_id;
}
```

After completion, poll:

```http
GET /api/v1/documents/{document_id}
```

until:

```text
READY
FAILED
```

For 2–10 MB PDFs, a normal single `PUT` is sufficient. Do not introduce multipart upload complexity yet.

---

## 17. Upload limits and security

### 17.1 Proposed MVP file size

Start with:

```text
25 MiB maximum PDF size
```

Most expected documents around 2–10 MB fit comfortably.

This can be changed by configuration.

### 17.2 Direct-upload size caveat

Because the browser uploads directly to object storage, FastAPI is not physically in the data path.

The application should:

1. reject a declared file size above the limit before signing;
2. verify `ContentLength` with `HEAD` after upload;
3. delete and reject an object if the actual size is above the limit.

For this MVP, that is sufficient.

If strict prevention of oversized uploads before any bytes reach storage becomes necessary, introduce a storage gateway/Worker or a provider mechanism specifically designed to enforce upload policies.

### 17.3 Presigned URLs

Treat presigned URLs like temporary credentials.

Rules:

- short TTL, e.g. 15 minutes;
- one object key per document;
- sign only required operation (`PUT` or `GET`);
- bucket remains private;
- never return storage API credentials to React;
- never write full signed URLs to logs;
- authorize the document before generating download URLs.

### 17.4 Filename safety

Store the original filename for display only.

Never use it:

- as a filesystem path;
- as an object key;
- as an SQL identifier;
- as a trusted MIME source.

### 17.5 MIME type

During upload:

```text
application/pdf
```

should be required and included in the signed PUT request.

After upload, actual binary validation remains mandatory.

### 17.6 CORS

R2 and MinIO must allow the frontend origin to perform browser uploads.

Development:

```text
http://localhost:5173
```

Production:

```text
https://<supplylens-frontend-domain>
```

Do not use `AllowedOrigins: ["*"]` in production unless there is a specific reason.

### 17.7 R2 credentials

Create credentials restricted to the SupplyLens bucket and only the operations required by the backend.

Secrets belong only in:

- deployment secret manager/environment;
- local `.env` excluded from Git.

---

## 18. State model

### Upload status

```text
PENDING
   │
   ├── upload/verification succeeds ──► UPLOADED
   │
   └── upload/verification fails ─────► FAILED
```

### Processing status

```text
NOT_STARTED
     │
     │ upload confirmed
     ▼
  PENDING
     │
     │ worker claims
     ▼
 PROCESSING
    │    │
    │    └──────── failure ───────► FAILED
    │
    └──────────── success ────────► READY
```

Valid common combinations:

```text
upload=PENDING   processing=NOT_STARTED
upload=UPLOADED  processing=PENDING
upload=UPLOADED  processing=PROCESSING
upload=UPLOADED  processing=READY
upload=UPLOADED  processing=FAILED
upload=FAILED    processing=NOT_STARTED
```

Avoid impossible combinations such as:

```text
upload=PENDING + processing=READY
```

Application services should own state transitions instead of controllers changing statuses directly.

---

## 19. Service boundaries in FastAPI

Suggested layers:

```text
API / Controllers
      │
      ▼
Application services
      │
      ├── DocumentRepository
      ├── ObjectStorage
      └── ProcessingJobRepository / queue
             │
             ▼
Infrastructure
      ├── PostgreSQL / SQLAlchemy
      └── boto3 S3 adapter
```

Example use cases:

```text
CreateDocumentUpload
CompleteDocumentUpload
GetDocument
CreateDocumentDownloadUrl
DeleteDocument
ProcessDocument
```

FastAPI route functions should mainly:

1. validate transport-level input;
2. call a use case/application service;
3. serialize the response.

They should not contain object-storage or extraction logic directly.

---

## 20. Suggested repository structure

For a monorepo:

```text
supplylens/
├── apps/
│   ├── api/
│   │   ├── src/
│   │   │   └── supplylens/
│   │   │       ├── api/
│   │   │       │   └── v1/
│   │   │       │       └── documents.py
│   │   │       ├── application/
│   │   │       │   └── documents/
│   │   │       │       ├── create_upload.py
│   │   │       │       ├── complete_upload.py
│   │   │       │       └── get_document.py
│   │   │       ├── domain/
│   │   │       │   └── documents/
│   │   │       ├── infrastructure/
│   │   │       │   ├── db/
│   │   │       │   └── storage/
│   │   │       │       ├── base.py
│   │   │       │       └── s3.py
│   │   │       ├── config.py
│   │   │       └── main.py
│   │   └── tests/
│   │
│   ├── worker/
│   │   ├── src/
│   │   │   └── supplylens_worker/
│   │   │       ├── main.py
│   │   │       ├── pdf/
│   │   │       ├── extraction/
│   │   │       └── embeddings/
│   │   └── tests/
│   │
│   └── web/
│       ├── src/
│       └── tests/
│
├── docs/
│   └── document-upload-storage-architecture.md
│
├── scripts/
│   └── init_storage.py
│
├── tests/
│   └── fixtures/
│       ├── invoice-simple.pdf
│       ├── invoice-multipage.pdf
│       ├── invoice-scanned.pdf
│       └── malformed.pdf
│
├── compose.yaml
├── .env.example
└── README.md
```

Exact folder naming can change, but keep storage infrastructure separate from application use cases.

---

## 21. Local development workflow

### First setup

```bash
# 1. Start PostgreSQL and MinIO
docker compose up -d postgres minio

# 2. Create local bucket + CORS
python scripts/init_storage.py

# 3. Run migrations
alembic upgrade head

# 4. Start FastAPI
uvicorn supplylens.main:app --reload --port 8000

# 5. Start React/Vite
npm run dev

# 6. Start worker when processing is implemented
python -m supplylens_worker.main
```

Expected services:

```text
React:          http://localhost:5173
FastAPI:        http://localhost:8000
FastAPI docs:   http://localhost:8000/docs
PostgreSQL:     localhost:5432
MinIO API:      http://localhost:9000
MinIO Console:  http://localhost:9001
```

### Daily workflow

Usually:

```bash
docker compose up -d
```

then run API, worker, and frontend through the preferred local tooling.

MinIO and PostgreSQL use named volumes, so documents and database records survive container restarts.

To intentionally reset local infrastructure:

```bash
docker compose down -v
```

**Warning:** `-v` deletes local PostgreSQL and MinIO volume data.

---

## 22. Testing strategy

We want three levels.

### 22.1 Unit tests

Use fake/in-memory implementations for:

- `ObjectStorage`;
- repositories;
- processing dispatch.

Test application rules without Docker/network dependencies.

Examples:

```text
- rejects non-PDF content type
- rejects zero-byte upload
- rejects declared size above limit
- generates object key from UUID
- does not use original filename as key
- does not complete when HEAD object is missing
- does not complete when actual size differs
- complete endpoint is idempotent
```

### 22.2 Integration tests

Run:

```text
FastAPI + PostgreSQL + MinIO
```

Verify real S3 behavior:

1. request presigned URL;
2. upload fixture with HTTP `PUT`;
3. call completion endpoint;
4. confirm DB row;
5. confirm MinIO object;
6. download using backend storage adapter.

This catches problems that a fake storage adapter cannot catch, especially:

- presigned signatures;
- CORS-related configuration;
- object-key handling;
- `HEAD`;
- metadata;
- content length.

### 22.3 Browser E2E tests

Use Playwright once the React flow exists.

Example:

```text
docker compose up
        │
        ▼
Playwright opens SupplyLens
        │
        ▼
select tests/fixtures/invoice-simple.pdf
        │
        ▼
React requests upload URL
        │
        ▼
browser uploads directly to MinIO
        │
        ▼
React calls /complete
        │
        ▼
worker processes document
        │
        ▼
UI becomes READY
        │
        ▼
assert extracted fields
```

This verifies the complete architecture, not merely mocked HTTP calls.

---

## 23. Recommended test fixtures

Keep small deterministic PDFs in the repository:

```text
tests/fixtures/
├── invoice-simple.pdf
├── invoice-multipage.pdf
├── invoice-with-tables.pdf
├── invoice-scanned.pdf
├── invoice-large-but-valid.pdf
├── malformed.pdf
└── not-a-pdf.pdf
```

Do not commit real supplier/customer documents containing private business information.

Generate synthetic fixtures instead.

---

## 24. Failure handling

### Upload URL generated but never used

The DB row remains:

```text
upload_status=PENDING
```

A cleanup job can later delete abandoned upload intents older than, for example, 24 hours.

### PUT fails in React

Do not call `/complete`.

Display retry.

A future retry endpoint can issue another URL for the same `document_id`.

### React uploads successfully but crashes before `/complete`

The object exists but DB still says `PENDING`.

Options:

**MVP:** user retries completion or an internal reconciliation task finds stale pending rows and performs `HEAD`.

**Later:** use R2 object-created event notifications.

The MVP should not add event infrastructure solely for this edge case.

### `/complete` called but object is missing

Return conflict/error and keep upload non-complete.

Suggested:

```http
409 Conflict
```

### File is not actually a PDF

Worker marks:

```text
processing_status=FAILED
```

with a controlled error code such as:

```text
INVALID_PDF
```

### Parser fails

Keep the original PDF.

Store:

```text
processing_status=FAILED
processing_error=<sanitized message>
```

Allow reprocessing after the parser is fixed.

---

## 25. Cleanup and deletion

A document deletion operation should eventually remove:

1. derived extracted/chunk data according to domain/audit policy;
2. object-storage artifacts;
3. the original PDF;
4. document metadata or soft-delete it depending on requirements.

For the MVP, prefer soft deletion in PostgreSQL:

```text
deleted_at = now()
```

and then have a cleanup path delete storage objects.

Avoid deleting the DB record first and leaving an untracked object in R2.

---

## 26. Observability

At minimum log:

```text
document_id
processing_run_id
storage_provider
object_key
upload_status
processing_status
duration_ms
error_code
```

Do **not** log:

```text
presigned URL
S3 secret key
raw extracted sensitive content by default
```

Useful metrics later:

```text
documents_uploaded_total
documents_processed_total
document_processing_failed_total
document_processing_duration_seconds
stored_document_bytes
pending_documents
```

The application's stored-byte count can also support the zero-dollar R2 quota guard.

---

## 27. API summary

| Method | Endpoint | Responsibility |
|---|---|---|
| `POST` | `/api/v1/documents/uploads` | Create document row and presigned `PUT` URL |
| `POST` | `/api/v1/documents/{id}/complete` | Verify uploaded object and queue processing |
| `GET` | `/api/v1/documents/{id}` | Read document lifecycle/status |
| `POST` | `/api/v1/documents/{id}/download-url` | Generate temporary private download/view URL |
| `POST` | `/api/v1/documents/{id}/upload-url` | Optional: regenerate expired upload URL |
| `DELETE` | `/api/v1/documents/{id}` | Future/optional deletion flow |

The actual binary upload endpoint is **not FastAPI**.

It is the temporary presigned object-storage URL returned by:

```text
POST /api/v1/documents/uploads
```

---

## 28. MVP implementation order

Implement in this order to avoid mixing PDF extraction with upload infrastructure too early.

### Phase 1 — storage foundation

1. Add PostgreSQL `documents` migration.
2. Add settings/configuration.
3. Define `ObjectStorage` interface.
4. Implement `S3ObjectStorage` with boto3.
5. Add MinIO to Docker Compose.
6. Add `scripts/init_storage.py`.
7. Confirm FastAPI can `HEAD`, `PUT`/sign, `GET`, and `DELETE` against MinIO.

### Phase 2 — upload API

8. Implement `POST /api/v1/documents/uploads`.
9. Generate UUID/object key.
10. Persist `PENDING` document.
11. Generate presigned `PUT`.
12. Implement React direct upload.
13. Implement `POST /{id}/complete`.
14. Verify with `HEAD`.
15. Mark `UPLOADED/PENDING`.
16. Implement `GET /{id}`.

At this point, direct browser-to-object-storage upload is complete and testable E2E.

### Phase 3 — processing worker

17. Implement worker claim loop.
18. Download object using the storage abstraction.
19. Validate PDF.
20. Calculate SHA-256.
21. Extract page count/text.
22. Add processing-run persistence.
23. Mark `READY` or `FAILED`.

### Phase 4 — extraction

24. Extract invoice/purchase candidate fields.
25. Save draft extraction.
26. Build review/correction UI.
27. Persist confirmed normalized business data.

### Phase 5 — retrieval

28. Create document chunks.
29. Select embedding model.
30. Enable pgvector.
31. Store embeddings.
32. Add document-grounded search/query capability.

### Phase 6 — production R2

33. Create private R2 bucket.
34. Create restricted R2 API credentials.
35. Configure production CORS.
36. Change environment settings from MinIO to R2.
37. Run integration smoke test.
38. Enable application storage quota/alerts.

No business/application code should need to change between steps 32 and 33–38.

---

## 29. Decisions intentionally deferred

Do not block the upload implementation on these decisions:

- OCR engine;
- exact PDF parser;
- exact extraction/LLM provider;
- embedding model and vector dimension;
- vector index type;
- advanced queue provider;
- R2 event notifications;
- resumable/multipart upload;
- PDF optimization/compression;
- authentication/tenant isolation details;
- exact normalized invoice schema.

They can be added after the base upload/storage lifecycle is proven.

---

## 30. Decisions already made

These should be treated as current SupplyLens architecture decisions unless requirements change:

1. **React does not proxy PDFs through FastAPI.**
2. **FastAPI creates short-lived presigned upload URLs.**
3. **React uploads directly to object storage.**
4. **Cloudflare R2 Standard is the production object-storage target.**
5. **MinIO is the local object-storage implementation.**
6. **Both use the same S3-compatible storage adapter.**
7. **PostgreSQL stores metadata and extracted/normalized information, not PDF bytes.**
8. **The database stores bucket/object key, not permanent public URLs.**
9. **The source PDF remains private and immutable.**
10. **FastAPI verifies an upload with an authoritative `HEAD` request before accepting completion.**
11. **PDF processing happens outside the upload request.**
12. **The worker fetches the PDF from object storage; the user does not upload it again.**
13. **Structured/confirmed business data and semantic document chunks are separate concerns.**
14. **pgvector will be used when semantic retrieval is implemented, avoiding a separate vector database initially.**
15. **A normal single presigned `PUT` is enough for the current expected 2–10 MB PDFs.**
16. **Multipart/resumable upload is deferred until it is actually needed.**
17. **The first durable processing queue can use PostgreSQL rather than adding Redis/RabbitMQ.**
18. **The project should enforce application-side storage limits to protect the $0 production objective.**

---

## 31. Official references

Cloudflare R2:

- S3 API overview:
  https://developers.cloudflare.com/r2/api/s3/
- S3 compatibility:
  https://developers.cloudflare.com/r2/api/s3/api/
- Presigned URLs:
  https://developers.cloudflare.com/r2/api/s3/presigned-urls/
- Pricing:
  https://developers.cloudflare.com/r2/pricing/

MinIO:

- Container documentation:
  https://min.io/docs/minio/container/index.html
- Single-node container deployment:
  https://min.io/docs/minio/container/operations/install-deploy-manage/deploy-minio-single-node-single-drive.html

---

## 32. Final architecture principle

The central rule is:

```text
The database knows WHAT a document is.
Object storage holds the original BYTES.
The worker understands WHAT IS INSIDE the document.
Normalized tables hold CONFIRMED BUSINESS FACTS.
pgvector/chunks support SEMANTIC DOCUMENT RETRIEVAL.
```

This separation lets SupplyLens evolve its parser, OCR, extraction strategy, and AI components without redesigning the upload/storage subsystem.
