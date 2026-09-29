<div align="center">

# SupplyLens

### From supplier PDFs to trustworthy purchase intelligence

**Reviewable extraction · Human confirmation · Transparent calculations · Cited answers**

![Status](https://img.shields.io/badge/status-early%20scaffold-f59e0b)
![Backend](https://img.shields.io/badge/backend-FastAPI-009688)
![Frontend](https://img.shields.io/badge/frontend-React%20%2B%20TypeScript-149eca)
![Database](https://img.shields.io/badge/database-PostgreSQL%20%2B%20pgvector-4169e1)
![AI](https://img.shields.io/badge/AI-optional-8b5cf6)

</div>

---

## The idea

Small retailers receive purchase orders, invoices, and scanned supplier PDFs containing the information they need—but not in a form they can reliably analyze. SupplyLens turns those documents into structured purchase records while keeping the original evidence, the user's corrections, and every calculated estimate visible.

> **The document is evidence. The confirmed record is truth. AI is an assistant, not an authority.**

The first real use case is a single private retailer, while the public project remains business-neutral and uses only synthetic or anonymized data.

## The approach

```mermaid
flowchart LR
    A[Supplier PDF] --> B{Digital or scan?}
    B -->|Digital| C[Text and table extraction]
    B -->|Scan| D[Local OCR]
    D --> C
    C --> E[Editable draft + source pages]
    E --> F[Validation findings]
    F --> G[Human review and confirmation]
    G --> H[(Trusted purchase data)]
    H --> I[Reports and trends]
    H --> J[Versioned policy estimates]
    C --> K[Document search]
    K --> L[Cited passages]
    L -. optional .-> M[LLM-composed answer]
```

SupplyLens separates three kinds of information that are easy to blur together:

| Layer | Meaning | Authority |
| --- | --- | --- |
| **Document facts** | What a supplier PDF appears to say | Must retain page-level provenance |
| **Confirmed records** | Values reviewed and accepted by a person | Source for purchase metrics |
| **Policy estimates** | Cost or price outputs from explicit inputs and rules | Versioned, reproducible, and clearly labeled |

This separation prevents uncertain OCR, generated text, or changing business formulas from silently rewriting purchase history.

## Two question paths

```mermaid
flowchart TB
    Q[User question] --> T{What kind of answer?}
    T -->|About document wording| R[Filtered keyword + semantic retrieval]
    R --> P[Passages with document and page citations]
    P -. optional LLM .-> A[Concise grounded answer]
    T -->|About purchase performance| M[Approved metric + typed filters]
    M --> D[(Confirmed database records)]
    D --> V[Deterministic result]
```

- **Document questions** use hybrid retrieval: exact search finds codes and labels; semantic search finds related wording. Search remains useful without an LLM.
- **Purchase questions** use approved metrics executed by the server. The model may suggest a metric request, but it never writes or executes SQL.

## Architecture

```mermaid
flowchart LR
    UI[React + TypeScript UI] -->|REST / events| API[FastAPI]
    API --> DB[(PostgreSQL + pgvector)]
    API --> STORE[(Private PDF storage)]
    WORKER[Python document worker] --> DB
    WORKER --> STORE
    WORKER --> OCR[OCRmyPDF + Tesseract]
    WORKER --> PARSE[pdfplumber + parsers]
    API -. opt-in .-> LLM[LLM provider adapter]
```

The backend is a modular Python application with API and worker entry points—not a fleet of microservices. PostgreSQL stores business records, job state, full-text search data, and vectors. Provider and storage details stay behind adapters so local development does not dictate deployment.

## Product guardrails

- The complete purchase workflow works with **no LLM credentials**.
- Extracted values are suggestions until a user confirms them.
- Money uses deterministic decimal arithmetic and versioned policies.
- Mixed currencies are never silently combined.
- Orders and invoices linked to one purchase are not double-counted.
- Models cannot approve purchases, edit policies, invent missing inputs, or run SQL.
- Real supplier PDFs, private formulas, and credentials never enter public fixtures or logs.

## Repository map

```text
SupplyLens/
├── apps/
│   ├── backend/          # FastAPI package; future API and worker modules
│   └── web/              # React + TypeScript + Vite
├── docs/                 # Product definition and architecture
├── fixtures/             # Synthetic PDFs and expected results
├── infra/                # Deployment configuration
├── compose.yaml          # Local PostgreSQL + pgvector
└── AGENTS.md             # Contributor guidance
```

## Current status

SupplyLens is at the **repository skeleton** stage.

| Area | Today | MVP direction |
| --- | --- | --- |
| Backend | FastAPI app with `/health` | Documents, purchases, catalog, policies, reports, assistant, worker |
| Frontend | Vite starter | Upload, side-by-side PDF review, reports, cited Q&A |
| Data | PostgreSQL/pgvector Compose service | Migrations, job leases, provenance, revision history |
| Tests | Not scaffolded yet | pytest, component tests, end-to-end workflow, retrieval evaluation |

## Run the scaffold

### Prerequisites

- Python 3.14 and [uv](https://docs.astral.sh/uv/)
- Node.js with npm
- Docker with Compose

### Backend configuration

The API reads `DATABASE_URL` from `apps/backend/.env`. Copy the example file there before starting the backend:

```powershell
# From the repository root
Copy-Item apps/backend/.env.example apps/backend/.env
```

The example URL is configured for the local database in `compose.yaml`:
`postgresql+psycopg://supplylens:localdev@127.0.0.1:5433/supplylens`.
For another database, replace it with a SQLAlchemy PostgreSQL URL in the form
`postgresql+psycopg://<username>:<password>@<host>:<port>/<database>`.
Keep credentials private and do not commit your `.env` file.

```bash
# Database
docker compose up -d db

# API (from apps/backend)
uv sync
uv run uvicorn supplylens.api:app --reload

# Web app (from apps/web)
npm ci
npm run dev
```

Useful frontend checks:

```bash
npm run lint
npm run build
```

## Delivery roadmap

```mermaid
flowchart LR
    A[1. Skeleton] --> B[2. Upload and review]
    B --> C[3. OCR and reconciliation]
    C --> D[4. Catalog and policies]
    D --> E[5. Reports]
    E --> F[6. Search and optional AI]
    F --> G[7. Deployment readiness]
```

Each slice should work end to end before the next one expands the system. Quality is measured with synthetic PDFs, expected extracted fields, correction counts, calculation traces, retrieval relevance, citation validity, and a full no-AI workflow.

## Scope boundaries

The MVP covers supplier purchase documents, product matching, configurable estimates, purchase reporting, and cited document search. It does **not** claim to track payments, inventory, stock receipt, retail sales, realized profit, or demand forecasting.

## Read the design

- [MVP definition](docs/SupplyLens-MVP-Definition-v0.1.md) — problem, users, scope, features, and completion criteria.
- [MVP architecture](docs/SupplyLens-Architecture-v0.1.md) — system boundaries, data model, workflows, security, and build order.
- [Contributor guidelines](AGENTS.md) — repository conventions and development commands.

## Contributing

Start with the relevant vertical slice, use synthetic data, and preserve provenance at every boundary. Before opening a pull request, run the checks available for the area you changed and describe any privacy, architecture, or calculation impact. See [AGENTS.md](AGENTS.md) for the full guide.
