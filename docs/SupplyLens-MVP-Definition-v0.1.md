# SupplyLens — MVP Definition

**Status:** Draft for review
**Date:** 28 September 2026
**Purpose:** Define what SupplyLens solves, what the first usable version includes, how its AI features work, and which technology we plan to use.

**At a glance**

- **Core workflow:** Upload a supplier PDF, review its extracted lines, organize products, apply a configurable calculation policy, and analyze confirmed purchases.
- **PDF support:** Automatically extract digital PDFs with selectable text. Preserve image-only or scanned PDFs, mark automatic extraction as unsupported, and route them to manual review.
- **AI boundary:** Purchase records and calculations work without an LLM. Optional AI helps with uncertain fields and natural-language answers.
- **Questions:** Hybrid retrieval finds evidence in documents; verified purchase metrics come from the database.
- **First release:** Purchases only. Payment, stock, inventory, sales, and demand forecasting come later.

## 1. The idea in one paragraph

SupplyLens helps a small retailer turn supplier purchase PDFs into trustworthy purchase and product information. It reads digital PDFs with selectable text, suggests the details it found, asks a person to correct and confirm them, and then shows purchase history and trends. Image-only or scanned PDFs remain available for manual review and entry.

It can also estimate costs and selling prices using a policy configured by that business. A user can search a supplier document, ask a cited question about it, or ask a question about the confirmed purchase data.

The essential purchase workflow works without a large language model (LLM). Optional AI assistance should make difficult extraction and question answering more convenient, while the confirmed data and calculation policy remain the sources of truth.

Mulligan Store is the first real use case. SupplyLens itself is a business-neutral product suitable for a public portfolio repository. Mulligan's supplier documents, private formula rules, rates, and business data stay outside that repository.

## 2. The problem

A retailer can receive a supplier order, an invoice, and other PDFs for the same purchase. A person then has to identify products, quantities, supplier codes, unit prices, fees, and sometimes weight. The supplier's name for an item may differ from the store's product name. An image-only or scanned document may have no selectable text and therefore requires manual entry in the MVP. Copying this information into a spreadsheet takes time, and repeated purchases are hard to compare.

Even after the information is entered, common questions remain difficult:

- Which products have we ordered or been invoiced for by a supplier?
- Have their unit prices changed?
- Which purchase document mentions a freight or handling charge?
- What cost and possible selling price follow from our current calculation policy?

An order or invoice is also easy to mistake for a payment, stock receipt, or sale. Those are separate events. The first version of SupplyLens should organize and explain purchase documents without claiming that goods were received, cash was paid, or retail sales happened.

## 3. Who uses the first version

The initial user is an owner or purchasing operator at one small retailer. They upload supplier PDFs, review extracted data, maintain a product catalog, configure their own cost and pricing policy, and inspect purchase reports.

The MVP is a single-business application with private access. It does not need the account management and isolation required for a multi-business SaaS. Its data model and calculation features must still avoid assumptions about a particular country, currency, supplier, tax, or product category.

## 4. What a complete purchase workflow looks like

Consider a supplier sales order with several product lines. The user uploads the PDF. SupplyLens stores the original privately and creates a processing job.

1. A PDF library reads text, tables, and page locations when the PDF contains selectable text. If the document is image-only or scanned, SupplyLens preserves the original, marks automatic extraction as unsupported, and sends it to manual review.
2. A parser suggests the document type, supplier, reference number, date, currency, lines, quantities, prices, fees, and other fields that are present. It keeps the source page for each suggestion.
3. Validation checks the shape of the data and arithmetic that the document allows. For example, it can compare a line's quantity multiplied by unit price with the displayed line total. A mismatch is shown to the user; it is not silently corrected.
4. If the business has enabled LLM assistance, SupplyLens can send a limited, relevant text excerpt for a difficult field and show an additional suggestion. This suggestion does not overwrite a confirmed value.
5. The user compares suggestions with the PDF, fixes mistakes, matches products to the catalog, and confirms the record.
6. A selected calculation policy produces clearly labeled estimates. Reports then summarize the confirmed purchase information.
7. The user can ask about the document and receive source passages or, with an LLM enabled, a short answer with document and page citations. They can also ask about purchase metrics, which are computed from confirmed records.

If a parser or an AI service cannot identify a field, or automatic extraction is unsupported for the document, the user can enter it manually and complete the workflow.

## 5. MVP features

### 5.1 Documents and extraction

- Upload supplier invoices and supplier order documents as PDFs. Automatic extraction supports digital PDFs with selectable text.
- Keep the original PDF private. Show document type, supplier, reference, date, and processing status.
- Preserve image-only or scanned PDFs, mark them as unsupported for automatic extraction, and provide manual review and entry instead.
- Extract text and tables from supported digital PDFs with page references.
- Provide a general parser and focused supplier layout rules where those rules improve the first real documents. An unfamiliar layout may require more manual review.
- Create an editable draft with field-level source references and validation findings.
- Detect likely duplicate uploads. Let the user link an order and invoice for the same underlying purchase so reports do not add their totals together.
- Record whether a confirmed value came from the document parser, an optional LLM suggestion, or a user's correction.

### 5.2 Product catalog

- Maintain a store product record and retain the original supplier description and identifiers on each purchase line.
- Suggest matches using exact identifiers first, then normalized names and reviewed fuzzy matches.
- Suggest a store-facing name and SKU using configurable, deterministic rules. The user accepts or edits each result.
- Permit a line to remain unmatched until the user resolves it; do not silently create duplicate products.

### 5.3 Configurable calculations

- A business creates a named calculation policy through guided settings. It can define required inputs, named steps, shared-charge allocation methods, currency conversion inputs, percentages, margins, and rounding choices as needed.
- The policy engine uses a limited set of safe operations and validated references between steps. It does not execute arbitrary Python or text written by an LLM.
- The user previews and approves a policy before it becomes active. Each estimate keeps the policy version, source inputs, manual inputs, intermediate values, and final outputs used at the time.
- Missing inputs produce a provisional result or block that specific calculation, with the reason visible. The user can still save the confirmed purchase facts.
- The public project contains the general calculation capability. Mulligan's actual formula definitions and values belong in private configuration, informed by the separate formula document.

### 5.4 Purchase history and reports

- Browse and filter confirmed records by supplier, product, category, document type, date, and currency.
- Show order values and invoice values as separate metrics. When both documents describe the same purchase, their values are not summed as two purchases.
- Show quantities, document unit prices, and unit-price trends where comparable records exist.
- Keep values in different currencies separate unless a documented conversion input and policy are applied. A converted figure is labeled as an estimate.
- Show estimated product cost and possible selling price from a policy separately from the order or invoice amount.
- Let the user inspect the records behind every summary.

These reports do not claim actual cash spent, current stock, sales revenue, realized profit, or demand forecasts. Payment, stock, and sales data are not collected in the MVP.

### 5.5 Ask SupplyLens

The interface has two clear question types:

1. **About a document:** For example, “What handling charge is shown on this invoice?” SupplyLens searches the selected PDF, or a filtered document set, and returns relevant passages with the document name and page. When an LLM is enabled, it can write a concise answer grounded in those passages and attach the same citations. If evidence is missing, it says so.
2. **About analyzed purchases:** For example, “What is the invoiced value from Supplier A in July?” or “Which products have a higher document unit price than on the previous invoice?” SupplyLens calculates the answer from confirmed records. An optional LLM can translate a natural-language question into an approved set of metric names and filters. The server validates that request and runs its own read-only queries. It does not execute SQL written by the model.

Without an LLM, document search, report filters, and purchase dashboards still give access to the same underlying information. Free-form generated answers are an optional interface.

## 6. Why we chose this RAG pattern

RAG means retrieving source material before asking an LLM to answer from it. In SupplyLens, the source material is the retailer's uploaded purchase documents. We chose a **two-step, hybrid retrieval pattern** for document questions:

1. Narrow the search to the selected document or chosen supplier/date filters.
2. Search both exact text and semantic meaning. Exact text helps find document numbers, product codes, and fee labels; semantic search helps when a question uses different words from the document.
3. Combine the ranked results, initially with Reciprocal Rank Fusion, and keep the document, page, and nearby table or section context.
4. Show the retrieved passages. If an LLM is enabled, give it only those passages to compose a cited answer.

The documents are split by page, section, and table context instead of arbitrary cuts through table rows. This is especially useful when a price or fee only makes sense beside its label or column heading.

The selected pattern has a fixed retrieval path and a limited number of model calls. It is easier to test and explain than an agent that repeatedly invents new searches. We will compare keyword-only, semantic-only, and hybrid retrieval on a small set of real questions before assuming hybrid improves results.

This RAG path answers questions about **document wording**. Purchase totals and trends come from the structured database. A question that needs both sources may initially return separate document evidence and a metric, or ask the user to narrow the request; open-ended multi-step research is outside the MVP.

Hybrid retrieval remains useful if no LLM is configured: it can return ranked source passages. Semantic embeddings are generated locally. If that local model is unavailable, exact-text search remains available.

## 7. Where an LLM helps, and where it does not decide

The baseline extractor is a normal Python document-processing pipeline. It does not require an LLM account or API key. The LLM can be enabled for two bounded tasks:

- Suggest values for unclear extracted fields using relevant text excerpts and a defined output schema.
- Interpret a question for document answers or map an analytics question to a restricted, read-only metric request.

The optional model's output is a proposal. Validation and human review decide what becomes a purchase fact. Deterministic code calculates money, aggregates reports, and applies the approved calculation policy. The model cannot change a policy, approve a purchase, invent missing numeric inputs, or run arbitrary database commands.

We should record which parser or model made each suggestion and measure whether LLM assistance reduces user corrections on the same document set. If it does not help enough to justify cost and complexity, the core product still stands.

## 8. Proposed technology and reasons

These choices are the initial implementation plan. Package versions will be pinned when the repository is created.

- **User interface - React, TypeScript, and Vite.** Build a responsive PDF review screen, purchase reports, and a view for cited answers.
- **API - Python with FastAPI and Pydantic.** Define typed contracts for uploads, review, products, policies, reports, and questions, with generated API documentation.
- **Database - PostgreSQL, SQLAlchemy, and Alembic.** Store suppliers, documents, purchases, products, policies, and jobs together, with explicit schema migrations.
- **Document extraction - pdfplumber.** Read text, tables, and page positions from digital PDFs so the review screen can point to the source.
- **Retrieval - PostgreSQL full-text search plus pgvector.** Combine exact-term search, semantic search, and document filters near the purchase data.
- **Local embeddings - Sentence Transformers with multilingual-e5-small as the first candidate.** Create semantic vectors locally for English and Spanish text. Test its quality and resource use before locking the model.
- **Optional generation - one LLM provider adapter, initially the OpenAI Python SDK.** Add structured extraction suggestions and cited answers only when enabled.
- **RAG orchestration - a small LangChain integration in the optional assistant module.** Use a familiar framework while keeping search, ranking, citations, and business decisions explicit in our code.
- **Document jobs - a Python worker sharing the backend package, with jobs stored in PostgreSQL.** Handle digital extraction and indexing with progress, retry, and recovery, without adding a message broker.
- **Local development - a monorepo and Docker Compose.** Keep the web app, API, worker, database, docs, and synthetic test data in one reproducible setup.
- **Tests and delivery - pytest, frontend component tests, end-to-end workflow tests, and GitHub Actions.** Verify calculations, extraction, review, query safety, retrieval quality, and the complete upload flow.

The Python API and document worker are two entry points into one modular backend, not independent microservices. The browser talks to the API over REST. It can receive document-job progress through server-sent events; the worker updates job records in PostgreSQL. PDF files live in private file storage, with local storage for development and an object-storage adapter for deployment.

We will choose a hosting provider after testing the worker's digital extraction and local embedding memory needs, private file storage, pgvector availability, and expected costs. The local Docker setup and synthetic demo data come first. This avoids promising a free public deployment that cannot run the chosen document pipeline.

### How this demonstrates the target role

The project is also a learning and portfolio project for the Truelogic Lead Full-Stack AI Engineer opportunity. The finished repository should provide evidence a reviewer can inspect:

- **Python backend and API design:** Typed FastAPI endpoints, a document worker, clear domain modules, and documented API contracts.
- **React and TypeScript:** A usable PDF review flow, product and policy screens, reports, and a cited question interface.
- **LLM integration and RAG:** Optional structured extraction suggestions, two-step hybrid retrieval, source citations, and evaluation against simpler baselines.
- **Data pipelines and databases:** Recoverable digital-document jobs, validation, PostgreSQL records, and a vector index.
- **Real-time interfaces and engineering quality:** Processing progress, automated tests, CI, containerized local setup, and measured extraction and retrieval quality.
- **Technical direction:** Short architecture decision records explaining the chosen scope, no-LLM fallback, RAG pattern, and tradeoffs found during implementation.

This project can demonstrate hands-on decisions and code. Career history and leadership experience still belong in the CV and interview examples.

## 9. Data and privacy boundaries

- One private business workspace is enough for the MVP. The user must sign in to access real supplier documents.
- The public repository and any public demo use synthetic or properly anonymized PDFs and purchase data. Real Mulligan documents and policy values remain private.
- LLM assistance is off by default. The business explicitly enables it and configures a provider credential.
- When possible, only relevant extracted text excerpts are sent to the provider, not entire PDFs. The interface makes the use of external processing visible.
- Original documents, extracted drafts, confirmed fields, user corrections, policy versions, and derived estimates remain distinguishable.
- Upload and processing failures retain a useful status and allow correction or retry. The original PDF remains available even when automatic extraction is unsupported or fails.

## 10. How we will verify the MVP

We will prepare synthetic or anonymized digital purchase PDFs and expected field values. This becomes a small repeatable evaluation set.

- **Extraction:** Compare document type, supplier, reference, quantities, prices, fees, and line totals with expected values. Measure how often the user must correct the baseline and whether optional LLM assistance reduces that effort.
- **Calculations:** Test policy operations, currency handling, missing inputs, rounding, policy version snapshots, and correct separation of document facts from estimates. The private Mulligan policy can have its own private acceptance examples.
- **Reports:** Compare order and invoice summaries to confirmed records; verify linked documents do not count twice and mixed currencies are not silently added.
- **Document Q&A:** Use expected source passages for questions about fees, terms, and product lines. Compare keyword-only, semantic-only, and hybrid retrieval; check whether cited answers are supported by the referenced page.
- **Analytics Q&A:** Confirm each supported question maps to an allowed metric and filters, uses read-only queries, and either returns the correct value or asks for clarification.
- **No-LLM path:** Run the full upload, digital extraction, review, policy, report, and document-search workflow without any model credentials.
- **End-to-end:** From one PDF upload, reach a confirmed purchase and a supplier report through the browser.

The README should publish the method and aggregate benchmark results from safe fixtures so another engineer can see what improved and what still needs review.

## 11. What is outside the MVP

- Recording payments or claiming that an invoice has been paid.
- Recording stock receipt, inventory balance, stock adjustments, or retail sales.
- Importing sales or stock data and forecasting supplier needs from demand.
- Reporting realized revenue or profit.
- Accounting, point-of-sale, e-commerce, and supplier integrations.
- Automatic approval of extracted facts or model-generated pricing rules.
- An unrestricted formula scripting language or a general autonomous agent.
- Native mobile apps and multi-business SaaS administration.

These can be later versions. The schema should keep purchase documents and future payment, receipt, and sale events conceptually separate so later work does not have to reinterpret old records.

## 12. MVP completion criteria

The MVP is usable when a person can upload a digital supplier PDF; automatically extract, review, and confirm its purchase lines; link an order and invoice when needed; match products and review name/SKU suggestions; configure and apply a versioned calculation policy; see accurate purchase-only reports; search or ask cited questions about a document; and ask supported questions about the confirmed purchase data. An image-only or scanned PDF must be preserved, marked unsupported for automatic extraction, and available for manual review.

The same core purchase workflow must succeed with LLM features switched off. The AI-enabled path should show a measurable improvement on the evaluation set and identify its cost, limitations, and failure cases.

## 13. Reference material for the proposed stack

- [Truelogic Lead Full-Stack AI Engineer role](https://jobs.ashbyhq.com/truelogic/7b557eac-51e4-4396-ada3-483421b22fdc)
- [pdfplumber documentation](https://github.com/jsvine/pdfplumber)
- [pgvector hybrid search](https://github.com/pgvector/pgvector#hybrid-search)
- [FastAPI background tasks guidance](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [FastAPI server-sent events](https://fastapi.tiangolo.com/tutorial/server-sent-events/)
- [LangChain retrieval patterns](https://docs.langchain.com/oss/python/langchain/retrieval)
- [multilingual-e5-small model card](https://huggingface.co/intfloat/multilingual-e5-small)
- [Vite React and TypeScript template](https://vite.dev/guide/)
- [Docker Compose documentation](https://docs.docker.com/compose/)
