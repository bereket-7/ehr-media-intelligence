# EHR Media Intelligence Platform

A local-first engineering assessment prototype for ingesting synthetic, unstructured EHR media records, cleaning and normalizing them, mapping them to HL7 FHIR R4 resources, generating constrained AI clinical summaries, and enabling semantic search.

> **Safety Notice:** This project is an engineering assessment prototype using synthetic data only. It is not clinical software, a medical device, or a clinical decision support tool. AI-generated summaries and semantic search results are informational, may contain errors or omissions, and must not be used for patient care, triage, diagnosis, or clinical decisions.

---

## Key Features

- **Multi-Format Ingestion & Cleaning:** Ingest synthetic records via JSON arrays, CSV spreadsheets, or plain-text clinical notes with automated date/gender normalization, duplicate suppression, and record-level transformation audit logs.
- **HL7 FHIR R4 Compliance:** Maps canonical clinical media to valid FHIR R4 `Patient`, `DocumentReference`, and `DiagnosticReport` resources packaged into per-patient collection Bundles with 100% reference integrity.
- **AI Clinical Summaries with Offline Fallback:** Patient-level summaries powered by OpenAI (`gpt-4o-mini`) or a zero-dependency deterministic offline fallback. Summaries are strictly constrained under 200 words, cached by content hash, and marked with explicit AI advisory labels.
- **Semantic Vector Search:** Natural language search powered by sentence embeddings (`all-MiniLM-L6-v2`) and persistent vector storage with top-5 ranked retrieval, similarity scoring, and multi-parameter filtering (resource type, date range, patient).
- **Accessible Healthcare Dashboard:** Single-page dashboard built with vanilla JavaScript (ES6+) and Tailwind CSS featuring WCAG 2.1 AA accessibility, keyboard navigation, live database metrics, drag-and-drop file upload, and a FHIR explorer.

---

## Technology Stack

- **Backend:** Python 3.11+, FastAPI, Pydantic v2, `fhir.resources`, Uvicorn.
- **Database & Persistence:** SQLite (relational records, audit logs, FHIR resources/bundles, summary cache).
- **Vector Storage:** Persistent ChromaDB with an automated SQLite-backed `EmbeddedVectorStore` fallback for zero-dependency portability.
- **Embedding Models:** `sentence-transformers` (`all-MiniLM-L6-v2`, 384-d dense vectors) with a CPU-compatible deterministic projection fallback.
- **AI Summarization:** OpenAI API (`gpt-4o-mini`) with rule-based deterministic clinical fallback.
- **Frontend:** Vanilla JavaScript (ES6+), HTML5 semantic landmarks, Tailwind CSS (via CDN).
- **Testing:** `pytest`, `pytest-asyncio`, Starlette `TestClient`.

---

## Repository Structure

```
ehr-media-intelligence/
├── AGENTS.md                          # Coding guidelines and quality gates
├── README.md                          # Platform documentation and quick start
├── Dockerfile                         # Production-grade multi-stage container build
├── docker-compose.yml                 # One-command container runtime with volume persistence
├── .dockerignore                      # Docker context exclusion rules
├── docs/                              # Comprehensive architectural and technical specs
│   ├── ONE_PAGE_WRITEUP.pdf           # Formal 1-page PDF assessment submission
│   ├── ARCHITECTURE.md                # Component architecture and data flow
│   ├── API_SPEC.md                    # REST API endpoint specification
│   ├── FHIR_MAPPING.md                # FHIR R4 resource mapping and validation rules
│   ├── TESTING.md                     # Test strategy and execution instructions
│   └── screenshots/                   # Visual walkthrough UI screenshots and samples
├── frontend/                          # Single-page application assets
│   ├── index.html                     # Semantic HTML5 layout with WCAG landmarks
│   ├── css/styles.css                 # Focus indicators, scrollbars, reduced motion
│   └── js/app.js                      # Client controller (search, modals, ingestion)
└── backend/                           # FastAPI backend application
    ├── requirements.txt               # Pinned Python package dependencies
    ├── pyproject.toml                 # Package metadata and pytest configuration
    ├── .env.example                   # Environment variable template (no secrets)
    ├── data/synthetic/                # Committed synthetic test fixtures (JSON, CSV, TXT)
    ├── scripts/
    │   ├── seed_data.py               # Database seeder utility
    │   ├── generate_pdf_direct.py     # Pure-Python PDF generator
    │   ├── generate_pdf.py            # PDF generation runner
    │   └── docker-entrypoint.sh       # Container initialization and auto-seeder
    ├── app/                           # Application source code
    │   ├── main.py                    # FastAPI application composition root
    │   ├── api/v1/routes/             # REST route handlers (health, ingest, patients, search, fhir)
    │   ├── core/                      # Configuration settings and structured logging
    │   ├── ingestion/                 # Parsers, cleaners, and ingestion coordinator
    │   ├── models/                    # Pydantic v2 canonical, search, and summary schemas
    │   ├── repositories/              # SQLite database initialization and data access
    │   └── services/                  # FHIR mapper, embedding, search, summarization
    └── tests/                         # Automated test suite (80 test cases)
```

---

## Quick Start

You can run the platform either **natively with Python 3.11+** (recommended for rapid development and testing) or **via Docker Compose** (recommended for zero-dependency containerized evaluation).

---

### Option A: Native Python Virtual Environment (Recommended)

#### 1. Prerequisites
- **Python 3.11+** installed (`python --version` or `python3 --version`).
- Git.

#### 2. Clone and Setup Environment
```bash
# Clone the repository
git clone https://github.com/bereket-7/ehr-media-intelligence.git
cd ehr-media-intelligence

# Create and activate virtual environment
# On macOS / Linux:
python3 -m venv .venv
source .venv/bin/activate

# On Windows (PowerShell):
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install backend dependencies
pip install -r backend/requirements.txt

# Configure environment variables
# On macOS / Linux:
cp backend/.env.example backend/.env

# On Windows (PowerShell / Command Prompt):
copy backend\.env.example backend\.env
```

#### 3. Seed Synthetic Dataset (Recommended)
Pre-populate SQLite persistence, generate per-patient FHIR R4 Bundles, and index semantic vectors from the committed synthetic fixtures:
```bash
python backend/scripts/seed_data.py --reset
```
*Expected output: Ingests 14 unique synthetic patients, 23 canonical media records, and 22 semantic vectors with zero parse errors.*

#### 4. Start the Application
Start the FastAPI application from the `backend/` directory:
```bash
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

---

### Option B: Docker & Docker Compose (Zero-Friction Containerized)

If you prefer evaluating the platform in an isolated container without installing Python dependencies locally:

#### 1. Prerequisites
- **Docker Desktop** (or Docker Engine + Compose plugin) installed and running.

#### 2. Launch the Application
From the repository root:
```bash
docker compose up --build
```
*The container automatically runs the synthetic data seeder on first boot, initializes SQLite and vector storage, runs healthchecks, and launches the FastAPI server on port 8000.*

To stop the container:
```bash
docker compose down
```

---

### Accessing the Platform (Both Options)

- **Web Dashboard:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive OpenAPI Documentation (Swagger UI):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Alternative ReDoc UI:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## Design Decisions & Trade-offs

1. **SQLite for Relational Persistence:**
   - *Why:* Chosen for local-first, zero-configuration evaluation. Eliminates external database server setup (Postgres/MySQL) while providing ACID transactions, atomic rollback on ingestion errors, and reliable relational integrity across patients, records, FHIR bundles, and audit logs.
   - *Trade-off:* Concurrency is limited by SQLite's single-writer lock; enterprise production would transition to PostgreSQL.
2. **HL7 FHIR R4 for Interoperability:**
   - *Why:* FHIR R4 is the global standard for modern healthcare interoperability. We use the official `fhir.resources` library to validate resources against R4 schemas. Demographics map to `Patient`, notes/imaging map to `DocumentReference`, and laboratory results map to `DiagnosticReport`.
   - *Trade-off:* Full FHIR R4 schemas are verbose; we map core mandatory and high-utility attributes to maintain high data quality without inventing missing fields.
3. **Embedding Model & Vector Storage Architecture:**
   - *Why:* We use `sentence-transformers` with `all-MiniLM-L6-v2` producing 384-dimensional dense vectors. It provides excellent clinical concept matching with a compact memory footprint (<120MB) and fast CPU inference. For vector persistence, ChromaDB is used, with an automated SQLite-backed `EmbeddedVectorStore` fallback to guarantee execution across all Python environments.
   - *Trade-off:* Domain-specific clinical models (e.g., Clinical-BERT) offer deeper terminology nuance but require significantly more memory and GPU acceleration.
4. **Deterministic Fallback for AI Summarization:**
   - *Why:* Healthcare systems must remain dependable when external AI providers experience outages, latency spikes, or API quota exhaustion. When `OPENAI_API_KEY` is omitted or unavailable, the system activates a rule-based deterministic clinical fallback that extracts recorded diagnoses, key findings, and abnormalities directly from persisted source records with zero hallucination risk.
   - *Trade-off:* The fallback summary is structural and concise rather than natural-language conversational, but it guarantees 100% evidence grounding.
5. **Zero-Framework Frontend (Vanilla JS + Tailwind CSS):**
   - *Why:* Avoids npm dependency bloat, Node version drift, and frontend build pipeline complexities. Reviewers can run the application immediately after starting FastAPI without running `npm install` or `npm run build`.

---

## Data Quality & Validation

- **Multi-Format Ingestion:** Streaming parsers handle JSON arrays, CSV spreadsheets, and delimited plain-text notes. Files exceeding 10 MB or containing unparsable syntax are safely rejected with descriptive error payloads.
- **Field Normalization:**
  - *Dates:* Normalized into standard ISO 8601 (`YYYY-MM-DD`). Varied formats (`MM/DD/YYYY`, `DD-Mon-YYYY`, `YYYY.MM.DD`) are handled deterministically.
  - *Gender:* Administrative gender codes are mapped to FHIR R4 values (`male`, `female`, `other`, `unknown`).
  - *Whitespace & Text:* Clinical narratives are trimmed and normalized while preserving all clinical facts and original source text.
- **Identity Resolution & Quarantine:**
  - Records lacking an explicit MRN are assigned a stable deterministic synthetic identifier (`pat_synth_...`).
  - When an MRN is received with a patient name conflicting with an existing record, the incoming record is flagged with `IdentityStatus.CONFLICT_QUARANTINED` and excluded from search indexing to prevent cross-patient record pollution. Patients are never merged based on fuzzy name matching alone.
- **Duplicate Suppression:**
  - An MD5 content fingerprint over `(patient_key, record_type, record_date, text)` identifies exact duplicates and suppresses redundant persistence while appending a trace to the audit trail.
- **Record-Level Audit Trail:**
  - Every transformation, normalization, duplicate suppression, and quarantine action is appended to a structured audit trail (`AuditEntry`) stored in SQLite.
- **FHIR Validation & Reference Integrity:**
  - Every generated resource is validated against HL7 FHIR R4 specifications via `fhir.resources`. Subject references (`Patient/{id}`) are verified to ensure no dangling or circular references exist within collection Bundles.
- **Synthetic Data Policy:**
  - All fixtures and committed files consist exclusively of synthetic, fabricated data. No real patient data, protected health information (PHI), or credentials exist in the repository.

---

## Web Dashboard Capabilities

1. **Semantic Search & Intelligence View:**
   - Natural language query input with instant submission.
   - Clickable clinical suggestion chips demonstrating semantic matching (*"Patient with signs of elevated blood sugar"*, *"Brain MRI imaging"*, *"Evidence of lung disease"*, *"Severe kidney infection"*).
   - Multi-parameter filter toolbar: Resource Type (`ALL`, `CLINICAL_NOTE`, `LABORATORY`, `IMAGING_STUDY`), Date Range bounds, and Patient MRN.
   - Ranked result cards displaying patient display name, synthetic MRN, record date, category badge, grounded text excerpt, and geometric cosine similarity score percentage.
2. **Patient Directory View:**
   - Table listing all ingested synthetic patients with demographic metadata (MRN, synthetic DOB, administrative gender, active status) and total linked record count.
   - Direct action button to open the detailed patient intelligence modal.
3. **Patient Detail & AI Summary Modal:**
   - **AI Clinical Summary:** Displays generation timestamp, provider/model lineage badge (`gpt-4o-mini` vs. `deterministic_clinical_fallback`), mandatory clinical disclaimer box, structured narrative (<200 words), and a one-click summary regeneration action.
   - **Source Records:** Chronological list of raw source documents linked to the patient.
   - **FHIR Bundle:** Formatted JSON representation of the patient's FHIR R4 Collection Bundle with a one-click "Copy JSON" button.
4. **Synthetic Data Ingestion Studio:**
   - Drag-and-drop file upload zone supporting `.json`, `.csv`, and `.txt` files up to 10 MB with client-side validation.
   - Ingestion summary cards (Accepted, Quarantined, Duplicates, Rejected) and an interactive transformation audit trail table.
5. **FHIR R4 Explorer:**
   - Patient dropdown to inspect and copy validated FHIR R4 Bundle JSON directly.
6. **Accessibility (WCAG 2.1 AA):**
   - High-contrast skip link (`#main-content`), ARIA landmarks, `aria-live="polite"` screen reader announcer, visible `:focus-visible` outlines, modal focus trapping with `Escape` key dismissal, and `prefers-reduced-motion` compliance.

---

## API Documentation

When the application is running, interactive API documentation and testing interfaces are available at:
- **Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc UI:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **OpenAPI Schema (JSON):** [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

For the complete offline specification covering all endpoints, request/response schemas, and error structures, see [docs/API_SPEC.md](docs/API_SPEC.md).

---

## Automated Testing & Quality Gates

The test suite consists of **80 automated tests** covering all milestones:

```bash
cd backend
pytest -v
```

### Test Suite Breakdown

| Test Module | Tests | Scope Covered |
|---|---|---|
| `tests/test_api_ingest.py` | 5 | Multipart uploads, JSON/CSV/TXT fixtures, size limits, invalid syntax |
| `tests/test_api_patients_fhir.py` | 9 | Patient listing, record queries, bundle retrieval, direct FHIR resource access |
| `tests/test_benchmark_search.py` | 1 | Benchmark measuring query latency across 50 records (< 2.0s target) |
| `tests/test_fhir_mapping.py` | 5 | Resource mapping (Patient, DocumentReference, DiagnosticReport), reference integrity |
| `tests/test_frontend_and_api.py` | 5 | Static frontend mounting, accessibility landmarks, stats endpoint, UI flows |
| `tests/test_health.py` | 5 | Health endpoints, OpenAPI docs, static assets, root serving |
| `tests/test_ingestion.py` | 12 | Parsers, demographic/date normalization, edge cases (missing MRN, duplicates, conflicts) |
| `tests/test_persistence.py` | 5 | SQLite CRUD, transactional rollbacks, reconnect durability, quarantined records |
| `tests/test_search.py` | 18 | Embeddings, vector persistence, top-k ranking, metadata filters, validation errors |
| `tests/test_summarization.py` | 15 | Structured schema, <200 word enforcement, offline fallback, cache hit/invalidation |
| **Total** | **80** | **All 80 tests passing (100% pass rate)** |

### Measured Performance Benchmarks

Measured using `tests/test_benchmark_search.py` across 50 synthetic records on a standard CPU:
- **Indexing Duration (50 records):** ~0.28 seconds
- **Mean Query Latency:** **10.58 ms**
- **Assessment Target:** < 2000 ms (< 2.0s) — **Target met by a wide margin**

---

## Limitations & Future Improvements

While this assessment prototype fully satisfies all project milestones, the following improvements would be prioritized for a production-grade enterprise clinical system:

1. **Standard Clinical Terminology Mapping:**
   - *Current:* Preserves raw source clinical descriptions, categories, and observation values.
   - *Future:* Integrate external terminology microservices to map raw strings to standard ontologies (LOINC for lab tests, SNOMED CT for clinical findings, RxNorm for medications).
2. **Enterprise Scale & Vector Database:**
   - *Current:* Uses local SQLite and ChromaDB / EmbeddedVectorStore, optimized for single-node evaluation.
   - *Future:* Migrate to distributed vector search engines (e.g., Qdrant, Milvus, or pgvector) and task queues (Celery/Redis) to index millions of patient media files asynchronously.
3. **Security, Privacy & Authentication:**
   - *Current:* Open local-first assessment API without authentication.
   - *Future:* Implement SMART-on-FHIR OAuth2/OIDC access control, role-based authorization (clinician vs. auditor), column-level database encryption, and immutable audit logging complying with HIPAA §164.312.
4. **Enhanced Frontend Features:**
   - *Current:* Single-file upload via drag-and-drop; vanilla JS state management.
   - *Future:* Batch multi-file drag-and-drop, client-side export of summaries to signed PDF documents, and precompiled offline Tailwind CSS bundle for air-gapped deployments.

---

## Project Documentation

Key technical documentation and assessment deliverables are available in the `docs/` directory:

- [One-Page Technical Write-up (PDF)](docs/ONE_PAGE_WRITEUP.pdf) — Formal submission covering architecture, implementation decisions, trade-offs, and future improvements.
- [Architecture & Data Flow](docs/ARCHITECTURE.md) — System components, architecture, and data flow.
- [API Specification](docs/API_SPEC.md) — REST API endpoints, request formats, and response schemas.
- [FHIR R4 Mapping](docs/FHIR_MAPPING.md) — FHIR resource mapping and validation approach.
- [Testing Documentation](docs/TESTING.md) — Testing strategy, covered scenarios, and execution instructions.