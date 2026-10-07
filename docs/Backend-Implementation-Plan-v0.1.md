# SupplyLens — Revised Implementation Plan

## Principles

1. **Checkpoint 1 is a small, demonstrable document-processing slice.**
2. **Milestone 2 starts the path to trusted purchase records and protected data.**
3. **RAG and optional LLM are already present in Milestone 1.**
4. **The complete MVP remains required; only intentionally excluded features are deferred.**
5. **No browser/UI requirement is hidden.** The first milestone is API-demonstrated; the React experience belongs in the complete MVP.
6. **Use synthetic data only until auth/workspace/private storage is complete.**
7. **OCR is outside the MVP.** Image-only documents retain the original and receive a manual-review path.
8. All estimates are planning estimates, not commitments.

---

# 1. Current implementation state

## Already implemented and tested

| Capability | Current evidence |
|---|---|
| FastAPI backend | `GET /health`, readiness checks, v1 router, typed configuration. |
| Database foundation | PostgreSQL via SQLAlchemy, Alembic, readiness/session handling. |
| Documents | Upload intent, completion, document metadata, soft delete, signed download, validation. |
| Private object storage | S3-compatible storage abstraction, local MinIO, integration tests. |
| Processing-job records | Job table, leases fields, attempts, errors, enqueue on completion. |
| Synthetic fixture set | Digital synthetic PDFs and expected fields in `fixtures/`. |
| Quality tooling | Backend coverage, lint, integration tests, versioning, workflows. |
| Frontend scaffold | React 19 + TypeScript + Vite +Vitest; no product workflow. |

## Models/placeholders without complete behavior

| Area | Missing behavior |
|---|---|
| Worker execution | No download/process/parse worker loop. |
| Extraction persistence | No versioned extraction run/page evidence. |
| Parser | No robust digital-PDF purchase-field extraction. |
| Draft/review API | No candidate + edit versions or conflict protection. |
| Purchase history | No supplier review, confirmation, revisions, or source links. |
| Product matching | No product records/review suggestions. |
| Calculation policy | No deterministic typed evaluator or estimate persistence. |
| Reports | No confirmed-purchase aggregation/drilldown. |
| Auth/workspace | No verified identity, workspace scope, private user-owned storage. |
| Semantic retrieval | Milestone 1 has deterministic page retrieval; Milestone 2+ will deepen it. |

## What Checkpoint 1 adds

Checkpoint 1 should prove the deterministic extraction/review-assist workflow. It is not a general auth release or a purchase-confirmation system.

---

# 2. Milestone 1 — Synthetic digital PDF evidence and draft review

## Goal

Process one digital synthetic PDF end-to-end through upload, job execution, page evidence, parser output, editable draft, and keyword citations. Optional LLM output is schema-bound and falls back to deterministic evidence.

## Scope

- One PDF fixture.
- One worker execution mode.
- One broad deterministic parser path.
- No browser required.
- No auth required.
- No purchase confirmation required.
- No semantic/vector retrieval unless the synthetic fixture is very easy to extend and local embeddings exist locally.

## Acceptance scenario

At the end of Milestone 1, demonstrate:

1. Create a document and upload-intent URL.
2. Upload `01_simple_digital_invoice.pdf` to MinIO.
3. Call complete and create one processing job.
4. Run a worker once.
5. Document moves to processing state.
6. Extraction run and page evidence are saved.
7. Parser returns supplier, reference, date, currency, lines, quantities, unit prices, totals, and page references.
8. Draft API exposes candidates and supports one edit.
9. Search API returns matched page passages without an LLM.
10. Optional schema-bound LLM adapter can answer with citations, but the deterministic path still works without it.

## Tasks

| # | Task | Purpose | Dependencies | Acceptance | Tests | Estimate | PR boundary |
|---|---|---|---|---|---|---|---|
| 1.1 | Extraction contracts and persistence | Define the internal result contract and store versioned evidence. | Existing document/job models. | Save/reload processed pages with extraction/parser versions. | Version/idempotent serialization tests, migration test. | **4h** | `backend/extraction-contracts` |
| 1.2 | Digital PDF extractor | Read fixture 01 via pdfplumber/bytes. | 1.1 | Original bytes assert hash/page count/text/tables; invalid PDF errors. | Unit parser tests against fixture 01. | **3h** | `backend/pdfplumber-adapter` |
| 1.3 | Baseline parser | Parse at least fixture 01's core fields/lines. | 1.1–1.2 | No fabrication; unavailable fields remain blank/unknown. | Parser correctness tests. | **3h** | `backend/baseline-parser` |
| 1.4 | Processing controller | Orchestrate load/download/extract/parse/persist. | 1.1–1.3 | One direct controller invocation processes fixture 01; invalid preserves original. | Controller tests with fake storage/persistence. | **3h** | `backend/process-doc-controller` |
| 1.5 | Minimal worker | Queue DB → extraction controller. | 1.4 | `python -m supplylens.worker --once` processes due job and updates states. | Worker unit/integration tests. | **3h** | `backend/worker-once` |
| 1.6 | Draft persistence/edit conflict | Store candidate fields and edit versions. | 1.1–1.4 | Edit can patch one draft field; stale version is rejected. | Persistence tests, 409 conflict test. | **3h** | `backend/draft-edit-api` |
| 1.7 | Job status retry | Expose safe job state and a manual/basic retry. | 1.5 | Failed/unsupported/their document state visible. | Basic API tests. | **2h** | `backend/job-status-retry` |
| 1.8 | Keyword passage indexing | Persist page/section/table passages. | 1.1–1.4 | Matching pages are searchable by exact context and citation refs. | Passage persistence and query tests. | **3h** | `backend/passage-index` |
| 1.9 | Keyword document Q&A | Answer by returning passages first. | 1.8 | User gets document/page/excerpt or no-result state. | Search tests. | **3h** | `backend/keyword-rag` |
| 1.10 | Optional LLM answer adapter | Schema-constrained bounded answer composer. | 1.8–1.9 | Real adapter only if enabled; deterministic disabled mode works. | Fake adapter unit tests; no live internet test needed. | **5h** | `backend/optional-llm-adapter` |
| 1.11 | End-to-end acceptance test | Prove flow. | 1.1–1.10 | A scripted validation runs upload completion → worker → draft edit → keyword search. | Postgres+MinIO integration test. | **4h** | `backend/e2e-acceptance` |
| 1.12 | Stabilization/documentation | Close rough edges. | 1.1–1.11 | Board and PR evidence distinguish mainline work and no-LLM paths. | Full local unit test run. | **4h** | `backend/cleanup-docs` |

**Total Milestone 1: 40h focused**

If PDF parsing is harder than expected, Milestone 1 becomes “upload + worker + extractor evidence + manual review” and parser/draft goes into the immediate next tiny PR.

---

# 3. Milestone 2 — Identity, ownership, and trusted review

## Goal

Convert the synthetic evidence flow into a basic reviewed-purchase system, protected by account/workspace boundaries.

## What is in this milestone

- Real identity context.
- Workspace ownership and authorization.
- Supplier selection.
- Purchase confirmation.
- Private object access.
- Revisions.
- Basic catalog/purchase data entries.

## What it still excludes

- Full React implementation is allowed but not mandatory for this backend milestone.
- Advanced diff, OCR, POS, payments, stock, reconciliation automation, and hosting build-out remain out of scope.
- Full embedding/reranking search.

## Tasks

| # | Task | Acceptance | Tests | Estimate |
|---|---|---|---|---|
| 2.1 | Auth identity and sessions | Private routes require verified identity/session; no dev bypass in production. | Unauthenticated protected endpoint test; trusted session test. | **8h** |
| 2.2 | Workspace ownership | Every saved document/job/draft/page belongs to workspace. | Cross-workspace access denied; migration applies to existing records. | **8h** |
| 2.3 | Authorization middleware/routes | All document/job/draft/purchase/search/download routes verify workspace relationship. | Unauthorized foreign access rejected. | **8h** |
| 2.4 | Private storage resolver | Server resolves workspace storage configuration and credentials; no public object exposure. | Fake per-workspace bucket test; no browser-supplied credentials. | **8h** |
| 2.5 | Supplier records | Create/read/select supplier per workspace. | Synthetic supplier selection persists. | **5h** |
| 2.6 | Purchase case/revision/confirm | Explicit planned/ordered/purchase_recorded snapshot after human review. | Immutable revision preserved; confirmation not duplicated on retry. | **10h** |
| 2.7 | Review history browsing | Browse records by supplier/status/date and inspect source. | History query returns snapshots only; no current-revision mutation. | **6h** |
| 2.8 | Basic source-link rules | A document cannot be the active source of two purchase cases. | Duplicate-link attempt returns a clear conflict. | **4h** |
| 2.9 | Basic product preservation | Imported/extracted descriptions remain; optional unmatched product label. | No fake SKU creation; line remains audit-trailed. | **4h** |
| 2.10 | Documentation/verification | MVP milestone 2 local validation script. | No-LLM and protected-access smoke test works. | **4h** |

**Milestone 2 total: ~65h**

---

# 4. Milestone 3 — Catalog, duplicates, policies, estimates

## Goal

Make the MVP product-scale enough to distinguish repeated suppliers/products, compare related facts, and estimate costs consistently.

| Area | Scope | Acceptance | Estimate |
|---|---|---|---|
| Product catalog | Create/read/update suppliers/products. | Supplier code remains distinct from store code. | **10h** |
| Matching suggestions | Exact/normalized/fuzzy suggestion logic available. | Suggestions require human acceptance. | **8h** |
| Deterministic naming | Spanish name/SKU suggestions from configurable rules. | Deterministic, editable, but not auto-applied. | **6h** |
| Duplicate suggestions | Exact hash and related-document detection. | Potential match never merges automatically. | **8h** |
| Document linking/comparison | Link order/invoice/bill to same purchase case. | Matching documents don't double count; differences are shown. | **12h** |
| Reconciliation workflow | User accepts/rejects changes; new snapshot if accepted. | Old revision remains immutable. | **8h** |
| Policy schema | Limited typed expressions, inputs, names, units, currency, rounding. | No arbitrary Python/LLM policy. | **10h** |
| Policy evaluator | Deterministically calculate intermediate values and estimate outputs. | Decimal math reproduces exactly; missing inputs result in provisional/blocked state. | **16h** |
| Policy preview/publish | Save draft, preview, publish explicit version. | Published version cannot be changed except by new version. | **8h** |
| Estimate snapshot | Tie estimate to purchase revision and policy version. | Reproducible calculation trace. | **8h** |
| Reports | Purchase-recorded supplier/product views, drilldown, filter. | Planned/ordered separate; no currency smoothing. | **16h** |
| Metrics API | Read-only approved metric definitions. | No arbitrary business metrics or generated SQL. | **8h** |

**Milestone 3 total: ~118h**

---

# 5. Milestone 4 — RAG deepening and evidence quality

This builds on Milestone 1's basic keyword passages.

| Work | Acceptance | Estimate |
|---|---|---|
| Contextual page/section passage builder | Table rows include headers/sections and citations. | **8h** |
| Refined keyword search | Boolean/filter by supplier/date/document, stable passages. | **6h** |
| Local embedding adapter and model version | pgvector/model metadata persisted cleanly; LLM not required. | **14h** |
| Semantic retrieval comparison | English/Spanish synthetic queries retrieve relevant passages. | **8h** |
| Hybrid retrieval/eval harness | Evaluate keyword/semantic/hybrid on 10–20 labeled examples. | **10h** |

**Milestone 4 total: ~46h**

---

# 6. Milestone 5 — Optional LLM maturation and reporting trace

Milestone 1 introduces an initial adapter. This milestone completes its bounded product behavior.

| Capability | Acceptance | Estimate |
|---|---|---|
| Extraction suggestions | Missing/uncertain fields receive schema-valid proposal, not silent truth. | **10h** |
| Cited document answers | Answer only from retrieved passages; citation page/document refs; no support = refusal/no-result. | **10h** |
| Analytics question interpretation | Natural language maps to approved metric definition and filters. | **8h** |
| LLM safety boundaries | No SQL, approval, calculation, policy mutation, or business-decision mutation. | **6h** |
| Evaluation methodology | Repeat correctness/correction effort/cost/failure tests; record measurements. | **8h** |

**Milestone 5 total: ~42h**

---

# 7. Milestone 6 — Complete browser experience and MVP verification

This is not postponed entirely; it is moved out of the 40-hour backend slice.

| Work | Acceptance | Estimate |
|---|---|---|
| Upload/progress UI | React can create intent, upload, complete, show state. | **10h** |
| Document review UI | Page preview/PDF download, fields, lines, warnings. | **18h** |
| Corrections/confirmation UI | Human edit and explicit planned/order/recorded choice. | **12h** |
| Linked documents UI | Related document suggestion/link and comparison. | **10h** |
| Product/catalog UI | Create/edit products, match suggestion review. | **12h** |
| Policy editor/preview UI | Configure slices/inputs/rounding; explicit publish. | **16h** |
| Reports/drilldown UI | Purchase-recorded supplier/product metrics and filters. | **14h** |
| Ask-question UI | Keyword/RAG passages and optional cited answer. | **12h** |
| No-LLM end-to-end validation | Whole app usable with LLM disabled. | **10h** |
| React/Vitest tests and final integration | Upload→review→confirm→report/search flow tested via API/fixtures. | **16h** |

**Milestone 6 total: ~130h**

---

# 8. Estimate to full MVP

| Milestone | Estimate |
|---|---:|
| 1 | 40h |
| 2 | 65h |
| 3 | 118h |
| 4 | 46h |
| 5 | 42h |
| 6 | 130h |
| **Total** | **~441h** |

This is a planning estimate. At 10–15 focused hours/week, that is roughly **30–44 weeks**, even if several paths are reduced. If your target is shorter, we need a reduced product profile and should not promise the complete MVP unchanged.

---

# 9. What comes before each choice driving a PR

Recommended immediate order:

1. M1.1 Extraction contracts/persistence.
2. M1.2 pdfplumber adapter.
3. M1.3 baseline parser only for the simplest fixture.
4. M1.4 processing controller.
5. M1.5 minimal worker.
6. M1.6 draft edit API.
7. M1.7 job state/retry.
8. M1.8 passage indexing and retrieval.
9. M1.10 optional LLM adapter.
10. M2.1 auth/workspace before continuing into real purchase history.

---

# 10. Summary of scope decisions

- We **do not remove** RAG/LLM/auth forms from the MVP.
- Milestone 1 becomes the smallest vertically coherent slice and includes initial RAG/LLM value.
- Milestone 2 is intentionally auth-first to prevent retrofitting security into purchase history.
- Milestone 6 is the real browser/MVP verification milestone.
- The complete MVP still includes document evidence, correlated purchase records, products, policies, reports, search, optional LLM, React flow, and tests.
