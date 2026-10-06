# SupplyLens — Backend Implementation Board

- **Last reviewed:** 6 October 2026
- **Implementation baseline:** `main` at `fee42fe6de518918b2c889bb397735f7120e3ba9` (`0.7.0`)
- **Purpose:** A plain-English, ordered backend backlog. Each task below is intended to become one branch and one focused pull request.
- **Scope:** Backend application code, database migrations, worker execution, backend tests, and the infrastructure needed to operate those components. Frontend implementation is a separate board.

## 1. How to use this board

This replaces the original B0–B9 proposal. That proposal described a scaffold that no longer exists and included OCR, which is outside the current MVP. Do not use the old upload routes or old test layout as implementation instructions.

Read the [MVP definition](SupplyLens-MVP-Definition-v0.1.md), [architecture](SupplyLens-Architecture-v0.1.md), and [upload/storage design](document-upload-storage-architecture.md) alongside this board. Product scope comes from the MVP; domain and security boundaries come from the architecture. The upload/storage design explains the implemented direct-upload direction, but its example schemas, status names, numeric JSON examples, and document polling SQL are not the current application contract. Use decimal strings, the existing job table, and the decisions below instead of copying those examples literally.

### 1.1 Task lifecycle

- **DONE:** Merged implementation exists, with linked evidence. This does not mean every later hardening requirement is complete.
- **TODO:** Not started or no merged implementation was found.
- **IN PROGRESS:** A branch exists; record its URL and owner.
- **BLOCKED:** Record the exact missing prerequisite or decision.
- **DEFERRED:** Intentionally outside this release; state why.

When starting a task, change only its status, owner, and branch link. When its PR merges, check its acceptance items, record the merged PR and verification evidence, and update the summary table in the same change or a small follow-up documentation PR. Never mark an entire phase complete because one of its tasks merged. A failed or unperformed check is not evidence of completion.

Task IDs are permanent. Do not renumber them when adding work. Use a new ID and insert it at the correct dependency point. If a task must be split, keep its ID as a parent and use suffixes such as `SL-BE-005A`; document which child delivers each original acceptance item. Do not silently move unfinished requirements into a completed ticket.

### 1.2 Branch and PR convention

- Suggested branch: `backend/sl-be-001-extraction-contracts`, changing the ID and short description for each task.
- Suggested implementation PR title: `feat: [SL-BE-001] add versioned extraction contracts`. Use `fix:`, `test:`, or another appropriate single prefix when the work is not a feature.
- `SL-BE-*` is a **local board ID, not an existing Jira key**. If Jira is adopted, add its actual key without removing the local ID.
- Each card's title becomes the Jira summary; goal and implementation become its description; dependencies become ticket links; acceptance items become acceptance criteria. Keep tests and merge output attached to the ticket.
- Follow [the PR definition](../specifications/pull-request-definition.md): Summary, Testing with separate Unit testing and Manual testing sections, and Rollback plan. Do not claim manual checks as automated tests.
- This board update uses `minor:` as requested. In the current release workflow, that prefix takes the default **patch** path: `0.7.0` would become `0.7.1` if no other release intervenes and no major/feature labels override it. Do not edit version manifests manually for this documentation PR. Implementation `feat:` PRs follow the workflow's feature/minor-version rule.

### 1.3 What “ready to merge” means for every task

In addition to its own checklist, every card must meet these shared gates:

1. Changes implement only that card's scope. Existing user work and unrelated refactors stay out of the PR.
2. The observable success, invalid-input, dependency-failure, and concurrency paths have tests where applicable. Python unit tests are co-located as `<module>_test.py`; follow [the Python unit-testing rules](../.github/instructions/python-unit-testing.instructions.md).
3. PostgreSQL-specific locks, enum migrations, constraints, and transactions are tested against disposable PostgreSQL. SQLite tests are useful but are not proof of PostgreSQL concurrency behavior. MinIO tests use disposable buckets and synthetic data.
4. Model changes include an inspected Alembic migration, clean upgrade, migration-drift check, and safe rollback instructions. Update the expected table set in `tests/integration/test_migrations.py` when adding tables. Never reset a development or production schema to run a test.
5. New ports use typed inputs/results and provider-independent errors. Controllers do not import provider SDKs, FastAPI, or ORM model classes to implement business rules.
6. New HTTP routes have typed schemas, documented status codes, stable error codes, and tests. Scope to the authorized workspace once the security phase is implemented; before then use synthetic data only.
7. The no-LLM path remains functional. Unknown facts stay unknown; prices and policy calculations use `Decimal`, not binary floats.
8. Do not log PDFs, extracted text, amounts, credentials, presigned URLs, or private policies. Tests and PR evidence contain no real supplier data.
9. Update this board, affected API examples, and operating instructions when behavior changes. Record practical manual checks separately.

## 2. What is already implemented

This inventory comes from current code and merged PRs, not from the outdated scaffold description in other files. The tests listed here exist; they were not all rerun as part of this documentation update.

| Historical ID | Status | Implemented capability | Evidence and boundary |
| --- | --- | --- | --- |
| DONE-01 | DONE | FastAPI package, liveness/readiness, lazy SQLAlchemy sessions, Alembic baseline, pytest/Ruff and development commands. | [PR #3](https://github.com/felipe0328/supplylens/pull/3); `api.py`, `database/database.py`, `alembic/`, `Makefile`. Readiness returns 503 on DB failure. [ADR 0001](decisions/0001-python-314-digital-pdf-compatibility.md) establishes Python 3.14/pdfplumber fixture compatibility, not field-extraction correctness. |
| DONE-02 | DONE | Twelve generated digital PDF scenarios with expected business fields and warnings. | [PR #2](https://github.com/felipe0328/supplylens/pull/2); `fixtures/README.md`, `fixtures/expected.json`, `fixtures/pdfs/`. These are inputs for future extraction tests, not evidence that extraction works. |
| DONE-03 | DONE | Document model, migrations, nonblank filename checks, upload/processing states, and soft deletion. | [PR #4](https://github.com/felipe0328/supplylens/pull/4), [PR #10](https://github.com/felipe0328/supplylens/pull/10); `models/document.py`, persistence adapter and migrations. No hash, extraction run, or workspace ownership yet. |
| DONE-04 | DONE | Private local MinIO, bucket initialization, disposable PostgreSQL/MinIO integration services. | [PR #5](https://github.com/felipe0328/supplylens/pull/5); `compose.yaml`, integration tests. Not a deployed workspace-specific R2 setup. |
| DONE-05 | DONE | ObjectStorage port and S3-compatible adapter: signed PUT/GET URLs, HEAD, download to file object, and deletion. | [PR #6](https://github.com/felipe0328/supplylens/pull/6); `port/storage/storage.py`, `adapters/storage/storage.py`. Signed upload uses `If-None-Match: *` to protect existing bytes. |
| DONE-06 | DONE | Upload-intent, completion, metadata, download-URL, and delete API, controllers, schemas and tests. | [PR #7](https://github.com/felipe0328/supplylens/pull/7), [PR #8](https://github.com/felipe0328/supplylens/pull/8), [PR #10](https://github.com/felipe0328/supplylens/pull/10). Completion checks stored size and MIME; it does not yet validate PDF contents or page limits. |
| DONE-07 | DONE | ProcessingJob model, paired lease fields, timestamps, attempts, errors, and migration. | [PR #11](https://github.com/felipe0328/supplylens/pull/11); `models/processing_job.py`. Fields alone do not implement leasing or recovery. |
| DONE-08 | DONE | Upload completion enqueues a job in the document transaction; repeated completion reuses the existing job. | [PR #12](https://github.com/felipe0328/supplylens/pull/12); `controllers/documents/report_upload_completed.py`, job persistence port/adapter, transaction tests in `routes/v1/documents_test.py`. Current enqueue returns any existing job for a document; it does not support versioned reprocessing or separate indexing jobs. |
| DONE-09 | DONE | Changed-file CI/hooks, backend coverage gate, migration/storage integration tests, and version automation. | `.github/workflows/quality.yml`, `.pre-commit-config.yaml`, `scripts/check_coverage.py`. Backend coverage target is currently 100%; do not lower it to accommodate new code. Backend static type checking and a full product-flow test are not yet implemented. |

### 2.1 Existing HTTP contracts: keep these working

| Method and route | Current behavior |
| --- | --- |
| `GET /health` | Process liveness; no DB required. |
| `GET /api/v1/health/ready` | DB readiness; 503 when unavailable. |
| `POST /api/v1/documents/uploads` | 201 with document ID and direct-upload instructions. No multipart API upload. |
| `POST /api/v1/documents/{id}/complete` | Verify stored metadata, mark uploaded, enqueue/reuse one job; return document metadata. |
| `GET /api/v1/documents/{id}` | Read non-deleted document metadata and processing state. |
| `POST /api/v1/documents/{id}/download-url` | Short-lived signed URL for an uploaded document. |
| `DELETE /api/v1/documents/{id}` | Soft-delete metadata and remove stored bytes. Later retention work must protect linked evidence. |

Current upload and processing states are distinct. Processing uses `PENDING`, `PROCESSING`, `PROCESSED`, `FAILED`; none means a purchase was human-confirmed. Job states are `PENDING`, `PROCESSING`, `SUCCEEDED`, `FAILED`. Keep existing response fields compatible; add explicit extraction support and review information through migrations and schemas rather than silently redefining `PROCESSED` as “reviewed.”

### 2.2 Known gaps, not completed features

- No PDF library, extraction adapter, stored page evidence, parser, draft editing, or confirmation flow.
- No worker entry point, atomic claim, heartbeat, expired-lease recovery, retry schedule, or job HTTP endpoint.
- No PostgreSQL concurrent-completion test proving the current enqueue lock works under competing requests.
- The job model starts `attempts` at 1 before execution. It has no job kind, pipeline version, lease generation, or next-attempt time.
- No authoritative SHA-256, exact-content duplicate detection, actual-byte/page/time limits, or orphan reconciliation.
- No supplier, purchase revision, catalog, policy, estimate, report, search, or assistant implementation.
- No authentication, workspace memberships, workspace-scoped data, or per-workspace storage credential resolution.
- Existing upload integration tests use short synthetic bytes with a PDF header, not a complete parseable PDF. Keep those tests for upload semantics; use real generated synthetic PDFs for extraction tests.

## 3. Implementation boundaries and shared contracts

Use the existing layer-oriented package; do not move the whole backend merely to match the architecture's illustrative folders. Paths below are relative to `apps/backend/src/supplylens/` unless another root is stated. Proposed files are created by their owning task, not all at once.

| Layer | What belongs here | Example |
| --- | --- | --- |
| `routes/v1/`, `schemas/` | HTTP validation, dependency wiring, response mapping, HTTP error translation. | `routes/v1/jobs.py`, `schemas/jobs.py` |
| `controllers/<feature>/` | One application action per module; coordinate ports and domain logic. | `controllers/job_processing/process_document.py` |
| `domain/` | Typed evidence/results, validation, status rules, matching and deterministic calculations. No HTTP/ORM/provider dependencies. | `domain/extraction.py`, `domain/parsing/`, `domain/policies/` |
| `port/<capability>/` | Typed protocols for storage, persistence, PDF extraction, embeddings, and optional LLM operations. | `port/pdf_extraction/pdf_extraction.py` |
| `adapters/<capability>/` | SQLAlchemy queries, pdfplumber, S3, local embedding model, provider SDK integration. | `adapters/pdf_extraction/pdfplumber_extraction.py` |
| `models/`, `alembic/` | Persisted representations, constraints, indexes, and schema evolution. | `models/extraction_run.py` |
| `worker/` | Polling, dependency construction, job claim, heartbeats, bounded execution, retry orchestration, shutdown. | `worker/__main__.py`, `worker/runner.py` |

The intended flow is:

```text
complete upload -> committed pending job
worker claims job -> processing controller loads metadata and stored PDF
PDF adapter -> versioned raw page text and tables
deterministic parser + validator -> candidates and findings
persistence -> reviewable draft, never a confirmed purchase
human edits/confirms -> immutable purchase revision
```

The PDF adapter reads evidence. It does not interpret purchase status, persist results, or call an LLM. The controller coordinates. The worker owns the job transport and execution lifetime. Optional LLM adapters later add separately labeled suggestions; they do not replace raw evidence, deterministic results, or user corrections.

### 3.1 Common data rules

- Use UTC, timezone-aware timestamps. Use one-based source page numbers. Bounding boxes include their page coordinate system; omit them when unreliable rather than inventing them.
- Money, rates, quantities, and weights are decimal strings in JSON, `Decimal` in logic, and reviewed `NUMERIC` columns in SQL. Currency and unit are explicit. Unknown is `null` or an explicit unknown marker, never zero.
- Every candidate has a stable ID, source kind, document/run/page reference, printed text, typed proposed value, and warning/confidence information. Do not invent a calibrated confidence score; an explicit uncertainty reason is acceptable.
- Suggested source kinds: `digital_parser`, `supplier_rule`, `llm_suggestion`, `user_entry`. A user's correction records actor, time, and reason/source where applicable.
- Named monetary components include merchandise, freight, handling, discount, tax, and printed grand total. Keep MSRP separate from net supplier unit price. Product, charge, and other rows are distinct.
- Purchase statuses are explicitly selected: `planned`, `ordered`, `purchase_recorded`. A supplier document label is not authorization to select a status.
- All new list APIs use a bounded `limit` and opaque cursor, with a stable tie-breaker such as `(created_at, id)`. All SQL uses bound parameters.
- New business errors return a stable code, short safe message, and field details when relevant. Use 422 for invalid values, 404 for missing or unauthorized objects, 409 for stale/conflicting actions, and 503 for unavailable dependencies. Preserve existing error responses unless a task explicitly migrates them.
- Controllers and persistence adapters do not hide transaction commits. The route or worker transaction boundary commits/rolls back. Downloading and parsing do not hold database row locks open.
- For idempotent business writes, persist a request receipt scoped by workspace + action + key, with a canonical payload hash and the created resource/version IDs in the same transaction. Same key/payload returns the original result; different payload is a 409. Do not expire receipts while a replay could create duplicate confirmed records. SL-BE-014 introduces this contract and later write actions reuse it.

### 3.2 Resolve these defaults before changing them

This board chooses implementable defaults, not a new product scope:

1. **Raw evidence:** `extraction_runs` plus `extracted_pages`, with typed/versioned JSONB for raw table evidence. Structured candidates are separate tables added later. Do not build a generic event-sourcing system.
2. **Replay:** One logical run per document + content hash + pipeline version. A failed retry continues/replaces incomplete work for that logical run; a new pipeline version creates a new run. Completed raw evidence and reviewed purchase history are never rewritten.
3. **Unsupported PDFs:** Image-only documents produce an explicit unsupported extraction outcome; the job succeeds at classification, not at extraction. Mixed PDFs keep usable digital pages and mark missing-page evidence for manual review. No OCR service or dependency is added.
4. **Lease safety:** Every claim has an increasing generation/token. Owner name alone is insufficient. Expired workers cannot commit outputs after another worker claims the job.
5. **Authentication/storage:** Synthetic development comes first. Real-data access requires verified identity, workspace membership, scoped persistence/search, and server-resolved private storage. No SaaS administration is required. Never infer authorization from a UUID.
6. **Conflicting source prose:** The MVP's older single-business paragraph is narrower than its updated privacy section and the architecture's workspace rules. Build a small shared-workspace ownership model and isolation, not a SaaS administration product. Authentication/storage decisions need an ADR, not a silent scope downgrade.

Record a short ADR under `docs/decisions/` if implementation evidence requires changing a default. Change the affected task and its tests before implementing the alternative.

### 3.3 Terms used in the task cards

- **Port:** A typed interface describing what the application needs, without selecting a library/provider.
- **Adapter:** The implementation of a port using SQLAlchemy, S3, pdfplumber or another tool.
- **Lease:** A temporary right for a worker to execute a job; it expires unless renewed.
- **Fencing / execution receipt:** A checked job owner and claim generation. An old worker's receipt becomes invalid when the job is reclaimed, so it cannot save stale results.
- **Idempotent action:** Repeating the same request produces the same logical result, not another purchase/job/output.
- **Optimistic concurrency:** An edit names the version it read; if that version is no longer current, the server rejects the edit instead of overwriting newer work.
- **Provenance:** The record of where a value came from: PDF page, parser, model suggestion or human correction.
- **ADR:** A short architecture decision record explaining a choice, its evidence and its consequences.

## 4. Ordered waterfall summary

Dependencies in each card are the actual start conditions. Complete the phases in order for a simple solo workflow. Authentication can be moved earlier, but the real-data gate must never be skipped. Later tasks should not block the first useful synthetic slice.

| Phase | Tasks | Status | Checkpoint |
| --- | --- | --- | --- |
| A — Read and run one PDF | SL-BE-001–007 | TODO | Uploaded PDF reaches stored page evidence through a recoverable worker. |
| B — Review and record | SL-BE-008–016 | TODO | Digital or manually entered draft becomes one immutable purchase case. |
| C — Duplicate and later documents | SL-BE-017–019 | TODO | Matching evidence does not double count; differences require a new revision. |
| D — Catalog | SL-BE-020–022 | TODO | Product matches and name/SKU proposals remain human-reviewed. |
| E — Policies and estimates | SL-BE-023–026 | TODO | Safe policy produces a reproducible, explainable estimate. |
| F — Reports | SL-BE-027–028 | TODO | Currency-safe metrics reconcile to current reviewed revisions. |
| G — Search | SL-BE-029–032 | TODO | Keyword search works alone; local vectors/hybrid are measured additions. |
| H — Optional assistance | SL-BE-033–035 | TODO | Opt-in suggestions and cited answers cannot write business decisions. |
| I — Real-data safety | SL-BE-036–041 | TODO | Verified workspace access, private storage, retention and quotas. |
| J — Operate and verify | SL-BE-042–045 | TODO | Reproducible local services, measurements, recovery, and full backend acceptance. |

**Recommended next branch:** SL-BE-001. Then SL-BE-002 and SL-BE-003. This proves the processing behavior before building worker infrastructure; SL-BE-004–006 connect it to jobs already being enqueued.

## 5. Phase A — Read and run one PDF

### SL-BE-001 — Define extraction results and persist versioned page evidence

- **Status:** TODO
- **Depends on:** DONE-03, DONE-07
- **Branch:** `backend/sl-be-001-extraction-contracts`

**Goal:** Agree on what a PDF reader returns and where raw evidence lives before coupling extraction to a worker.

**Implementation:**
1. Add `domain/extraction.py` with typed page text, table/cell evidence, optional bounding boxes, page support outcome, warnings, extraction version, and overall outcome (`digital`, `partial`, `unsupported`). Keep raw text separate from proposed business fields.
2. Add `port/pdf_extraction/pdf_extraction.py`. Define a reader accepting a seekable binary stream and explicit limits, returning the typed result. Define provider-independent errors for invalid PDF, encrypted PDF without an allowed password workflow, page-limit breach, and unavailable extraction capability.
3. Add `models/extraction_run.py` and `models/extracted_page.py`, their migration, and persistence port/adapter. A run records document, authoritative content hash, pipeline version, outcome, timestamps, and sanitized error. A page records run, one-based number, text, support outcome, and versioned raw table payload.
4. Require unique `(document_id, content_sha256, pipeline_version)` for a logical run and unique `(run_id, page_number)` for pages. Enforce nonblank versions and positive page numbers. Keep document/run relationships consistent through FKs.
5. Extend document extraction-support state without making `PROCESSED` mean “confirmed.” Add the explicit unsupported state/outcome needed by the API. Review PostgreSQL enum upgrade/downgrade safety; do not silently reinterpret existing values.
6. Define a typed execution receipt carrying job ID, owner, lease generation and expiry for later fenced writes. It is a contract only; claiming jobs is SL-BE-004.

**Tests:** DTO serialization of decimal-free raw evidence; invalid page/version inputs; model constraints; rollback on page-write failure; repeated logical-run insertion; clean PostgreSQL upgrade/downgrade/reupgrade and schema drift. Do not rely on SQLite for PostgreSQL enum behavior.

**Acceptance / after merge:**
- [ ] A controller can persist and reload synthetic page evidence without pdfplumber, HTTP, or a worker.
- [ ] Same-version replay cannot create duplicate runs/pages, and a different version retains the earlier run.
- [ ] Persisted raw evidence has an explicit schema version and no confirmed business values.

**Not included:** PDF reading, structured parsing, draft editing, LLM calls. **Rollback:** Revert code before removing new tables; preserve any evidence that must survive a downgrade.

### SL-BE-002 — Implement bounded digital PDF extraction with pdfplumber

- **Status:** TODO
- **Depends on:** SL-BE-001
- **Branch:** `backend/sl-be-002-pdfplumber-adapter`

**Goal:** Turn original PDF bytes into evidence while explicitly recognizing unsupported pages.

**Implementation:**
1. Add a Python 3.14-compatible pdfplumber dependency and lock it with `uv`; use [ADR 0001's existing compatibility evidence](decisions/0001-python-314-digital-pdf-compatibility.md) as the starting point and verify the selected locked version. Create `adapters/pdf_extraction/pdfplumber_extraction.py` implementing the extraction port.
2. Check PDF signature and parseability, encrypted-file behavior, actual page count, and configured limits. Do not treat MIME or `%PDF` alone as proof of a valid PDF. Keep original text, not only normalized text.
3. Read every allowed page's text, words/positions, and tables. Preserve row order and page context; record uncertainty for irregular tables instead of guessing cells or claiming exact coordinates.
4. Define and test what “usable selectable text” means. Classify image-only pages as unsupported; retain usable pages in mixed files and add a warning identifying pages requiring manual entry. Blank pages must not invent data.
5. Translate expected library failures to port errors. Close file/library resources on all paths. No storage calls, persistence, supplier logic, subprocess shell commands, or LLM SDK here.
6. Add generated image-only, mixed, encrypted, malformed and excessive-page test cases using synthetic data. Keep fixture tooling dependencies separate where feasible; do not regenerate all existing PDFs unnecessarily.

**Tests:** Existing fixture page counts/text/table locations; two-page fixture 07 retains page numbers; image-only and mixed outcomes; empty/malformed/encrypted bytes; page-limit rejection; closing resources after errors. Actual wall-clock enforcement is implemented in SL-BE-005, not by an uninterruptible thread timeout here.

**Acceptance / after merge:**
- [ ] A direct call reads fixtures 01 and 07 with no DB, storage, or LLM credential.
- [ ] Unsupported input is distinguishable from corrupt input and dependency failure.
- [ ] No supplier status, money interpretation, or human confirmation is inferred by the adapter.

**Not included:** OCR, purchase-field parser, worker execution. **Rollback:** Revert the adapter/dependency together; stored evidence from earlier runs remains readable.

### SL-BE-003 — Orchestrate one document-processing action

- **Status:** TODO
- **Depends on:** SL-BE-001, SL-BE-002, DONE-05, DONE-08
- **Branch:** `backend/sl-be-003-process-document-controller`

**Goal:** Implement `controllers/job_processing/process_document.py` so the workflow is directly testable before adding polling.

**Implementation:**
1. Accept a job ID/execution receipt and injected document, job, extraction-persistence, storage, and PDF-extraction ports. Resolve job → active uploaded document → server-selected object key. Do not trust caller-provided filenames, URLs, or storage credentials.
2. Use the existing `ObjectStorage.download_fileobj` into a bounded temporary file or spooled stream. Enforce actual downloaded-byte limits, not only HEAD metadata. If the existing downloader needs a bounded write wrapper, implement/test that wrapper without bypassing the storage port.
3. Compute authoritative SHA-256 while reading the stored bytes; persist hash/actual size with a migration. Rewind for the PDF adapter. Storage ETag is not the SHA-256. Preserve the original object.
4. Reuse the logical run for the same hash/version. Return the existing completed result on replay. Write raw pages, support outcome, page count and document processing result atomically, with an ownership-check hook that SL-BE-004 will enforce.
5. Classifying an image-only file is a successful job outcome with unsupported automatic extraction and manual-entry eligibility. Invalid/corrupt PDF is a permanent processing failure; temporary storage failure is retryable. Return typed outcomes/errors so the worker can decide job state.
6. Keep long downloads/extraction outside DB transactions. Only short result persistence is transactional. Never mark a job succeeded before its result transaction commits. Temporary files are removed on success, exception, or interrupted child cleanup.

**Tests:** Controller uses only injected ports; missing/deleted/not-uploaded document; storage outage; downloaded size differs from declared size; byte cap; computed hash; unsupported outcome; transaction rollback; repeated completed run; extraction error does not delete source bytes. Use an explicit test execution context, not an unauthenticated HTTP processing endpoint.

**Acceptance / after merge:**
- [ ] A synthetic uploaded document can produce stored page evidence through a direct controller invocation.
- [ ] Results and document state never partially commit, and failures preserve the source object.
- [ ] No worker loop, SQLAlchemy model, pdfplumber import, or provider credential leaks into the controller's business logic.

**Not included:** Claim implementation, job scheduling, business parsing. **Rollback:** Retain hashes/evidence; revert orchestration and document metadata changes only with reviewed migration notes.

### SL-BE-004 — Add atomic job claims, fencing, and lease recovery

- **Status:** TODO
- **Depends on:** SL-BE-001, SL-BE-003
- **Branch:** `backend/sl-be-004-job-leases`

**Goal:** Two workers can compete safely, and a crashed worker cannot permanently lose or later overwrite a job.

**Implementation:**
1. Extend jobs with kind, pipeline version, next-attempt time, maximum-attempt policy, progress step, and increasing lease generation. Add an append-only execution-attempt record keyed by job/generation, with start/end/outcome/error and retry-cycle identity. Initial kind is extraction. Migrate existing jobs to that kind/version. Set new pending jobs to zero actual attempts; document how legacy `attempts=1` rows are interpreted/backfilled.
2. Replace “any job for this document” lookup with an explicit logical identity, initially document + kind + version. Add a database uniqueness constraint and due-job index. Preserve repeated completion behavior; resolve uniqueness conflicts without aborting the surrounding transaction unexpectedly.
3. Add `claim_next_due_job`, `renew_lease`, and owned completion/failure methods to the job port/adapter. Claim pending/due or expired-processing jobs using a short transaction and `SELECT ... FOR UPDATE SKIP LOCKED`; skip deleted/not-uploaded documents. Use database time for expiry and due checks.
4. Claim increments attempts and lease generation, records owner/expiry/started time, and commits before work begins. A renewal must match job, owner, generation, processing state, and a still-valid lease. A completion must use the same guarded identity.
5. Enforce that raw-result commits from SL-BE-003 verify the receipt under the final transaction's job lock. Lost ownership rolls back all page/state/output changes. Reuse of an owner name cannot allow a stale generation to write.
6. Expired claims are recoverable within the attempt bound. Exhausted jobs receive a final safe error, not endless reclaiming. A soft-deleted document cannot publish outputs if deletion occurred during processing.

**Tests:** Real PostgreSQL: two claimers get different jobs; only one claims a single job; expired lease is reclaimed; not-yet-due job stays pending; heartbeat extends expiry; stale generation/expired owner cannot renew or commit; deletion during execution blocks output; concurrent upload completion still creates one logical extraction job. Inspect the upgraded constraints/indexes and migration drift.

**Acceptance / after merge:**
- [ ] A crash after claim leaves work reclaimable without manual SQL.
- [ ] Stale workers cannot create pages, change document state, or finish the replacement worker's job.
- [ ] Existing upload-completion response and idempotence stay compatible.

**Not included:** Polling CLI or retry HTTP routes. **Rollback:** Stop workers before downgrading lease schema; do not downgrade while claims are active.

### SL-BE-005 — Run a separate worker with bounded execution and shutdown

- **Status:** TODO
- **Depends on:** SL-BE-003, SL-BE-004
- **Branch:** `backend/sl-be-005-worker-runner`

**Goal:** Consume queued work in a separate process, without FastAPI background tasks or a message broker.

**Implementation:**
1. Add `worker/__main__.py` and `worker/runner.py`; expose `uv run python -m supplylens.worker` and a `--once` mode for one due job. Construct ports/adapters at this entry point, sharing the backend package with the API.
2. Add validated configuration for worker identity, poll interval, lease duration, heartbeat interval, maximum job duration, byte/page limits and attempts. Heartbeat interval must be comfortably shorter than lease duration. Inject clock/wait behavior for deterministic tests.
3. Keep claim and heartbeat orchestration in the parent process. Run download/extraction/controller work in a stoppable child process; create clients and DB sessions inside their owning process. Support Windows spawn as well as Linux; never pass live sessions or boto clients across processes.
4. Renew ownership while the child runs. On lost lease or deadline, terminate/join the child and do not permit unfenced outputs. Define memory/CPU limits for deployment and enforce a hard wall-clock deadline; a thread timeout that leaves parsing running is insufficient.
5. Commit job success only with persisted output. Catch unexpected exceptions at the worker boundary, sanitize them, and hand retry/permanent decisions to SL-BE-006. DB outage must not produce a busy loop or falsely report success.
6. On graceful shutdown, stop claiming new work; allow bounded completion or stop the child, leaving an explicitly recoverable lease. Use structured logs with IDs, kind, duration, attempt and outcome only.

**Tests:** Empty queue, one-shot mode, two sequential jobs, library exception, child timeout/termination, lost heartbeat, DB outage backoff, stop signal, temporary-file cleanup, and Windows-compatible child construction. PostgreSQL/MinIO test uploads a valid synthetic fixture and runs one worker job.

**Acceptance / after merge:**
- [ ] Upload completion followed by `--once` persists extraction evidence and finishes its job.
- [ ] API request latency does not include PDF processing.
- [ ] An indefinitely slow extractor can be stopped and its job recovered; no source PDF is removed.

**Not included:** Redis/Celery, arbitrary task plugin framework, deployment containers. **Rollback:** Stop the worker and retain queued jobs/results; API uploads remain durable.

### SL-BE-006 — Add bounded retries and job-status/manual-retry APIs

- **Status:** TODO
- **Depends on:** SL-BE-004, SL-BE-005
- **Branch:** `backend/sl-be-006-job-retries-api`

**Goal:** Make failures visible and recoverable without repeatedly processing permanent failures.

**Implementation:**
1. Define retryable errors (temporary storage/DB/provider availability) and permanent processing errors (invalid/encrypted/over-limit PDFs). Unsupported scanned input is not a retry error. Use stable domain codes and map them explicitly to the current integer error column or migrate it safely to documented string codes.
2. Schedule bounded exponential backoff, for example `min(base * 2^(attempt-1), cap)` with injected jitter. Add validated settings and tests; count a reclaimed crash as an execution attempt. Clear leases on retry scheduling and final failure.
3. Add `GET /api/v1/jobs/{id}` and a bounded document-job list such as `GET /api/v1/documents/{id}/jobs`. Return kind, version, state, progress step, attempts, next attempt, safe error and timestamps. Do not return private exception details or storage URLs.
4. Add `POST /api/v1/jobs/{id}/retry`. Only an eligible terminal failed job can start a new bounded attempt cycle; concurrent/repeated retry requests must not enqueue duplicate logical work. Preserve historical executions/audit metadata instead of hiding the prior failure by resetting counters silently.
5. Reject retry for succeeded, active, unsupported-only, or deleted-source work with a documented 409. A new pipeline version is a separate reprocess action, not a manual retry of an old version.
6. Add `POST /api/v1/documents/{id}/reprocess` selecting a server-approved pipeline version. Enqueue or return the unique document/kind/version job; reject caller-supplied executable code/configuration and deleted sources. Return 202 for newly scheduled work or the documented existing-job result on replay. Preserve earlier runs, corrections, purchase revisions and estimates; same-version completed work is reused rather than rewritten.

**Tests:** Backoff and maximum attempts; permanent versus transient outcomes; last error/timestamp preservation; failed final commit; HTTP 404/409/503; concurrent manual retries/reprocessing; unsupported pipeline version; job/document relation and pagination; reprocessing retains old output and reviewed corrections. Add repeatable REST Client examples under `apps/backend/tests/manual/`.

**Acceptance / after merge:**
- [ ] A user can inspect a failure and request an eligible retry without direct DB access.
- [ ] A temporary storage outage recovers; corrupt input stops at a final understandable failure.
- [ ] Retry does not create new purchases, duplicate extraction output, or unbounded processing.

**Not included:** SSE/WebSocket progress; polling is sufficient. **Rollback:** Disable new retry requests, stop workers, and preserve attempt history before schema rollback.

### SL-BE-007 — Harden ingestion and deletion around active jobs

- **Status:** TODO
- **Depends on:** SL-BE-005, SL-BE-006
- **Branch:** `backend/sl-be-007-document-lifecycle`

**Goal:** Close lifecycle races introduced when uploaded documents can actually be processed.

**Implementation:**
1. Review completion as one short transaction updating upload status and enqueueing extraction. Do not enqueue failed/not-uploaded/deleted documents. Repeated completion must preserve uploaded time and processing outcome, including a terminal job.
2. Make deletion invalidate pending/active work and block final output through the SL-BE-004 fence. Define how signed URLs already issued behave until expiry; deletion must never be described as instant revocation of a bearer URL.
3. Add a durable storage-deletion request or equivalent reconciliation record before deleting bytes, so storage and DB failure cannot silently disagree. Successful object deletion is idempotent. Do not delete original bytes just because extraction fails.
4. Add a bounded `GET /api/v1/documents` list with filename, upload state, processing/support outcome, latest job reference, timestamps and stable pagination. No bucket credentials, raw object keys, or indefinite URLs.
5. Update completion documentation to say metadata verification happens synchronously and PDF-content validation happens in the worker. Return/latest-link job information compatibly so clients can discover processing state.
6. Establish the hook for rejecting deletion of purchase-linked evidence; the actual retention rule arrives in SL-BE-040. Never postpone active-worker deletion tests until that phase.

**Tests:** PostgreSQL competing completion requests; complete versus delete; delete during download/extraction/final commit; storage deletion outage followed by replay; wrong MIME/size; invalid file accepted as uploaded but later failed by content validation; stable document list cursors.

**Acceptance / after merge:**
- [ ] No deleted document can acquire a new job or publish new results.
- [ ] DB/storage disagreements are visible and have a recoverable record.
- [ ] A client can list documents and follow status without rebuilding existing upload routes.

**Not included:** Global orphan sweeps, workspace quotas, real-data retention policy. **Rollback:** Keep deletion reconciliation records until processed; do not re-enable deleted data accidentally.

## 6. Phase B — Review and record

### SL-BE-008 — Store typed candidates and add a baseline deterministic parser

- **Status:** TODO
- **Depends on:** SL-BE-001, SL-BE-003, SL-BE-007
- **Branch:** `backend/sl-be-008-baseline-parser`

**Goal:** Convert raw page evidence into reviewable suggestions, without losing what the PDF actually printed.

**Implementation:**
1. Add `domain/parsing/` with a pure parser accepting the versioned extraction result. Return header candidates, row candidates, provenance and uncertainty; no SQL, HTTP, pdfplumber, LLM, or fixture-name routing.
2. Add `document_fields`, `document_lines`, and a draft/run relationship with persistence port/adapter and migrations. Candidate IDs are stable within the logical run. Store raw printed wording and proposed typed values separately.
3. Baseline fields: supplier name, descriptive document type, reference, date, currency; line code/description, purchased quantity/unit, net unit price, printed total; named document amounts. Unknown values remain explicit.
4. Recognize observable headings/labels and preserve source page/text location. Distinguish `product`, `charge`, `other`; preserve discounts and MSRP separately. A heading or fee label is not a product.
5. Wire parsing after raw extraction in the processing controller using a pipeline version that identifies both extraction and parser configuration. Commit valid raw evidence under the execution fence before the separately atomic candidate/finding write, so a parser failure retains source pages. Record separate raw/parsing step outcomes and manual-review eligibility; no silent partial success without warnings. Replays may reuse completed raw evidence but must not duplicate candidate writes.

**Tests:** Fixture 01 baseline fields/rows against `expected.json`; unknown layout yields partial candidates; ambiguous currency never guessed; printed strings and source IDs survive serialization; repeated parser run has no duplicate candidates; persistence rollback.

**Acceptance / after merge:**
- [ ] One digital invoice produces typed page-linked suggestions in the DB.
- [ ] An unfamiliar document can still be reviewed manually, with missing fields clearly identified.
- [ ] No candidate creates a supplier master record or confirms a purchase automatically.

**Not included:** All supplier layouts or arithmetic validation. **Rollback:** Retain raw runs; candidate-table rollback must not remove reviewed evidence once later phases reference it.

### SL-BE-009 — Add focused layout rules for difficult fixture scenarios

- **Status:** TODO
- **Depends on:** SL-BE-008
- **Branch:** `backend/sl-be-009-layout-rules`

**Goal:** Improve deterministic parsing where general rules are ambiguous, using observable layout markers.

**Implementation:**
1. Add a small rule registry with a typed match result, stable rule ID/version, priority and clear fallback. Select by labels/column structure/printed supplier markers, never file path, fixture ID, or expected answers.
2. Implement narrowly scoped rules for handling/MSRP (02), repeated headers and multipage rows (07), discount/shared fees (10), case packs and weight (11), and Spanish decimal-comma fields (12). Treat 03–06 as evidence for pre-order and later-document layouts, not automatic purchase linking.
3. Preserve purchased quantity versus sellable units, per-case versus per-unit weight, printed net price versus MSRP, and one-time document discounts versus already-discounted line prices. Ambiguous conversions remain warnings.
4. Keep the parser generic outside positively matched rules. A conflicting/partial match must not overwrite a higher-trust manual correction; rule output is only a new candidate set.
5. Record supported scenarios and known limitations; bump pipeline version when semantics change. Do not require 100% extraction accuracy before allowing review.

**Tests:** Expected candidate values/pages for 02, 07, 10–14; repeated page headings do not duplicate rows; decimal comma becomes canonical string; missing weight/currency stays missing; small heading changes exercise fallback; rule choice is recorded and deterministic.

**Acceptance / after merge:**
- [ ] Each supported fixture has a documented rule or general-parser path and known warnings.
- [ ] A charge, discount, pack note or MSRP cannot silently become a sellable quantity/net price.
- [ ] New layout support is added through one rule, not a growing controller conditional tree.

**Not included:** OCR, real supplier fixture publication, automatic relationship decisions. **Rollback:** Use the previous pipeline version; keep old run history.

### SL-BE-010 — Validate extraction shape and arithmetic without rewriting evidence

- **Status:** TODO
- **Depends on:** SL-BE-008, SL-BE-009
- **Branch:** `backend/sl-be-010-document-validation`

**Goal:** Explain missing or contradictory values before a user confirms them.

**Implementation:**
1. Add pure validation functions and a typed finding: code, severity, affected candidate IDs, safe explanation, relevant source pages and expected-versus-printed values.
2. Validate quantity/unit/amount shapes, unambiguous currency, line-role consistency, quantity × net unit price, merchandise subtotal, named fees/discounts/tax and printed grand total where evidence is sufficient.
3. Declare decimal tolerances and rounding assumptions explicitly. Do not validate an unknown formula as if it were known; report “cannot reconcile” rather than inventing tax, freight or discounts.
4. Save findings by run/draft version. Revalidate edited values without deleting original printed candidates or old findings. Distinguish blocking confirmation requirements from review warnings that can be acknowledged with a reason.
5. Wire findings into processing output and later draft APIs. Validation never adjusts a PDF total to make it match.

**Tests:** Fixture 14 emits separate line/document mismatch findings; 10 does not double-apply discount; 02 includes the charge once; 11 preserves quantity dimensions; 13 flags missing currency; tolerance boundaries, missing inputs, duplicate charge identities, negative discounts and rounding.

**Acceptance / after merge:**
- [ ] An incorrect printed total remains unchanged and is accompanied by a precise finding.
- [ ] Validation is deterministic and runs without a DB or external service.
- [ ] Every finding can be traced to a field/line and source page where available.

**Not included:** Policy cost calculations or human confirmation. **Rollback:** Keep old findings and their validator version; disabling validation must not silently bypass confirmation checks.

### SL-BE-011 — Expose editable drafts and manual entry with conflict protection

- **Status:** TODO
- **Depends on:** SL-BE-007, SL-BE-008, SL-BE-010
- **Branch:** `backend/sl-be-011-draft-review-api`

**Goal:** A person can correct a parser result or enter every required field when extraction is unsupported.

**Implementation:**
1. Add `GET /api/v1/documents/{id}/draft` and `PATCH /api/v1/documents/{id}/draft`, schemas, controllers and persistence. Return draft version, candidates, effective user selections, source references, findings and support outcome.
2. Use optimistic concurrency: patch includes `expected_version`; one transaction compares/increments the draft version and stores corrections. A stale patch returns 409 with safe current-version information.
3. Store corrections separately from extraction evidence with actor/time/source/note. Support field updates, row additions/removals/reclassification and explicit unknown date/weight. Manual rows have their own stable IDs; never fake a parser page reference.
4. Permit an empty manual draft for unsupported or failed extraction when the original is retained. Revalidate effective values on edits. Keep read-only original candidate values accessible.
5. Define a trusted local synthetic actor until SL-BE-036; never let an HTTP client select arbitrary actor identity. Reject production use of the synthetic actor once auth exists.
6. Make new-run evidence available without erasing user selections. If reprocessing conflicts with a correction, show competing evidence; do not auto-replace it. Publish sample request/response JSON and error codes.
7. Add bounded extraction-run list/detail access under `/api/v1/documents/{id}/extractions` so prior versions/outcomes and their page evidence can be inspected. Validate that requested run IDs belong to this document; page evidence is paginated/size-bounded and protected like the original PDF.

**Tests:** Read/edit, stale version, two competing editors, manual image-only draft, correction provenance, row lifecycle, invalid field types, DB rollback and new run arriving after a correction. No-LLM tests must cover the entire manual path.

**Acceptance / after merge:**
- [ ] A user can prepare a digital or scanned document for confirmation using only the API.
- [ ] Original extraction and human edits remain distinguishable and auditable.
- [ ] A stale edit cannot silently overwrite another user's work.

**Not included:** Frontend PDF viewer or purchase creation. **Rollback:** Preserve correction history; do not downgrade a schema that is referenced by confirmed revisions without export/recovery planning.

### SL-BE-012 — Add supplier records and explicit draft association

- **Status:** TODO
- **Depends on:** SL-BE-011
- **Branch:** `backend/sl-be-012-supplier-api`

**Goal:** Reviewed purchases can reference a stable supplier rather than an untrusted parsed name.

**Implementation:**
1. Add `Supplier` and optional reviewed alias/identifier records with migrations, persistence and domain validation. Keep parsed supplier wording on the document; master display names are separate.
2. Add create/list/read/update supplier routes under `/api/v1/suppliers`, with stable pagination and an expected version for mutable records. Validate names and identifiers; do not assume a country-specific tax ID format.
3. Let draft edits select an existing supplier or explicitly create one. Candidate normalization can suggest existing suppliers, but does not auto-merge records.
4. Define conservative duplicate-name handling and explicit alias uniqueness. Archive rather than deleting referenced suppliers. Prepare ownership fields/queries for SL-BE-037 without adding fake tenancy enforcement now.

**Tests:** Create/update/list; empty name/invalid identifiers; stale update; duplicate alias conflict; archived supplier behavior; selecting supplier does not erase printed wording; renamed supplier does not rewrite historical evidence.

**Acceptance / after merge:**
- [ ] A reviewed draft references a chosen supplier ID with the original printed name still available.
- [ ] Supplier creation is an explicit action, not a parser side effect.
- [ ] Referenced suppliers cannot disappear through an ordinary delete.

**Not included:** Supplier SaaS administration or supplier-system integrations. **Rollback:** Retain referenced suppliers or roll back dependent purchase features first.

### SL-BE-013 — Model purchase cases, immutable revisions and source links

- **Status:** TODO
- **Depends on:** SL-BE-011, SL-BE-012
- **Branch:** `backend/sl-be-013-purchase-models`

**Goal:** Establish the distinction between an uploaded document and the human-reviewed business record.

**Implementation:**
1. Add purchase case, revision, revision-line and document-link models, migrations and persistence contracts. A case points to one current revision; revision number is unique within the case.
2. A revision records explicit status, supplier, date or unknown-date marker, descriptive source document type, currency-qualified monetary components, actor/time and source draft version. Lines retain purchased/sellable quantities, units, original supplier text/codes and source candidate/correction IDs.
3. Make revisions and revision lines append-only at application boundaries. Provide no ordinary update/delete methods for published revisions. Current-pointer changes are version-checked transactions.
4. Enforce one active purchase-case association per document. A case may have multiple documents, but no document may count as a source for two active cases. Primary/supporting link roles are explicit.
5. Use `NUMERIC` with reviewed precision/scale for financial/quantity columns; reject unsupported overflow rather than truncating. No payment, receipt, inventory or sales tables.

**Tests:** FK/unique/check constraints, current pointer consistency, historical line persistence, monetary precision, rollback, and document-link uniqueness under concurrent inserts in PostgreSQL.

**Acceptance / after merge:**
- [ ] The DB can represent a planned, ordered or recorded case with immutable source-linked history.
- [ ] A later source link cannot inherently create a second counted purchase.
- [ ] There is no ambiguous single `total` or implicit currency conversion.

**Not included:** Confirmation routes or linking workflow. **Rollback:** Export/retain reviewed revisions; schema removal is not safe once real records exist.

### SL-BE-014 — Confirm a reviewed draft as one purchase case

- **Status:** TODO
- **Depends on:** SL-BE-010, SL-BE-011, SL-BE-012, SL-BE-013
- **Branch:** `backend/sl-be-014-purchase-confirmation`

**Goal:** Turn an explicit human decision into a transactionally complete first purchase revision.

**Implementation:**
1. Add `POST /api/v1/purchases`, request/result schemas and controller. Require document/draft ID, expected draft version, explicit business status and an idempotency key. Add the request-receipt model/migration/persistence implementing the shared idempotent-write contract; do not rely on an in-memory key cache.
2. Validate selected supplier, meaningful date or explicit unknown marker, currency for all included amounts, and reviewable product/charge rows. Enforce blocking requirements; unresolved nonblocking findings need documented acknowledgements rather than silent dismissal.
3. Lock/check the draft and document association in a short transaction; create the case, first immutable revision/lines and primary link; set current pointer and store trusted actor/time. All writes commit together.
4. Same key and same payload return the same case/revision. Same key with different payload returns 409. Different keys competing for the same document must not create two cases.
5. A pre-order requires explicit status; an invoice is not required to choose `purchase_recorded`. Manual entry can confirm an unsupported PDF. Unknown sellable quantity blocks only affected unit estimates, not valid purchase facts.
6. Add `GET /api/v1/purchases/{id}` with current revision, warnings and source references. Never create a policy estimate implicitly during confirmation.

**Tests:** All three statuses; manual confirmation; missing currency/status; stale draft; acknowledged findings; repeated/competing requests; failure midway leaves no case/partial revision; bill without invoice; unsupported document path; no provider key.

**Acceptance / after merge:**
- [ ] One explicit confirmation creates exactly one complete case/revision.
- [ ] Parser, worker and LLM code cannot invoke an implicit confirmation path.
- [ ] Case detail explains selected facts and their original document/manual sources.

**Not included:** Status inferred from document title, payment facts, calculations. **Rollback:** Disable new confirmation writes; retain created revisions and links before any downgrade.

### SL-BE-015 — Add revision history, explicit status changes and purchase browsing

- **Status:** TODO
- **Depends on:** SL-BE-014
- **Branch:** `backend/sl-be-015-purchase-history`

**Goal:** Correct a confirmed case without rewriting history and browse plans separately from purchases.

**Implementation:**
1. Add `POST /api/v1/purchases/{id}/revisions`, requiring expected current revision, reason and idempotency key. Copy selected facts into a new immutable snapshot; allow explicit field/line/status changes under the same confirmation rules.
2. Atomically create the revision, point the case at it, and append audit metadata. Stale current revision returns 409. A status promotion from planned/ordered to purchase-recorded is always explicit.
3. Add revision list/detail endpoints and `GET /api/v1/purchases` with supplier, date, status, currency and source-document-type filters. State unknown-date and timezone-boundary behavior. Stable pagination must not repeat/drop rows with equal timestamps.
4. Keep historical supplier wording, product selections and source links on each snapshot. A later master-record rename must not rewrite the snapshot.
5. Return clear current-versus-historical markers and revision IDs for downstream report/estimate consumers.

**Tests:** Old snapshot remains unchanged; competing status changes; repeat revision request; current list reflects new revision; unknown dates; mixed currency filter; stable pagination; document-type filter does not count support links as extra cases.

**Acceptance / after merge:**
- [ ] A user can inspect every prior decision and explicitly promote a plan/order.
- [ ] A new revision changes current facts only; earlier source-linked facts remain available.
- [ ] Browsing makes business status explicit and does not claim payment or stock receipt.

**Not included:** Automatic invoice precedence or reconciliation logic. **Rollback:** Retain history; returning to an earlier active revision is an explicit new reviewed action, not a destructive edit.

### SL-BE-016 — Prove the first useful backend slice end to end

- **Status:** TODO
- **Depends on:** SL-BE-001–015
- **Branch:** `backend/sl-be-016-review-flow-acceptance`

**Goal:** Verify the integrated workflow before adding catalog, policies or AI.

**Implementation:**
1. Add PostgreSQL/MinIO integration tests: create intent → PUT valid synthetic PDF → complete → worker once → read draft → correct/select supplier → confirm → retrieve source and history.
2. Add parallel scenarios for image-only manual entry and corrupt extraction failure followed by manual review where usable evidence permits it. No OCR or provider calls.
3. Use fixture 03 for a planned case; explicitly promote it through a new revision. Verify uploaded title alone never selects business status.
4. Test a crash/reclaim and repeated completion/confirmation at the real transaction boundaries. Assert exactly one logical output and case.
5. Add an executable API walkthrough/REST Client collection with setup, expected status codes, request versions, and cleanup restricted to disposable test resources. Correct implementation gaps only within this slice; split unrelated changes into new cards.

**Tests:** This card's integration suite plus existing unit/API tests. Run with external AI credentials absent. Record actual commands/results, not only manual screenshots.

**Acceptance / after merge:**
- [ ] A fresh developer environment can complete a digital and manual purchase case through public APIs.
- [ ] Original bytes, corrected facts, current revision and history reconcile.
- [ ] Phase B can be marked complete from an automated test, not from separate module claims.

**Not included:** Browser automation or reports that do not exist yet. **Rollback:** Revert acceptance tooling without changing application records; any behavior fix has its own rollback notes.

## 7. Phase C — Duplicate and later documents

### SL-BE-017 — Detect exact duplicates and suggest related documents

- **Status:** TODO
- **Depends on:** SL-BE-003, SL-BE-015, SL-BE-016
- **Branch:** `backend/sl-be-017-duplicate-suggestions`

**Goal:** Identify repeated content and likely related evidence without merging purchases automatically.

**Implementation:**
1. Index authoritative content hashes. Duplicate scope must become workspace-local in SL-BE-037; never reveal a hash match from another workspace. A client-supplied checksum is advisory only.
2. Because hashing currently happens after direct upload, retain both uploaded document records and record an explicit exact-duplicate relationship; do not claim the initial upload was deduplicated. Avoid deleting bytes needed by any source link. A later preflight upload optimization is separate work.
3. Add `GET /api/v1/documents/{id}/relationship-suggestions` returning exact-content matches separately from possible same-purchase matches. Return reasons and relevant evidence, not just a mysterious score.
4. For likely relationships, compare known supplier identity, printed reference/linked reference, date, currency and line identifiers/amounts. Missing values reduce certainty; a matching grand total or filename alone is insufficient.
5. Suggestions do not change case links, status, active revision or estimates. Add user dismissal/acknowledgement persistence if required to avoid repeatedly showing an already reviewed suggestion.

**Tests:** Reupload identical bytes; same name with different bytes; same totals but unrelated supplier; fixtures 03–04 and 05–06; missing currency; suggestion replay; duplicate attached to an existing case cannot create a second counted case through confirmation. Add cross-workspace tests in SL-BE-038.

**Acceptance / after merge:**
- [ ] A user sees exact duplicates and plausible relationships with clear reasons.
- [ ] A possible relationship never silently merges documents or purchases.
- [ ] Existing source bytes and confirmation history survive duplicate detection.

**Not included:** Automatic deduplication of immutable object storage. **Rollback:** Remove suggestions/relationship flags without unlinking confirmed case evidence.

### SL-BE-018 — Link supporting documents and produce a comparison

- **Status:** TODO
- **Depends on:** SL-BE-013, SL-BE-015, SL-BE-017
- **Branch:** `backend/sl-be-018-supporting-documents`

**Goal:** An invoice or later bill can support an existing case without becoming another purchase.

**Implementation:**
1. Add `POST /api/v1/purchases/{id}/documents` with document ID, expected current revision, explicit link intent and idempotency key. Enforce one active case per document and reject attempts to attach evidence owned by another case.
2. Add `GET /api/v1/purchases/{id}/comparison?document_id=...`. Compare selected candidate/draft values with an exact target revision; record comparison algorithm version and evidence run/draft version.
3. Align lines conservatively by reviewed supplier code or other reliable identifiers. Ambiguous matches stay unmatched; partial shipments, missing fields, discounts and rounding do not become guessed equivalence.
4. Return field-level categories: equal, changed, missing, extra, not comparable. Distinguish header date/reference changes from economic changes. Currency/unit incompatibility is explicit.
5. A match gets `matched_supporting_evidence`; economic differences get `needs_reconciliation`. Neither changes current facts, case status or historical estimates. Retain both originals and an audit link event.

**Tests:** Fixtures 03–04 match economic facts despite different labels/references; 05–06 show quantity and handling differences; unrelated document; missing fields; two competing case links; repeated link; matching attachment leaves current revision ID unchanged.

**Acceptance / after merge:**
- [ ] Both PDFs can be inspected as evidence for one case.
- [ ] Matching invoice attachment creates no new purchase or estimate.
- [ ] Differences are reviewable at field/line level before any fact changes.

**Not included:** Accepting differences or relinking between cases. **Rollback:** Preserve link/comparison history; do not delete supporting objects when reverting comparison code.

### SL-BE-019 — Reconcile selected differences and audit relinking

- **Status:** TODO
- **Depends on:** SL-BE-015, SL-BE-018
- **Branch:** `backend/sl-be-019-document-reconciliation`

**Goal:** Make later-document changes a deliberate new revision rather than a hidden overwrite.

**Implementation:**
1. Add `POST /api/v1/purchases/{id}/reconciliation` with expected revision, comparison ID/version, explicit accepted field/line changes, reason and idempotency key. Reuse the revision validation/service from SL-BE-015.
2. Refuse stale comparisons if either the current revision or supporting draft/run changed. Recompute for review; do not silently apply a newly calculated diff.
3. Create a complete new immutable revision, retaining selected source-field references from either document and unchanged fields from the previous snapshot. Reject implicit status promotion based on an invoice title.
4. Define an explicit relink action requiring source and destination case versions, trusted actor and reason. Record the old link as superseded instead of deleting it. Lock both cases in a consistent order and enforce one active association.
5. Do not move a primary source if doing so would leave confirmed facts without retained provenance; require an explicit reviewed replacement or return 409. Old revisions keep their historical source references even after a current link changes.

**Tests:** Selected versus rejected differences; fixtures 05–06; stale comparison; repeated reconciliation; concurrent revisions/relinks; prior estimate/revision unchanged; unmatched partial lines; old source links remain inspectable.

**Acceptance / after merge:**
- [ ] A mismatching invoice updates current facts only through a confirmed new revision.
- [ ] Relinking cannot create double counting or erase historical evidence.
- [ ] Every accepted change has actor, reason and selected source provenance.

**Not included:** Automatic reconciliation or invoice priority. **Rollback:** Preserve revisions and link history; correct an erroneous decision with another reviewed revision.

## 8. Phase D — Catalog

### SL-BE-020 — Add catalog products with stable identifiers

- **Status:** TODO
- **Depends on:** SL-BE-015, SL-BE-019
- **Branch:** `backend/sl-be-020-product-catalog`

**Goal:** Maintain store-facing products independently from supplier wording.

**Implementation:**
1. Add product model/migration/port/adapter with display name, SKU, category, optional normalized identifiers, version and archive state. Specify canonical SKU normalization and uniqueness; later scope it per workspace.
2. Add create/list/read/update routes under `/api/v1/products`. List supports bounded name/SKU/category filters; updates use expected version. Reject blank names, ambiguous identifier formats and conflicting SKUs with stable errors.
3. Archived products remain valid historical references; no hard deletion of referenced records. Keep product identity separate from mutable display labels.
4. Add nullable product association and snapshot display fields to revision lines without rewriting old supplier text. Existing unmatched lines remain valid.

**Tests:** CRUD, duplicate/case-normalized SKU, pagination, stale update, archive/reference protection, category filters, master rename leaves earlier revision snapshots unchanged, migration/backfill of unmatched lines.

**Acceptance / after merge:**
- [ ] A store product can be created and searched without changing any PDF evidence.
- [ ] Duplicate SKUs cannot pass through concurrent requests.
- [ ] Old purchase lines remain understandable after catalog edits.

**Not included:** Stock levels, sales, automatic creation from a parser. **Rollback:** Preserve referenced product identities; removing associations must not erase revision snapshots.

### SL-BE-021 — Suggest and explicitly accept product/supplier mappings

- **Status:** TODO
- **Depends on:** SL-BE-011, SL-BE-020
- **Branch:** `backend/sl-be-021-product-matching`

**Goal:** Repeated supplier lines can map to reviewed catalog products, with uncertainty visible.

**Implementation:**
1. Add supplier-product mapping records with supplier, normalized supplier code, product, trusted reviewer/time and version. Enforce one active reviewed mapping per supplier/code within its workspace.
2. Add `GET /api/v1/document-lines/{id}/match-suggestions`: reviewed supplier mapping first, then exact identifiers, normalized name and finally bounded fuzzy suggestions. Return match basis and ambiguity; never auto-accept fuzzy results.
3. Add `PUT /api/v1/document-lines/{id}/product` with expected draft version and chosen product or explicit unmatched state. Persist the reviewed decision and optionally a supplier mapping through an explicit flag.
4. Validate that the supplier, document line and product belong to the same ownership boundary once tenancy exists. Charge/other rows cannot become catalog products merely because their labels match.
5. For already confirmed facts, apply product changes through a new revision rather than modifying revision lines. Mapping updates affect future suggestions only.

**Tests:** Reviewed map outranks fuzzy match; exact code; ambiguous names remain unlinked; different suppliers reuse a code safely; charge exclusion; conflicting mapping; old revision snapshot; manual unmatch; stale draft update.

**Acceptance / after merge:**
- [ ] A user can accept/reject a suggested product link with a recorded reason/source.
- [ ] Reviewing one supplier-code mapping improves future suggestions without rewriting past purchases.
- [ ] Unmatched lines remain confirmable where other required facts are valid.

**Not included:** Autonomous catalog merging. **Rollback:** Retain reviewed mapping history; disable new suggestions without changing accepted historical links.

### SL-BE-022 — Suggest deterministic store names and SKUs

- **Status:** TODO
- **Depends on:** SL-BE-020, SL-BE-021
- **Branch:** `backend/sl-be-022-name-sku-suggestions`

**Goal:** Offer configurable store-facing labels, including Spanish templates, without relying on an LLM.

**Implementation:**
1. Define a small validated configuration schema for templates, normalization and controlled dictionaries. Keep private naming rules in private workspace configuration, not source code.
2. Add a pure suggestion function and preview action for selected draft lines/products. Return proposed name/SKU, rule/version, inputs and warnings for missing pieces or collisions.
3. Use safe placeholder substitution, not executable expressions or arbitrary Python. Bound template size and output length; document accent/case/separator behavior.
4. Acceptance goes through product create/update with uniqueness/version checks; preview alone never reserves or changes a SKU. User edits are allowed and remain explicit decisions.

**Tests:** Synthetic English/Spanish rules, accents, missing attributes, excessive template size, invalid placeholders, duplicate SKU proposals and race at acceptance; no provider credentials/calls.

**Acceptance / after merge:**
- [ ] The same inputs and rule version produce the same preview.
- [ ] Suggestions can be accepted/edited without exposing private dictionaries.
- [ ] SKU collisions are visible and cannot bypass DB uniqueness.

**Not included:** Private business templates in public fixtures or LLM product naming. **Rollback:** Disable preview; accepted product records remain valid.

## 9. Phase E — Policies and estimates

### SL-BE-023 — Define a bounded policy schema and validator

- **Status:** TODO
- **Depends on:** SL-BE-013, SL-BE-020, SL-BE-022
- **Branch:** `backend/sl-be-023-policy-contracts`

**Goal:** Describe configurable calculations safely before implementing execution.

**Implementation:**
1. Add `domain/policies/` with a versioned policy schema: named typed inputs, source (`purchase`, `manual`, `scenario`), unit/currency, required/range rules; approved steps; named outputs; explicit rounding.
2. Initial approved operations: bounded add/subtract/multiply/divide, percentages, allocation by declared nonnegative basis, explicit-rate currency conversion and rounding. Do not add arbitrary scripts, SQL, imports or `eval`.
3. Validate references, unique names, graph cycles, maximum inputs/steps/depth, dimensional compatibility, supported precision and output currency/unit. Zero denominators and invalid rates are errors.
4. Define allocation charge identity/category and usage rules to prevent the same source fee being allocated twice. Explain which charges remain unallocated.
5. Return structured validation findings with step/input IDs and safe explanations. Unknown data is not converted to zero. Add an ADR covering operation semantics and public synthetic policy examples.

**Tests:** Valid small graph; unknown refs; cycles; incompatible units/currencies; overflow/size bounds; duplicate charge usage; invalid rounding/rate; malicious expression text; missing optional input versus required input.

**Acceptance / after merge:**
- [ ] A synthetic policy has a typed validated representation independent of DB, HTTP and provider code.
- [ ] Unsafe/ambiguous graphs are rejected before evaluation.
- [ ] The representation can express the MVP pricing subset without publishing private formulas.

**Not included:** Policy persistence or actual money calculation. **Rollback:** Preserve schema-version metadata; do not reinterpret old definitions with new semantics.

### SL-BE-024 — Implement deterministic Decimal evaluation and trace

- **Status:** TODO
- **Depends on:** SL-BE-010, SL-BE-023
- **Branch:** `backend/sl-be-024-policy-evaluator`

**Goal:** Evaluate a validated policy reproducibly with visible assumptions and intermediate values.

**Implementation:**
1. Add a pure evaluator receiving validated definition and typed input snapshot. Use an explicit Decimal context, deterministic step order and declared rounding stages.
2. Record each step's operation, referenced values, result unit/currency, rounding adjustment, source input IDs and warnings. Output is labeled `complete`, `provisional` or `blocked` per affected result.
3. Missing FX, weight, quantity or tax treatment blocks dependent outputs unless the user supplies an explicit scenario assumption. Independent outputs may still complete. Never silently default a rate, fee or weight.
4. Allocate shared charges by a validated basis; distribute rounding remainder by a documented stable tie-breaker so shares reconcile exactly. Reject zero/negative invalid bases and duplicate allocation of a charge.
5. Keep source facts distinct from derived estimates. Selling-price output is not realized profit, and purchased case quantity is not automatically sellable unit quantity.

**Tests:** Operation boundaries, precision overflow, negative discounts, zero division, rate direction, allocation remainder/ties, double allocation, missing input dependency propagation, changed scenario and exact deterministic replay. Use invented amounts and no LLM.

**Acceptance / after merge:**
- [ ] One synthetic multi-line/fee policy produces traceable output with exact reconciliation.
- [ ] Identical definition and inputs produce identical serialized results.
- [ ] A missing weight blocks only dependent unit-cost outputs, not purchase confirmation or unrelated results.

**Not included:** Private policy examples or a free-form formula language. **Rollback:** Version evaluator semantics; retain old definitions/traces for existing estimates.

### SL-BE-025 — Persist policy drafts, preview and immutable publication

- **Status:** TODO
- **Depends on:** SL-BE-023, SL-BE-024
- **Branch:** `backend/sl-be-025-policy-api`

**Goal:** A user can configure, validate, preview and approve a policy without altering published history.

**Implementation:**
1. Add policy identity, mutable draft and immutable published-version records with schema/evaluator version, trusted publisher/time and definition hash. Draft edits use optimistic version checks.
2. Add policy create/list/read/edit, validate, preview and publish routes under `/api/v1/policies`. Publish requires expected draft version, validation success, explicit user approval and idempotency key.
3. Preview receives explicit reviewed revision/scenario inputs, returns evaluator trace and findings, and does not activate/persist a published policy accidentally. Validate no cross-policy/version confusion.
4. Published definitions are append-only. Editing starts/updates a draft; a new publication has a new version. Active-version selection is explicit and version-checked.
5. Enforce bounded definitions/input payloads at HTTP and domain levels. Do not log private policy content. Expose only safe synthetic examples publicly.

**Tests:** Draft conflicts; invalid publish; repeat publish; preview leaves active version unchanged; immutable old version; two concurrent publications; wrong input types; migration precision/version constraints.

**Acceptance / after merge:**
- [ ] A synthetic policy can be previewed and explicitly published through the API.
- [ ] Published versions cannot be mutated by the ordinary edit route.
- [ ] Every preview/publication identifies exact definition and evaluator versions.

**Not included:** Frontend guided editor or LLM policy generation. **Rollback:** Disable publication writes; retain published versions referenced by estimates.

### SL-BE-026 — Persist reproducible estimates tied to exact revisions

- **Status:** TODO
- **Depends on:** SL-BE-015, SL-BE-024, SL-BE-025
- **Branch:** `backend/sl-be-026-estimate-api`

**Goal:** Preserve what a calculation used, not merely its final price.

**Implementation:**
1. Add estimate/run and output persistence with FKs to exact purchase revision and policy version. Store input snapshot/provenance, manual assumptions, evaluator version, intermediate trace, outputs, warnings and creator/time.
2. Add `POST /api/v1/purchases/{id}/estimates`, `GET /api/v1/estimates/{id}` and a bounded case-estimate list. Request selects exact revision/policy version and explicit scenario inputs; idempotency key prevents duplicate request replays.
3. Permit planned/ordered cases to create clearly provisional estimates. Missing inputs produce blocked/provisional outputs with reasons; they do not prevent saving valid reviewed purchase facts.
4. Historical estimates are immutable. Changing a purchase, rate scenario, policy or evaluator creates another estimate. Listing clearly marks whether inputs match the case's current revision/active policy.
5. Persist financial output as decimal/currency-qualified values and preserve allocation charge lineage. Do not add a “paid” or “realized margin” field without actual future events.

**Tests:** Exact replay from persisted inputs; changed purchase/policy does not alter old result; plan label; missing input; idempotence/conflicting payload; output rounding/precision; referenced policy/revision cannot be deleted.

**Acceptance / after merge:**
- [ ] A saved estimate can be explained and replayed without accessing today's mutable configuration.
- [ ] Manual assumptions and document facts are distinguishable in the result.
- [ ] A plan's estimate cannot be mistaken for a recorded purchase amount or profit.

**Not included:** Automatic repricing on every edit. **Rollback:** Retain estimate snapshots and referenced versions; stop new estimates before schema changes.

## 10. Phase F — Reports

### SL-BE-027 — Build currency-safe purchase reports and drill-down

- **Status:** TODO
- **Depends on:** SL-BE-019, SL-BE-021, SL-BE-026
- **Branch:** `backend/sl-be-027-purchase-reports`

**Goal:** Summaries reconcile to human-reviewed cases, not the number of PDFs uploaded.

**Implementation:**
1. Add persistence queries and controllers for `/api/v1/reports/suppliers`, `/products` and `/unit-prices`. Read exactly one current revision per case; default to `purchase_recorded`. Plans/orders require separate explicit views.
2. Group monetary totals by currency. Converted views require explicit estimate/policy/rate provenance and are labeled estimates. Never aggregate raw unlike currencies.
3. Support supplier, product/category, date, business status and document-type filters with documented inclusive/exclusive date boundaries and unknown-date handling. Bound result sizes; add query indexes based on measured plans rather than speculative views.
4. Unit-price trends compare matching product/supplier/unit/currency bases. Case-pack versus single-unit prices need explicit comparable quantities; unmatched or unknown bases are excluded with a reason, not silently normalized.
5. Return counts and case/revision/line IDs or a drill-down link for every aggregate. Keep document order/invoice evidence views separate from purchase totals; supporting invoices never multiply case rows in joins.
6. Source factual amounts and policy cost/price estimates remain separate response fields. Use honest metric names, not cash-spent, stock, revenue or realized profit.

**Tests:** Two linked PDFs count once; changed current revision counted once; historical estimate unchanged; plan excluded by default; USD/EUR split; date/filter boundaries; unit incompatibility; archive/catalog rename; drill-down sum matches summary under stable transaction snapshot.

**Acceptance / after merge:**
- [ ] Every summary is explainable from a bounded list of current reviewed revisions.
- [ ] No supporting-document join double counts a purchase.
- [ ] Mixed currency and noncomparable units are visible, not hidden in a total.

**Not included:** Payments, stock, sales or forecasts. **Rollback:** Revert read APIs/indexes; do not change reviewed records to repair a report bug.

### SL-BE-028 — Expose an allowlisted read-only metric contract

- **Status:** TODO
- **Depends on:** SL-BE-027
- **Branch:** `backend/sl-be-028-approved-metrics`

**Goal:** Dashboard filters and future language assistance share the same safe server-owned calculations.

**Implementation:**
1. Add a registry of approved metric names, initially `confirmed_purchase_value`, `quantity_by_product`, and `unit_price_history`, each with typed allowed filters, grouping and currency/unit semantics.
2. Add `POST /api/v1/metrics/query`; validate metric/filter schema and bind caller scope server-side. Reject SQL, unknown metrics, unknown filters and oversized queries. Reuse report queries instead of implementing a second arithmetic path.
3. For ambiguous date/supplier/currency requests return a structured clarification or explicit breakdown. Bound maximum date range/rows and document defaults.
4. Response includes normalized request, source revision/drill-down references and semantic limitations. The metric execution interface exposes no purchase mutation or policy publication methods.

**Tests:** Known metric outputs equal corresponding report; unknown names/filters/SQL rejected; currency ambiguity; bounded range; no mutation; invalid product units; exact filter normalization and safe error messages.

**Acceptance / after merge:**
- [ ] Approved typed requests produce deterministic read-only results with traceable sources.
- [ ] Future LLM interpretation can only propose this contract, never a query string.
- [ ] Report and metric values cannot diverge through duplicate implementations.

**Not included:** Natural-language interpretation. **Rollback:** Disable metric endpoint; existing report APIs keep working.

## 11. Phase G — Search

### SL-BE-029 — Build versioned contextual passages and independent indexing jobs

- **Status:** TODO
- **Depends on:** SL-BE-004, SL-BE-006, SL-BE-008, SL-BE-028
- **Branch:** `backend/sl-be-029-search-indexing`

**Goal:** Index document evidence without making purchase review depend on search success.

**Implementation:**
1. Add search-passage model/migration with document/run, page, ordered passage number, original text, table-heading/row context, passage-builder version and full-text representation. Use unique logical passage identity.
2. Implement a pure passage builder: page/section boundaries and complete table rows with their headings. Bound passage size; do not split an amount away from its label or discard source context to hit a token count.
3. Add indexing job kind/version and scheduling after extraction results commit. Keep extraction and indexing outcomes separate; update enqueue's logical identity so an extraction job does not suppress an index job.
4. Index idempotently for one selected extraction version. New passage-builder versions write a new set and atomically switch the searchable selection. Old run evidence remains available; partial index failure does not publish a mixed set.
5. Unsupported pages have no invented text passages. Deleted/retained-access-restricted documents are removed from active retrieval. Do not erase a reviewable draft because indexing failed.

**Tests:** Passage text/page fidelity; table-heading context; long-row boundary handling; repeated indexing; failure halfway leaves previous index selected; independent retry; two kinds for same document; deletion/reindex race with lease fencing.

**Acceptance / after merge:**
- [ ] A digital document has stable contextual passages keyed to its run/version.
- [ ] Indexing outage leaves draft editing and purchase confirmation usable.
- [ ] Extraction and index jobs can coexist without duplicate or missing work.

**Not included:** Vectors or generated answers. **Rollback:** Stop index jobs and retain prior selected passage set; purchase workflow is unaffected.

### SL-BE-030 — Add exact-term/full-text search with source citations

- **Status:** TODO
- **Depends on:** SL-BE-029
- **Branch:** `backend/sl-be-030-keyword-search`

**Goal:** Useful document search works with no model or external credential.

**Implementation:**
1. Add a retrieval port/SQL adapter and `POST /api/v1/documents/search`. Request has query, optional selected document/supplier/date filters, bounded result limit and pagination where appropriate.
2. Use PostgreSQL full-text ranking plus an explicit exact-identifier path for punctuation-sensitive codes/references. Choose/test text configuration for English/Spanish rather than assuming stemming preserves every SKU.
3. Apply ownership and active-document filters before retrieval. Before SL-BE-038, all fixtures are synthetic; do not expose this endpoint to real workspaces without scoping.
4. Return passage ID, document ID/name, run/version, page, excerpt and ranking mode. Retrieval citations are source pointers, not proof that a generated claim is true.
5. Validate query length/filter combinations and use bound SQL parameters. Empty/no-evidence result is explicit. Bounded dependency errors leave reports/review available.

**Tests:** Exact SKU/reference, Spanish terms, handling-charge query, document/supplier/date restriction, no result, injection-looking query as inert text, source page validity and deleted-document exclusion. No embedding download/provider call.

**Acceptance / after merge:**
- [ ] A user can find a fee/product passage and open its original page.
- [ ] Keyword search works with AI settings absent and embeddings disabled.
- [ ] Search never calculates confirmed purchase totals from PDF wording.

**Not included:** Semantic search or free-form answers. **Rollback:** Remove read endpoint/index use without touching source evidence.

### SL-BE-031 — Add optional local embeddings and versioned vectors

- **Status:** TODO
- **Depends on:** SL-BE-029, SL-BE-030
- **Branch:** `backend/sl-be-031-local-embeddings`

**Goal:** Add semantic evidence retrieval as a measured local capability, not a required external service.

**Implementation:**
1. Define an embeddings port and local adapter. Evaluate Sentence Transformers with `multilingual-e5-small` as the documented first candidate; record model revision, dimension, normalization, query/passage prefixes and resource requirements.
2. Verify Python 3.14/library compatibility before selecting dependencies. If incompatible or too heavy, record an ADR and retain keyword search; do not silently downgrade Python or add a remote embedding provider.
3. Store vectors with passage/model/version/dimension identity using pgvector and migrations. Do not mix embeddings from different models in a similarity query. New model versions re-embed safely without deleting evidence.
4. Add independent embedding job kind/handler with bounded batch size, execution time and memory. Model installation/cache preparation is an explicit operator step; ordinary upload/tests must not download weights implicitly.
5. Model unavailable or embedding failure means keyword-only availability, not a failed purchase or unusable document. Expose safe embedding/index status separately.

**Tests:** Port with deterministic fake vectors; dimensional mismatch; model version isolation; replay/no duplicates; failed batch recovery; disabled/unavailable model fallback. Mark actual-model tests separately and run a measured opt-in synthetic smoke/evaluation.

**Acceptance / after merge:**
- [ ] Semantic vectors can be created locally with reproducible model metadata.
- [ ] Core tests and the purchase workflow run with weights absent.
- [ ] Reported RAM/runtime measurements justify the chosen model or document why it remains disabled.

**Not included:** Paid remote embeddings or claims of improved quality without evaluation. **Rollback:** Disable embedding jobs/retrieval; preserve keyword passages and model metadata.

### SL-BE-032 — Fuse keyword/vector results and evaluate retrieval

- **Status:** TODO
- **Depends on:** SL-BE-030, SL-BE-031
- **Branch:** `backend/sl-be-032-hybrid-retrieval`

**Goal:** Decide whether hybrid retrieval improves answers on the same labeled questions.

**Implementation:**
1. Add a retrieval service with keyword-only, vector-only and hybrid modes; filters and authorized scope apply to both paths before results are combined.
2. Implement documented Reciprocal Rank Fusion with bounded candidate counts, stable tie-breaking and passage deduplication. Do not combine incompatible raw ranking scores directly.
3. Preserve document/page/table context in final results. If semantic retrieval fails or is disabled, return keyword results with explicit fallback metadata rather than an empty/error result.
4. Add a synthetic question/evidence dataset for exact codes, synonyms, Spanish text, fees, missing evidence and document filters. Build a CLI comparing hit/recall-at-k, rank quality, citation validity, latency and memory on identical queries.
5. Publish aggregate outcomes and limitations. Keep hybrid optional if measured improvement does not justify resource use; an evaluation decision is a valid deliverable, not a reason to invent positive results.

**Tests:** Rank-fusion/tie/dedup behavior; exact-code preservation; filter parity; fallback; wrong-model rejection; expected page citations; deterministic evaluation report without raw private text.

**Acceptance / after merge:**
- [ ] Retrieval mode and fallback are visible to clients/operators.
- [ ] A repeatable report compares all available modes on the same safe dataset.
- [ ] No quality claim is made without recorded measurements.

**Not included:** LLM composition or an autonomous research agent. **Rollback:** Select keyword mode; retain evidence and evaluation artifacts.

## 12. Phase H — Optional assistance

### SL-BE-033 — Add opt-in, evidence-backed suggestions for uncertain fields

- **Status:** TODO
- **Depends on:** SL-BE-010, SL-BE-011, SL-BE-032
- **Branch:** `backend/sl-be-033-optional-field-assistance`

**Goal:** Help with difficult fields while preserving the complete deterministic/manual path.

**Implementation:**
1. Define a narrow LLM port for structured field suggestions, with typed relevant excerpts, requested uncertain fields, schema and provider-independent errors. Implement one adapter using the OpenAI Python SDK as the documented first provider; keep its API/version choices in the adapter.
2. Assistance is disabled by default. The trusted workspace/local synthetic setting explicitly enables it; a missing key or provider outage does not fail ordinary extraction, review or confirmation. Workspace secret resolution is completed in SL-BE-039.
3. Add `POST /api/v1/documents/{id}/suggestions`. Target one run/draft version; send only bounded relevant excerpts, not the whole PDF by default. Start with one bounded synchronous provider call and explicit timeout; return typed suggestions/status or safe disabled/unavailable errors. Only move it to a separate job in a later task if measured latency requires it; heavy PDF extraction never moves into the API.
4. Persist suggestions separately with source `llm_suggestion`, model/provider version, prompt/schema version, evidence refs, timing and usage metadata. Numeric suggestions are decimal strings and pass deterministic shape/arithmetic validation before being shown.
5. Do not overwrite original parser candidates, selected user corrections, or confirmed facts. Reject unsupported source references/extra fields; stale draft results become competing suggestions, not automatic edits.
6. Apply timeout, input/output token limits, call-count/cost bounds and sanitized provider error handling. Do not give the provider business-write tools, SQL execution or policy access. Treat instructions in supplier text as untrusted data.

**Tests:** Disabled path makes zero calls; fake provider valid/malformed response; invented currency/amount/source rejection; stale draft; existing user correction unchanged; timeout/outage; prompt-injection fixture cannot issue commands; bounded payload and no raw text in logs. Real-provider smoke is explicit, opt-in and synthetic.

**Acceptance / after merge:**
- [ ] Assistance produces separately labeled proposals that require human selection.
- [ ] Provider failure does not block manual completion or modify current purchase facts.
- [ ] Same-set evaluation can measure correction effort, cost and failure cases; no improvement is assumed.

**Not included:** Automatic approval, replacement of digital extraction, policy authoring or broad agent behavior. **Rollback:** Disable assistance; retain already reviewed provenance and existing suggestions as historical evidence.

### SL-BE-034 — Compose optional document answers with validated citations

- **Status:** TODO
- **Depends on:** SL-BE-032, SL-BE-033
- **Branch:** `backend/sl-be-034-cited-document-answers`

**Goal:** A generated answer is grounded in retrieved document passages and admits missing evidence.

**Implementation:**
1. Add `POST /api/v1/questions/document` and a narrow answer-composition port. Request includes question and allowed document/supplier/date scope; retrieve through the existing service before any generation.
2. Use a small optional LangChain retrieval-and-compose integration only if it helps the documented stack. Application code still owns filters, ranking, prompts, limits and citation validation. No repeated agent-invented searches or unrestricted tools.
3. Pass a bounded set of passages with server-issued citation IDs. Structured output includes answer/refusal, cited IDs and limitations. Validate that cited passages came from this authorized retrieval and still refer to available evidence.
4. Do not claim that citation-ID validation proves semantic truth. Evaluate whether each factual claim is actually supported; refuse or clearly limit unsupported answers. No evidence means no invented answer.
5. Disabled/unavailable LLM returns useful passages and explicit generation status. PDF wording questions do not compute purchase totals; route mixed requests to separate evidence/metric results or clarification.
6. Persist only the metadata/history justified by retention policy; do not log raw questions/excerpts by default. Show when external processing occurred and which model/version was used.

**Tests:** Fee question cites correct page; unsupported question refusal; nonexistent/foreign citation rejected; instructions inside a PDF are inert; provider outage returns passages; question/passage limits; purchase-total question is not answered by adding PDF amounts; English/Spanish safe examples.

**Acceptance / after merge:**
- [ ] Generated claims can be inspected alongside their actual PDF source passages.
- [ ] Without an LLM, the same route or documented fallback still exposes retrieved evidence.
- [ ] Optional composition cannot mutate purchases, policies or index state.

**Not included:** Open-ended research agents or uncited authoritative answers. **Rollback:** Disable composer; keyword/hybrid search remains available.

### SL-BE-035 — Interpret purchase questions into approved metric requests

- **Status:** TODO
- **Depends on:** SL-BE-028, SL-BE-033
- **Branch:** `backend/sl-be-035-metric-question-interpretation`

**Goal:** Natural language is an optional input method for server-defined metrics, not a source of calculations.

**Implementation:**
1. Add `POST /api/v1/questions/purchases` and a narrow metric-interpretation port. Provide only approved metric/filter definitions and minimal authorized lookup context; no arbitrary schema dump or raw purchase database access.
2. Provider output is either a schema-valid metric request or clarification. Validate names, dates, currency, supplier/product resolution and bounds through SL-BE-028; inject workspace scope on the server, never accept it from model output.
3. Execute the same read-only metric service as dashboard filters. Return normalized interpreted request, deterministic result/drill-down and clarification/limitations. The LLM never adds prices or changes the numeric result.
4. Explicitly reject generated SQL, unsupported inventory/payment/profit metrics, unknown entities and write intents. Ambiguous “spent” or unclear month/currency requires clarification or honest purchase-value terminology.
5. Without a key/provider, approved metric requests and reports remain usable. A language-interpreter outage is not a metrics outage.

**Tests:** Labeled questions map to approved requests; ambiguity clarification; invented metric/entity; injected SQL/write request; foreign scope; typed filter rejection; numeric result identical to direct metric call; provider failure.

**Acceptance / after merge:**
- [ ] An accepted language request runs only an allowlisted read-only query.
- [ ] Every numeric answer comes from deterministic reviewed-record queries.
- [ ] No model response can approve a purchase or publish a policy.

**Not included:** General analytical SQL generation or future-domain facts. **Rollback:** Disable interpreter endpoint; direct metrics/reports keep working.

## 13. Phase I — Real-data safety

**Hard gate:** Only synthetic development is allowed until SL-BE-036–041 and the operating/recovery requirements in Phase J are complete. An authenticated login alone is not sufficient: records, jobs, search and storage must share the same verified workspace boundary.

### SL-BE-036 — Establish trusted identity and secure API sessions

- **Status:** TODO
- **Depends on:** DONE-01; normally start after SL-BE-035, or move earlier
- **Branch:** `backend/sl-be-036-authentication`

**Goal:** Replace the synthetic actor with a verified operator identity without building custom password cryptography.

**Implementation:**
1. Write a short auth ADR before implementation. Recommended concrete baseline: standards-based OIDC authorization-code flow with PKCE through a maintained library/provider and server-side browser sessions. Select/document the provider and deployment origins; if this baseline cannot run locally, approve a documented alternative before coding. No homemade password hashing/token protocol.
2. Add login/start, callback, logout and `GET /api/v1/me` routes. Validate state/nonce, issuer, audience, approved algorithms, signature and expiry; bound JWKS/provider requests and fail closed. Never trust unverified token claims or a client-submitted actor ID.
3. Store user identity and revocable session records. Cookie settings must be HttpOnly, Secure in production and appropriate SameSite. Protect state-changing cookie-authenticated requests against CSRF, including credential/settings actions; validate redirect destinations against an allowlist.
4. Return minimal identity/session information. A login is not workspace membership. Keep liveness/readiness separately public where appropriate.
5. Local synthetic bypass is explicitly test/development-only and refuses production startup. Tests use trusted injected identity, not actual provider calls or production secrets. Do not expose a default password in a hosted environment.

**Tests:** Login callback validation, invalid/expired signature/issuer/audience, missing/incorrect state/nonce, logout/revocation, cookie flags, CSRF, provider outage, open redirect, synthetic bypass forbidden in production.

**Acceptance / after merge:**
- [ ] A signed-in operator has a trusted server-derived actor ID and a revocable session.
- [ ] Unauthenticated private actions are denied; login alone grants no foreign-record access.
- [ ] Auth choice and local setup are documented with no production credential committed.

**Not included:** SaaS billing/admin, custom password database, complete workspace enforcement. **Rollback:** Keep private services closed; never revert to anonymous real-data access to restore availability.

### SL-BE-037 — Add workspace ownership and migrate existing synthetic records

- **Status:** TODO
- **Depends on:** SL-BE-036 and all existing domain model tasks
- **Branch:** `backend/sl-be-037-workspace-ownership`

**Goal:** Every business-owned record has an unambiguous ownership boundary enforced by schema and repository contracts.

**Implementation:**
1. Add workspace and workspace-membership models with active membership and minimal operator permission rules. Use an explicit documented local synthetic workspace for existing development records; no public signup/admin product is required.
2. Add `workspace_id` to documents, suppliers, purchases/revisions, catalog/mappings, policies/versions, estimates, jobs/runs, passages/vectors, suggestions, audit/lifecycle records where needed. Derived records must not refer across workspaces.
3. Backfill in a staged migration: create synthetic workspace, assign existing records, validate relationships, then enforce non-null ownership. Document how a real installation supplies ownership before migration; never guess among multiple businesses.
4. Use composite ownership-aware FKs/unique constraints where practical to prevent cross-workspace references. Scope supplier identifiers, SKUs, idempotency keys and duplicate relationships to a workspace; reviewed global uniqueness assumptions need explicit migration.
5. Change persistence protocols to require a trusted workspace scope. Remove unscoped private `get_by_id`/mutation methods from ordinary application paths; worker scope is derived from the claimed job, not client input.

**Tests:** Backfill a populated synthetic schema; non-null/ownership/FK constraints; two workspaces reuse SKU/supplier codes safely; cross-workspace revision/source/product/policy links rejected; migration upgrade and drift; invalid ambiguous ownership blocks migration.

**Acceptance / after merge:**
- [ ] Every private row is owned directly or through an enforced ownership-safe relationship.
- [ ] Existing synthetic history survives the migration with the same source/revision identities.
- [ ] Repository contracts make accidental unscoped access difficult.

**Not included:** Trusting a workspace ID from a request as authorization. **Rollback:** Take a backup; ownership cannot safely be stripped while real workspaces share an installation.

### SL-BE-038 — Enforce membership on all HTTP, worker and retrieval paths

- **Status:** TODO
- **Depends on:** SL-BE-036, SL-BE-037, all implemented private APIs
- **Branch:** `backend/sl-be-038-workspace-authorization`

**Goal:** A member sees their business's shared records, and cannot discover another business's records.

**Implementation:**
1. Resolve authenticated identity and active workspace membership in a central dependency. Verify membership even if the request chooses a workspace; never treat UUID possession or an object-key prefix as authorization.
2. Apply trusted scope to every document upload/complete/read/list/delete/download URL, job/status/retry, draft, supplier, purchase/revision/link, product/mapping, policy, estimate, report, metric, search and question action. Keep a route-by-route authorization checklist in the PR.
3. Unauthorized private object IDs return indistinguishable 404 responses where appropriate; unauthenticated requests return 401. Permission failures must not reveal foreign filenames, hashes, counts, citations or timing-dependent lookup details unnecessarily.
4. Worker claims bind job/document/workspace ownership and build scoped adapters. Both keyword and vector retrieval filter before returning/ranking visible results; LLM prompts receive authorized excerpts only.
5. Audit trusted actors on confirmation, revision, mapping, policy publication, linking and retries. Membership revocation blocks new requests; server sessions and cached permission data must not prolong access indefinitely.

**Tests:** Parameterized two-workspace authorization matrix across all route groups; member sharing within one workspace; foreign IDs/filters/job IDs/citations/idempotency keys; revoked membership; search/metrics counts do not leak; worker cannot load a document under the wrong scope; no anonymous signed URLs.

**Acceptance / after merge:**
- [ ] There are no ordinary private routes using unscoped persistence or caller-selected actor identity.
- [ ] Both read and write cross-workspace attempts fail without leaking record details.
- [ ] The same ownership boundary applies to DB facts, PDFs, search and assistant context.

**Not included:** SaaS administration. **Rollback:** Disable private traffic if enforcement is unavailable; never fall back to global unscoped access.

### SL-BE-039 — Resolve private storage and provider secrets per workspace

- **Status:** TODO
- **Depends on:** SL-BE-037, SL-BE-038, DONE-05
- **Branch:** `backend/sl-be-039-workspace-storage`

**Goal:** API and worker use each business's approved private storage configuration, not one global production bucket.

**Implementation:**
1. Add workspace storage settings with approved provider/endpoint, private bucket, region, key prefix and secret reference. Store credentials in a secrets manager or protected equivalent, not plaintext application columns. Write an ADR selecting the local and hosted secret-resolution mechanism.
2. Define server-side storage-client/secret resolver ports. Build the S3 adapter using the document's workspace configuration for signing, HEAD, download and delete. Shared MinIO configuration is synthetic-development-only.
3. Store authoritative bucket/object-key or opaque storage-config revision references for each original; do not recompute a historical object's location from today's settings. New keys use `workspaces/{workspace_id}/documents/{id}/original.pdf`; migrate legacy keys through an explicit location/backfill plan without losing sources.
4. Validate endpoint/provider configuration to avoid SSRF and unsafe credential forwarding: approved HTTPS production endpoints, restricted local MinIO exception, bucket/key rules and server-controlled credentials. Cache clients by workspace/config revision, not merely bucket name.
5. Expose a minimal authorized settings/verification action for designated workspace operators. Write-only secret installation/rotation returns no secret value; validate access using a dedicated safe test object and remove only that test object.
6. Signed URLs remain short-lived bearer capabilities. Preserve immutable conditional PUT behavior and verify R2 support with a dedicated synthetic test bucket. Resolve optional LLM credentials the same way, with explicit workspace opt-in; never use one workspace's provider key for another.

**Tests:** Two workspace configurations/buckets/client caches; key isolation; historical location after config rotation; missing/revoked secret; unsafe endpoint rejection; no credential returned/logged; presigned expiry/conditional replacement; opted-in R2 smoke with synthetic data only.

**Acceptance / after merge:**
- [ ] API and worker reach the same authorized original using workspace-owned storage settings.
- [ ] Rotation or a second workspace cannot redirect old documents to the wrong bucket.
- [ ] No browser payload, DB plaintext credential or log exposes provider/storage secrets.

**Not included:** Public buckets or guaranteed zero-cost hosting. **Rollback:** Keep previous config revisions and secret references available for retained objects; never move/delete originals as an implicit downgrade.

### SL-BE-040 — Complete audit, privacy, retention and safe deletion rules

- **Status:** TODO
- **Depends on:** SL-BE-019, SL-BE-025, SL-BE-038, SL-BE-039
- **Branch:** `backend/sl-be-040-audit-retention`

**Goal:** Keep business decisions traceable and avoid deleting the evidence behind confirmed history.

**Implementation:**
1. Standardize append-only audit events for confirmation/revision, product mapping, policy publication, linking/relinking, manual retry, settings/secret changes and retention actions. Record trusted workspace/actor, action, resource/version IDs, time, request ID and reason; no raw document/policy content or credentials.
2. Audit business writes in the same transaction as the decision. Worker/system events use explicit system identity plus job/generation. Add bounded authorized audit access with minimal safe fields.
3. Choose/document a retention ADR before real-data use. Safe default: ordinary delete rejects purchase-linked PDFs/required provenance with 409; archive hides them from ordinary lists while preserving authorized historical source inspection.
4. Define a separately authorized permanent-retention action only if required by the approved policy. It must account for document objects, extracted text, passages/vectors, suggestions, session/question history and backups, with legal/business retention conflicts explicit. Do not casually implement cascading deletion of immutable purchase history.
5. Complete durable deletion/reconciliation behavior from SL-BE-007. Immediately stop access/jobs/retrieval as dictated by the retention state, then remove permitted objects idempotently; record failure and recovery. Previously issued URLs may survive until TTL expires.
6. Add log redaction tests and a documented inventory of private data locations, external-provider exposure, retention periods and operator permissions.

**Tests:** Audit atomicity; no fabricated actor; linked-source delete denied; archive preserves history; eligible unlinked deletion replay after storage outage; index exclusion; retention permissions; logs do not contain PDF text, price/policy payload, URLs or keys.

**Acceptance / after merge:**
- [ ] Every significant human/system decision has a safe, trustworthy audit event.
- [ ] Ordinary deletion cannot silently orphan a confirmed purchase's evidence.
- [ ] Retention behavior is explicit, tested and compatible with immutable history.

**Not included:** A generic event-sourcing framework or automatic destructive purges. **Rollback:** Preserve audit/retention records; never make hidden data publicly visible when reverting code.

### SL-BE-041 — Enforce quotas and reconcile abandoned uploads/orphan objects

- **Status:** TODO
- **Depends on:** SL-BE-007, SL-BE-039, SL-BE-040
- **Branch:** `backend/sl-be-041-storage-quotas-reconciliation`

**Goal:** Bound storage/process abuse and recover direct-upload partial failures safely.

**Implementation:**
1. Add configurable workspace soft/hard storage limits, maximum in-flight uploads, per-document bytes/pages and bounded queued work. Reserve declared bytes atomically when creating upload intent; include outstanding reservations so parallel intents cannot bypass quota.
2. Track reservation expiry, actual stored size and lifecycle state. Completion/worker validation settles actual usage; rejected/abandoned upload cleanup releases reservations only when safe. Keep actual-byte validation even when signed Content-Length is present.
3. Add an operator/maintenance command with dry-run default to reconcile expired intents, missing objects, durable delete requests and orphan objects. Scope every operation to approved workspace bucket/prefix and an age grace period longer than active upload URLs/jobs.
4. Never delete unknown bucket objects broadly. A deletion candidate must have recorded ownership/lifecycle evidence or an explicitly reviewed orphan policy; skip active/recent uploads, retained source objects and live leases. A DB outage is not permission to sweep storage.
5. Rate-limit expensive public/private actions by trusted identity/workspace and bound concurrent worker execution. Record safe quota/lifecycle counters, not private filenames or pricing.
6. Document test-only versus production maintenance invocations and operator approval requirements for applying a dry-run plan.

**Tests:** Concurrent reservations reach but do not exceed quota; actual oversized bytes; abandoned intent grace period; expired signed URL; cleanup replay; active lease/referenced source skipped; wrong prefix/bucket rejected; DB/storage outage; no broad deletion when inventory is incomplete.

**Acceptance / after merge:**
- [ ] Concurrent direct uploads cannot exceed the declared workspace quota through reservation races.
- [ ] Partial upload/delete failures are inspectable and recoverable through a safe maintenance path.
- [ ] Cleanup cannot delete unrelated or retained business evidence.

**Not included:** A provider free-tier hard spending guarantee. **Rollback:** Disable cleanup application first; retain quota/lifecycle records and default to refusing unsafe new uploads.

## 14. Phase J — Operate and verify

### SL-BE-042 — Make API, worker and local services reproducible

- **Status:** TODO
- **Depends on:** SL-BE-005, SL-BE-039, SL-BE-041
- **Branch:** `backend/sl-be-042-backend-runtime`

**Goal:** A new developer/operator can run the backend processes with explicit setup and safe configuration.

**Implementation:**
1. Add documented worker Make targets and backend container/runtime definitions if needed. API and worker use the same locked package/image but separate commands/processes. Keep PostgreSQL/MinIO persistent development storage separate from disposable tests.
2. Provide a Compose profile or documented commands for backend API, worker, DB and storage. Explain browser-accessible versus internal S3 endpoints so signed URLs remain valid; do not silently change signatures by rewriting hostnames.
3. Migrations run as an explicit operation before compatible API/worker startup, not in every worker or under competing boot processes. Validate configuration and fail closed for missing production auth/workspace/secrets.
4. Bound CPU/memory, child-process count, job time, connections and restart behavior. Support graceful worker shutdown and avoid running as root where feasible. Secrets come from approved external configuration, never image layers.
5. Add `.env.example` entries only for new nonsecret settings/placeholders, and update operating instructions. Synthetic setup must not accidentally point at a real bucket/database.

**Tests:** Locked fresh install; container/build smoke where added; one valid synthetic upload through API/worker; DB/storage missing at startup; auth bypass rejected in production; restart recovers expired work; migration compatibility and graceful stop.

**Acceptance / after merge:**
- [ ] The documented local stack runs independently of a hosted provider or LLM account.
- [ ] API and worker can restart without losing committed uploads/jobs.
- [ ] Configuration distinguishes development, disposable tests and private production explicitly.

**Not included:** Choosing a hosting vendor before measurements or a frontend deployment. **Rollback:** Stop new runtime deployment and return to a compatible image/config; retain DB and objects.

### SL-BE-043 — Add static checking, safe observability and resource evaluations

- **Status:** TODO
- **Depends on:** SL-BE-032, SL-BE-035, SL-BE-042
- **Branch:** `backend/sl-be-043-quality-observability`

**Goal:** Measure correctness and resource use without leaking business data or relying on type annotations alone.

**Implementation:**
1. Add a backend static type-checker configuration and locked dev dependency, selecting/documenting one tool such as Pyright. Add a focused Make target and changed-backend CI job. Provider libraries stay behind typed adapter interfaces; record narrowly justified missing-stub exceptions rather than blanket ignores.
2. Add safe structured request/job correlation and operational counters: job kind/outcome/attempt, lease age, queue depth, duration, page count, dependency availability, index mode and optional provider usage. No raw PDFs, extracted values, policy content or signed URLs.
3. Add worker-health/queue inspection for operators without changing `/health` into a DB-dependent route. Do not claim worker availability solely because an API process is alive.
4. Add repeatable synthetic evaluation commands for extraction field accuracy/page provenance/warnings, correction count, retrieval quality, job time, peak RAM/CPU and optional provider cost. Separate deterministic fake-provider CI from explicit live-model measurements.
5. Publish aggregate results, exact environment/model/pipeline versions and known failure cases. Compare optional AI against the same deterministic baseline. Use measurements to write a hosting/resource ADR; no unconditional zero-cost claim.

**Tests:** Type-check affected package; metric label bounds; sensitive-log redaction; worker-heartbeat stale detection; evaluation fixtures/expected output; disabled embedding/provider behavior; stable safe report serialization.

**Acceptance / after merge:**
- [ ] CI checks backend types as well as syntax/lint/tests without reducing the existing coverage gate.
- [ ] Operators can distinguish a queued job, stalled lease and dependency outage safely.
- [ ] Published evaluation claims are backed by recorded synthetic measurements.

**Not included:** Logging private payloads for debugging or claiming AI wins from a single anecdote. **Rollback:** Disable new collectors/checks only with documented risk; retain safe historical evaluation evidence.

### SL-BE-044 — Back up database and objects and prove restoration

- **Status:** TODO
- **Depends on:** SL-BE-039, SL-BE-040, SL-BE-042, SL-BE-043
- **Branch:** `backend/sl-be-044-backup-restore`

**Goal:** A restored reviewed purchase still has its original evidence and exact calculation versions.

**Implementation:**
1. Document/run a coordinated backup procedure for PostgreSQL and private object storage with a manifest linking DB snapshot, object inventory/checksums, application/migration version and required configuration/secret references. Choose a quiesced or consistency-safe capture method explicitly.
2. Encrypt/protect backup artifacts outside Git/public CI; define operator access, retention and restore-point/recovery-time expectations. Backups must not contain plaintext provider credentials or require secrets to be copied into repository files.
3. Add a restoration verification command targeting a newly created isolated test DB/bucket only. Restore schema/facts/objects, validate source hashes and links, replay a saved estimate and inspect current/history reports.
4. Clear/reconcile restored active leases so workers cannot resume a foreign owner session blindly. Search indexes may be rebuilt from retained evidence; confirmed revisions and original objects cannot be substituted by generated summaries.
5. Test missing object, wrong hash and incompatible schema/version failures explicitly. Document rollback/restore sequencing before deployment and any retention deletion limitations involving backups.

**Tests:** Synthetic backup/restore into isolated resources; source-byte hash equality; purchase/revision/policy/estimate replay; no active stale owner; missing/tampered source raises failure; authorization survives restore; command refuses development/production target without an explicit reviewed operator procedure.

**Acceptance / after merge:**
- [ ] A completed restore drill reconstructs a source-linked purchase and reproducible estimate.
- [ ] Backup locations and operator procedures are documented without private artifacts committed.
- [ ] Operational recovery does not require destructive trial-and-error on the development or production DB.

**Not included:** Automatic unapproved restore or broad bucket deletion. **Rollback:** Keep known-good backups/manifests; reverting tooling must not remove the recovery evidence.

### SL-BE-045 — Run final backend acceptance and publish the remaining UI handoff

- **Status:** TODO
- **Depends on:** All preceding tasks, or an explicitly approved deferral with no weakened safety invariant
- **Branch:** `backend/sl-be-045-backend-mvp-acceptance`

**Goal:** Verify the whole backend and state clearly what is still needed for the product MVP.

**Implementation:**
1. Extend the automated PostgreSQL/MinIO/API/worker acceptance suite: upload → extraction → correction/manual entry → supplier/product review → confirmation/revision → related-document comparison → policy publication/estimate → report drill-down → document search.
2. Run the core flow with external AI credentials absent and local embeddings disabled. Add separate optional-assistance tests with deterministic provider fakes; live-model quality/cost is evaluation evidence, not a CI prerequisite.
3. Cover fixtures 01–14 present in the fixture map, not missing numeric filenames 08/09. Explicitly test pre-order exclusion, bill/invoice single counting, changed quantity/fee reconciliation, mixed currency, handling/MSRP, packs/weight, missing currency and bad printed totals.
4. Repeat key flows across two workspaces, including signed URLs, jobs, search, metrics, provider settings, retention and idempotency. Test worker crash/timeout/storage outage, stale editors and backup restoration at real boundaries.
5. Finalize OpenAPI schemas/examples, cursor/error/version contracts, developer commands and a frontend handoff describing review/progress/confirmation/product/policy/report/question APIs. Keep API-contract testing distinct from browser end-to-end testing.
6. Update this board's completed evidence and list genuinely deferred work. A task may be deferred only by explicit scope decision; no incomplete security or deterministic calculation rule is hidden behind “MVP.”

**Tests:** Unit/API coverage gate, static checking, PostgreSQL/MinIO integration/migrations, full backend acceptance, safe restore drill and repeatable evaluation commands. Record all actual results and any excluded opt-in model/provider checks.

**Acceptance / after merge:**
- [ ] The backend's complete core purchase workflow passes with no AI services.
- [ ] Optional AI cannot change confirmed facts or execute arbitrary queries/policies.
- [ ] Source provenance, immutable history, currency safety and workspace isolation hold end to end.
- [ ] The remaining browser workflow is explicitly handed off; backend completion is not misreported as full product/browser MVP completion.

**Not included:** Browser implementation, payment/stock/sales domains or a public demo with private data. **Rollback:** Revert acceptance tooling safely; behavior changes require their own data-aware rollback plan.

## 15. Verification commands and safe working procedure

Commands below describe the reviewed `main` baseline. Tasks that introduce new commands must update this section. Future `worker`/type/evaluation commands are deliverables, not commands that already exist.

| Check | Current command and scope |
| --- | --- |
| Locked backend install | `uv sync --project apps/backend --locked` |
| Backend syntax | `make be-check` |
| Backend lint/format | `make be-lint` |
| Unit/API tests with current coverage gate | `make be-test` |
| Focused Python test | From `apps/backend`: `uv run pytest src/supplylens/<feature>/<module>_test.py` (replace placeholders with the actual path). Run broader coverage before merge. |
| PostgreSQL/MinIO integration | `make be-test-integration`; it starts disposable services and runs `pytest -m integration tests/integration`. |
| Create migration | `make db-revision msg="Describe the schema change"` — the actual Make variable is lowercase `msg`. Inspect generated SQL/Python before applying. |
| Apply/check migrations | `make db-upgrade`, `make db-check`; select the intended database explicitly first. |
| Migration safety test | `uv run --project apps/backend pytest -m integration apps/backend/tests/integration/test_migrations.py`; requires the disposable test DB to be running. |
| Version automation tests | `make version-test` |
| Changed-file hooks | `pre-commit run --files <exact changed paths>` |
| Broad repository gate | `make check` — includes frontend lint/build; relevant when shared setup/contracts change. |

Use `.env.example` to configure local synthetic services; never commit `.env`. Integration tests require a disposable DB whose name ends in `_test`; PostgreSQL-specific tests must not target development data. Test cleanup commands remove disposable services/volumes: run them only for the corresponding test environment. Do not combine schema-resetting migration tests with unrelated tests in parallel against the same DB.

For each branch:

1. Confirm a clean/understood worktree and read the card's dependencies. Preserve unrelated staged/unstaged work.
2. Copy the card's goal, scope and acceptance criteria into the PR draft. Agree on any unresolved ADR before implementation.
3. Add focused failing behavior tests, then implement contracts/domain logic/adapters/wiring. Add schema only when this card needs it.
4. Run applicable checks, inspect migration drift, and perform the documented synthetic manual scenario. Record environment limitations honestly.
5. Review privacy, no-LLM behavior, transaction/lease/version rules and rollback risk.
6. Update the card's status/evidence only when the PR actually merges. Staging, committing, pushing and merging still require the developer's explicit direction under repository rules.

## 16. Decisions, exclusions and board maintenance

### 16.1 Decisions that need recorded evidence

| Decision | Owning task | Required record |
| --- | --- | --- |
| Usable text/page/byte/time limits | SL-BE-002, SL-BE-005 | Limits, fixtures, measured runtime and unsupported-page behavior. |
| Legacy attempt backfill and lease generation | SL-BE-004 | Migration plan, due/expiry semantics and PostgreSQL concurrency proof. |
| Confirmation warning policy and unknown fields | SL-BE-010, SL-BE-014 | Blocking versus acknowledgeable findings and explicit unknown markers. |
| Supplier/layout rule versioning | SL-BE-009 | Match markers, fallback, supported fixtures and limitations. |
| Policy operations/precision/rounding | SL-BE-023, SL-BE-024 | Safe schema/evaluator semantics and synthetic reconciliation examples. |
| Local embedding compatibility/resources | SL-BE-031, SL-BE-032 | Pinned model/dependencies, fallback and same-set retrieval results. |
| Identity provider/session mechanism | SL-BE-036 | Auth ADR, local/production setup, trusted claims and CSRF/redirect controls. |
| Legacy ownership and object-key migration | SL-BE-037, SL-BE-039 | Explicit synthetic backfill, private-data ownership procedure and source preservation. |
| Secret store, retention and quota policy | SL-BE-039–041 | Approved operator access, safe deletion scope, reservation/cleanup rules. |
| Hosting and recovery objectives | SL-BE-043, SL-BE-044 | Measured needs, protected backup/restore procedure and drill evidence. |

### 16.2 Outside this board's MVP

- OCR for scanned PDFs; manual entry is the intended supported path.
- Payment collection/status, stock receipt, inventory balance, retail sales, forecasting, realized profit or accounting integrations.
- A message broker, separate domain microservices, general autonomous agent, unrestricted SQL or executable formula language.
- Multi-business SaaS administration/billing. This does **not** waive workspace ownership, membership verification or isolation.
- SSE/WebSockets before polling is shown insufficient; automated embedding/LLM dependence.
- Real supplier PDFs, private policy formulas/rates, credentials or identifiable customer data in Git, logs, tests, screenshots or public PRs.
- A guaranteed free hosting promise. Resource and provider limits require measurement and review.

### 16.3 Historical B0–B9 crosswalk

| Original package | New treatment |
| --- | --- |
| B0 foundation | DONE-01 and DONE-09; remaining static checking is SL-BE-043. |
| B1 upload/private bytes | DONE-03–08; remaining lifecycle/content/hash/quotas/security work is explicit in SL-BE-002–007, 017 and 036–041. |
| B2 worker/extraction | Split into SL-BE-001–010 so contracts, PDF reading, jobs and parsing are individually reviewable. |
| B3 review/revisions | SL-BE-011–016. |
| B4 authentication | SL-BE-036–039 with verified workspace isolation, not only a login endpoint. |
| B5 OCR/related documents | OCR removed as outside scope; supported manual path in SL-BE-002/011; linking/reconciliation in SL-BE-017–019. |
| B6 catalog | SL-BE-020–022. |
| B7 policies | SL-BE-023–026. |
| B8 reports/metrics | SL-BE-027–028. |
| B9 search/AI | SL-BE-029–035, with keyword-only baseline and separate bounded assistance. |

### 16.4 Reusable task template

When adding a task, use this shape so it can be copied into Jira without reconstructing its intent:

```markdown
### SL-BE-046 — Imperative task title

**Status:** TODO
**Depends on:** Explicit task IDs or implemented capabilities
**Branch:** backend/sl-be-046-short-name
**Owner / branch / merged PR:** Add real links when they exist

**Goal:** Problem solved and why it matters.

**Implementation:**
1. Exact owning modules, contracts and data changes.
2. Observable behavior, error/edge paths and security boundaries.
3. Transaction, concurrency, versioning and provenance rules.
4. API/configuration/migration and operating instructions.

**Tests:** Named success, failure, concurrency and no-LLM scenarios;
state which need PostgreSQL, MinIO or an explicitly opted-in provider.

**Acceptance / after merge:**
- [ ] Observable deliverable that can be verified independently.
- [ ] Failure/edge behavior and preserved invariant.
- [ ] Required documentation/evidence updated.

**Not included:** Explicit neighboring scope.
**Rollback:** Safe reversal and data/configuration implications.
```

## 17. References

- [SupplyLens MVP definition](SupplyLens-MVP-Definition-v0.1.md)
- [SupplyLens architecture](SupplyLens-Architecture-v0.1.md)
- [Document upload and storage design](document-upload-storage-architecture.md)
- [Repository rules](../AGENTS.md)
- [Pull request definition](../specifications/pull-request-definition.md)
- [Python unit-testing rules](../.github/instructions/python-unit-testing.instructions.md)
- [Synthetic fixture map](../fixtures/README.md) and [expected values](../fixtures/expected.json)
- [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [pdfplumber](https://github.com/jsvine/pdfplumber)
- [SQLAlchemy session basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)
- [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [PostgreSQL SELECT / SKIP LOCKED](https://www.postgresql.org/docs/current/sql-select.html)
- [pgvector hybrid search](https://github.com/pgvector/pgvector#hybrid-search)
