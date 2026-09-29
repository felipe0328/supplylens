# SupplyLens — Backend Implementation Plan

**Status:** Proposed work plan  
**Date:** 28 September 2026  
**For:** [`felipe0328/supplylens`](https://github.com/felipe0328/supplylens)  
**Purpose:** Turn the [MVP definition](SupplyLens-MVP-Definition-v0.1.md) and [architecture](SupplyLens-Architecture-v0.1.md) into small backend tasks that one developer can complete and verify independently.

## 1. Starting point and working rule

The repository currently has a Python 3.14 FastAPI package with only `GET /health`, a React starter, a PostgreSQL 17 + pgvector Compose service, and no backend tests or migrations. Use `apps/backend/src/supplylens/` as the Python package. Keep the API and future worker in that package; develop one end-to-end backend slice at a time.

**Do not start with a full database schema or LLM integration.** The first useful flow is: upload a synthetic PDF → retain its bytes → process a job → review extracted or manually entered values → record a purchase case. Every later feature builds on that distinction between document evidence and a reviewed record.

Two setup fixes belong in the first PR: the Compose DB is configured as `localdev` while its health check asks for `supplylens`, and compiled `__pycache__/*.pyc` files are tracked. Fix the health check, ignore generated Python files, and remove those tracked cache files. The API is currently backed by a root-level `api.py`; it can stay there until the first router is introduced.

### Language used throughout this plan

- **Document:** An immutable supplier PDF plus extracted suggestions. It is evidence, not a purchase.
- **Purchase case:** The human-reviewed business view, possibly supported by more than one document.
- **Business status:** `planned`, `ordered`, or `purchase_recorded`, chosen explicitly by a user. A pre-order is not automatically a recorded purchase; an invoice is not required to record a real bill as a purchase.
- **Revision:** An immutable version of a reviewed purchase case. Current reports read one current revision per case.
- **Estimate:** A policy result tied to one purchase revision or provisional scenario and one policy version. It does not represent payment, stock, or realized profit.

## 2. Backend boundaries

| Module | Owns | Must not own |
| --- | --- | --- |
| `api` | HTTP routes, authentication, request/response schemas, error translation. | PDF parsing and financial rules. |
| `documents` | Upload metadata, storage interface, extraction candidates, provenance, document review. | Purchase-reporting semantics. |
| `jobs` / `worker` | Recoverable processing state, leases, retries, PDF/OCR/indexing execution. | Human confirmation. |
| `purchases` | Business status, revisions, source links, later-document reconciliation. | OCR or model-generated final decisions. |
| `catalog` | Store products, supplier identifiers, reviewed matches, name/SKU suggestions. | Rewriting supplier text on old document lines. |
| `policies` | Safe typed steps, validation, publication, deterministic evaluation, trace. | Python execution from user text or a private formula baked into public code. |
| `reports` | Currency-safe aggregation of reviewed cases and drill-down. | Treating invoices as payments or pre-orders as completed purchases. |
| `search` / `assistant` | Passage retrieval, citations, optional model adapters and approved metric interpretation. | Arbitrary SQL, purchase confirmation, policy publication. |
| `infrastructure` | SQLAlchemy repositories, migrations, local/object storage adapters, provider clients. | Core business rules. |

Use application services called by routes and the worker. Keep money/revision/policy rules independent of FastAPI and ORM models so they can be tested directly. Add directories as slices require them; empty module scaffolding provides little value.

## 3. Shared contracts and conventions

Start HTTP routes under `/api/v1`. Examples below are proposed contracts, not all endpoints to build in the first PR. Return IDs and status links after asynchronous operations; do not block upload on OCR. Protect private routes when real data is used.

| Concern | Contract |
| --- | --- |
| Money | Decimal in Python and database `NUMERIC`; JSON amounts as decimal **strings** with explicit ISO currency. Never binary floats for monetary calculations. |
| Quantity and weight | Decimal strings with units (`unit`, `pack`, `lb`, etc.); do not infer sellable quantity from supplier quantity. |
| Dates and pagination | ISO dates/timestamps, UTC storage, cursor or limit/offset pagination with stable sort. |
| Evidence | Field candidate includes `document_id`, one-based `page`, optional bounding box/text excerpt, source kind, and extraction version. Manual changes include actor/time. |
| Errors | Stable machine code, short human message, and field details where applicable. Use `400/422` invalid input, `404` unavailable resource, `409` duplicate or stale revision, `503` unavailable dependency. |
| Concurrency | Draft edits and purchase revision creation include an expected version/current revision; reject stale writes rather than silently overwriting another edit. |
| Idempotence | Exact duplicate PDF upload returns a clear existing-document result or conflict; worker replays do not create duplicate drafts. A retry must not create another purchase. |
| Versioning | Document extraction run/version, current purchase revision, policy version, and estimate inputs are retained separately. |

Do not require a parsed supplier, date, or currency merely to upload a PDF. Require reviewed information only at the point where the user records a purchase case. A handling/freight row is a `charge`, MSRP is distinct from supplier net price, and missing weight remains missing. These are important lessons from the supplied examples, but use invented values in public fixtures.

## 4. Work packages and endpoints

Each package is independently reviewable. A route listed in a later package is deliberately **not** required in an earlier one.

### B0 — Backend foundation and test harness

**Deliver:** Fix Compose health check; remove tracked Python cache and add a root ignore rule; add `pytest`, `httpx`/FastAPI `TestClient`, Ruff, database configuration, SQLAlchemy, Alembic, and a migration command. Introduce an app factory or dependency wiring only if it improves test isolation. Keep existing `/health`; add `GET /api/v1/health/ready` that checks a DB connection and returns an unavailable status if DB is down. Decide whether Python 3.14 works with the selected document/OCR dependencies before accumulating more dependencies; document a version change if required.

**Tests:** One API test for liveness without DB, one readiness success/failure test, and a clean PostgreSQL migration up test. Tests should point at a disposable test database, never the development database. Update `Makefile` with a backend test/check target.

**Done when:** A new clone can run `uv sync`, start the DB, apply migrations, and run the backend tests from documented commands. No generated cache files remain tracked.

### B1 — Document upload and private bytes

**Endpoints:**

| Method and path | Behavior |
| --- | --- |
| `POST /api/v1/documents` | Multipart PDF upload. Validate size and PDF signature, stream to a local private store, compute SHA-256, persist `Document` and a queued `ProcessingJob`; return `202` with both IDs and status URLs. Do not create a purchase. |
| `GET /api/v1/documents/{id}` | Metadata and processing state; no raw storage key. |
| `GET /api/v1/documents/{id}/file` | Authorized PDF stream with safe response headers. |
| `GET /api/v1/jobs/{id}` | Job state and error code, scoped to the document. |

**Logic:** A `DocumentStore` protocol (`put`, `open`, `delete`) with a local-disk adapter, configurable file/page limits, exact-hash duplicate handling, and cleanup/reconciliation if file storage and DB transaction disagree. Limit concurrent uploads and never trust filename or MIME alone. Upload must work with no model key. For this early local slice, use only synthetic PDFs until authentication is implemented.

**Tests:** Valid PDF persists metadata and bytes; malformed/non-PDF and oversized uploads fail; exact repeat does not make a new job; file endpoint returns original bytes; missing IDs and storage failure give useful errors; database failure leaves no silently orphaned purchase. PostgreSQL integration tests verify document/job transaction behavior.

**Done when:** You can upload a synthetic PDF, inspect its job, and retrieve the same bytes after restarting the API.

### B2 — Recoverable worker and digital extraction

**Endpoints:** `GET /api/v1/documents/{id}/draft`; `POST /api/v1/jobs/{id}/retry` for failed jobs. The worker is a separate CLI/process entry point, not a FastAPI background task.

**Logic:** Implement a leased PostgreSQL job claim, bounded retries/backoff, and idempotent output keyed by document plus extractor version. Start with digital PDFs and `pdfplumber`: page text, table rows, one-based page references, and source positions when reliable. A general parser and the first supplier rule return candidate header fields, product lines, and charge lines. Do not turn a freight row into a product. Record warnings for mismatched line totals and unknown fields; never silently fix source values. Keep the PDF and allow manual review on extraction failure.

**Tests:** Two small synthetic digital PDFs with different layouts and expected JSON fields; repeated worker execution creates no duplicate lines; crash/retry leaves a recoverable job; a fixture with MSRP versus net supplier price and a freight charge classifies them correctly; malformed tables produce warnings and a reviewable draft rather than invented values.

**Done when:** Upload followed by worker execution produces a draft with page-linked candidates, even if some fields need manual input.

### B3 — Draft edits and reviewed purchase revisions

**Endpoints:**

| Method and path | Behavior |
| --- | --- |
| `PATCH /api/v1/documents/{id}/draft` | Save field/line corrections using an expected draft version; retain original candidate and correction provenance. |
| `POST /api/v1/purchases` | Create a case from a reviewed document and explicit status (`planned`, `ordered`, `purchase_recorded`); return case and revision IDs. |
| `POST /api/v1/purchases/{id}/revisions` | Create a new immutable reviewed revision, checking expected current revision. |
| `GET /api/v1/purchases/{id}` | Current revision, source links, status, and monetary components. |
| `GET /api/v1/purchases/{id}/revisions` | Historical revisions with actor/time. |
| `GET /api/v1/purchases` | Filtered case list; status and currency are explicit. |

**Logic:** Confirmation is a transaction. A case has a current revision pointer; revisions and their lines never mutate. Require an explicit business status and reviewed currency/amounts. Permit unknown fields with explicit warnings where appropriate, but do not claim a definitive per-unit cost when sellable quantity is unknown. A pre-order stays outside recorded purchase totals even after its data has been reviewed. A bill may be marked `purchase_recorded` without any invoice. Link the primary document once; prevent it from becoming the primary source for another case.

**Tests:** Plan/order/purchase statuses; manual correction provenance; no invoice needed; immutable old revision; stale version returns `409`; confirmation rollback is atomic; a charge line stays out of sellable product quantity; no LLM credential in the entire path.

**Done when:** A person can upload a synthetic bill, correct it, record a purchase, and inspect its original PDF and revision history through the API.

### B4 — Authentication before real data

**Endpoints:** A minimal session surface such as `POST /api/v1/session`, `DELETE /api/v1/session`, and `GET /api/v1/me`; exact provider/session implementation is a small ADR. No multi-tenant SaaS administration.

**Logic:** One business workspace, explicit operator identity, authenticated private PDF and record access, server-held secrets, secure cookie/CSRF handling as appropriate to the chosen frontend setup. Keep public `/health` separate. Never make a development bypass available in production.

**Tests:** Unauthenticated upload/read denied; authenticated access allowed; role checks where needed; another user's private file is not accessible if multi-user accounts are enabled; no credentials or PDFs appear in logs. Finish this before loading actual supplier files or deploying a private instance.

**Done when:** Real private documents can be handled with authenticated access and no public file URL.

### B5 — OCR, duplicate suggestions, and related documents

**Endpoints:** `POST /api/v1/purchases/{id}/documents` to attach a document; `GET /api/v1/purchases/{id}/comparison` for field differences; `POST /api/v1/purchases/{id}/reconciliation` to create an explicit revised case after review. Existing job endpoints cover OCR retries.

**Logic:** Detect scanned pages and run local OCR before the same parser. Exact file hash detects repeats; fuzzy supplier/reference/date/line signals only **suggest** a relationship. Later matching invoice = supporting evidence, no new case/estimate. A mismatch creates a review finding, not an automatic overwrite. Document type alone never changes business status. Preserve extraction run history.

**Tests:** Mixed digital/scanned synthetic PDF; OCR failure retains source; repeat PDF does not double-count; matching bill/invoice attaches to one case unchanged; mismatched values need explicit reconciliation; pre-order does not silently become a recorded purchase.

**Done when:** A second document can be compared and linked without changing reviewed values or totals by surprise.

### B6 — Product catalog and supplier matches

**Endpoints:** `POST /api/v1/products`, `GET /api/v1/products`, `GET /api/v1/products/{id}`, `PATCH /api/v1/products/{id}`, `GET /api/v1/document-lines/{id}/match-suggestions`, `PUT /api/v1/document-lines/{id}/product` (reviewed link). Exact route naming may be adjusted before implementation; keep business behavior stable.

**Logic:** Keep supplier description/code on historical lines. Prefer reviewed supplier-code mappings, then exact identifiers, normalized names, then fuzzy suggestions. Nothing fuzzy auto-links. Spanish name/SKU templates are deterministic and configurable; protect unique SKU and supplier mapping constraints. A line may stay unmatched.

**Tests:** Exact identifier match; ambiguous fuzzy candidates remain unlinked; supplier code maps consistently after review; duplicate SKU rejected; catalog rename does not rewrite source line or prior revision.

**Done when:** Repeated supplier lines can be matched to one product with a traceable manual decision.

### B7 — Policy definition and deterministic estimates

**Endpoints:** `POST /api/v1/policies` (draft), `PATCH /api/v1/policies/{id}`, `POST /api/v1/policies/{id}/validate`, `POST /api/v1/policies/{id}/preview`, `POST /api/v1/policies/{id}/publish`, `POST /api/v1/purchases/{id}/estimates`, `GET /api/v1/estimates/{id}`.

**Logic:** Define typed named inputs and a bounded acyclic graph of approved operations; validate references, units, currency, zero division, and allocation bases. Published versions are immutable. Evaluate using `Decimal`, explicit FX and rounding inputs, and an intermediate-value trace. Missing weight/FX/tax treatment blocks the affected output or yields an expressly provisional scenario. Detect double allocation and reconcile allocation remainders. The public repo contains no private Mulligan rates or formula config.

**Tests:** Pure evaluator tests for step ordering, cycle/type/unit rejection, allocation sum after rounding, currency mismatch, missing input, deterministic replay; API tests for draft versus published immutability; old estimate remains unchanged when a policy or purchase revision changes. Private acceptance cases stay outside public Git.

**Done when:** One synthetic policy can produce an explainable per-unit estimate and be replayed exactly from persisted inputs and policy version.

### B8 — Purchase reports and safe metrics

**Endpoints:** `GET /api/v1/reports/suppliers`, `GET /api/v1/reports/products`, `GET /api/v1/reports/unit-prices`, and `POST /api/v1/metrics/query` with an allowlisted metric name and typed filters. Provide drill-down IDs for every total.

**Logic:** Read one current revision per purchase case; default to `purchase_recorded`, allow separate plan/order views. Group amounts by currency or require an explicit policy-based conversion and label converted values as estimates. Support date/supplier/product filters. Do not expose “actual spent,” current stock, realized profit, or demand without future event data.

**Tests:** Two related documents count once; an unpromoted pre-order counts only in plan/order view; different currencies are not added; revisions change current report while historical estimate remains; filter/metric allowlist rejects unsupported requests; every total drills down to its records.

**Done when:** Report values reconcile to the reviewed case list and can be explained from source documents.

### B9 — Search and optional AI

**Endpoints:** `POST /api/v1/documents/search` (passages and citations), optional `POST /api/v1/questions/document` (grounded answer), optional `POST /api/v1/questions/purchases` (model proposes an allowlisted metric request). Keep document questions separate from structured metric questions.

**Logic:** First add PostgreSQL full-text passages with document/page context. Add local embeddings and pgvector as a measured improvement, then merge ranked results. A local embedding failure falls back to keyword search. An opt-in LLM adapter sees only relevant excerpts, returns schema-checked suggestions/answers, and cannot update facts, policies, or SQL. Store model/extractor versions and evaluate keyword versus semantic versus hybrid on labeled synthetic questions.

**Tests:** Exact product code retrieval, synonym question retrieval, page citation validity, unsupported answer refusal, prompt-injection text in a PDF cannot issue business commands, model outage leaves search and reports working, unapproved metric/SQL rejected.

**Done when:** Passage search works with no external credentials; optional AI demonstrates measured value over the baseline without becoming a dependency.

## 5. Data model: create tables when a slice needs them

| Slice | Tables to introduce or extend | Key constraints |
| --- | --- | --- |
| B0 | Alembic metadata only. | Migration can be applied to a clean PostgreSQL instance. |
| B1 | `documents`, `processing_jobs`. | Document hash/index and job-document FK; file path is an opaque key. |
| B2 | `extraction_runs`, `document_fields`, `document_lines`. | Extraction version/idempotence; page references; source roles. |
| B3 | `suppliers`, `purchase_cases`, `purchase_revisions`, `purchase_lines`, source links. | Unique revision number per case; current pointer; one primary source link; immutable history by service contract. |
| B4–B6 | User/session tables as selected, document link/comparison records, `products`, `supplier_products`. | Explicit relationship, unique reviewed identifiers/SKU as appropriate. |
| B7 | `policies`, `policy_versions`, `estimates`. | Immutable published version; estimate FK to exact case revision and policy version. |
| B8–B9 | Report indexes/views only if measured, `search_passages` with text/vector indexes. | Passage references document and page; embedding model/version identified. |

The logical architecture is not a mandate to build every table immediately. Review each migration and constraint with a real use case and synthetic fixture. Avoid a generic event-sourcing framework; immutable purchase revisions provide the history this MVP needs.

## 6. Test strategy and developer workflow

| Test level | Use it for | Example |
| --- | --- | --- |
| Pure unit | Calculation operations, document arithmetic checks, matching thresholds, status transitions. | Two fees allocated by value reconcile after rounding. |
| API contract | Validation, status codes, version conflicts, auth, response schemas with FastAPI `TestClient`. | Stale draft edit returns `409`. |
| PostgreSQL integration | FKs, transactions, migration up, job leases/idempotence, currency-safe report queries. | Two linked PDFs produce one purchase total. |
| Worker/fixture integration | Digital and scanned PDFs with expected fields and pages. | Freight row is a charge, not a sellable product. |
| One small end-to-end path | Upload → draft → human review → purchase → report, with no LLM. | Synthetic bill appears in supplier report. |
| Retrieval evaluation | Labeled questions, expected passages/citations, keyword/vector/hybrid comparison. | “Handling charge?” cites the correct page. |

Use `pytest` fixtures for isolated database/storage resources, `tmp_path` for file adapters, and synthetic PDFs checked into `fixtures/`. Do not mock SQLAlchemy when a behavior depends on PostgreSQL transactions or constraints. Do not add tests that simply repeat implementation code. For each package, write a failing test for its key invariant, implement, then run the relevant tests and one broader integration check. Pin dependencies in `uv.lock`; run tests and lint in CI. FastAPI's `TestClient` supports normal pytest API tests, and Alembic supplies the schema migration workflow.

**Suggested PR rhythm:** one B0 PR; split B1/B2 if large; one focused PR per remaining package or half-package. Each PR includes a short “why,” endpoint examples, migration notes, verification commands, and one sample response or screenshot where useful. You should be able to explain the business rule without reading framework code.

## 7. First three coding sessions

1. **Session 1 — hygiene and tests:** Fix Compose health check, ignore/remove cache files, add pytest/TestClient and a health test, add `make be-test`. Commit when tests pass.
2. **Session 2 — database baseline:** Add config, SQLAlchemy session, Alembic, a first reversible migration, and a disposable PostgreSQL integration test. Verify clean setup from scratch.
3. **Session 3 — upload boundary:** Define `DocumentStore`, `Document` and `ProcessingJob` persistence, then implement `POST /api/v1/documents` for synthetic PDFs. Keep extraction for B2.

The first full vertical checkpoint is not an AI demo: it is a synthetic PDF uploaded, retained, turned into a reviewable draft, and recorded under the correct business status. That gives every later module a trustworthy foundation.

## 8. Decisions to record as you code

- Exact limits for PDF bytes/pages and job duration, based on fixtures and local measurements.
- Exact duplicate response shape (`409` with existing ID versus idempotent return) before frontend work.
- Whether field corrections are versioned draft snapshots or an append-only correction log; either way retain original extraction evidence.
- Whether a single operator account is enough initially; authentication must precede real data.
- Policy JSON schema and operation set after proving it can express the MVP pricing subset using **private** examples.
- When to add SSE instead of polling, and when to add vectors instead of keyword-only search, based on measured need.

These choices do not block B0. Put short ADRs in `docs/decisions/` when resolved.

## 9. References

- [SupplyLens MVP definition](SupplyLens-MVP-Definition-v0.1.md)
- [SupplyLens architecture](SupplyLens-Architecture-v0.1.md)
- [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [SQLAlchemy session basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)
- [PostgreSQL `SKIP LOCKED`](https://www.postgresql.org/docs/current/sql-select.html)
- [pgvector hybrid search](https://github.com/pgvector/pgvector#hybrid-search)
