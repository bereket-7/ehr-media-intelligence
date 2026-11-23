# Architecture and Design Decisions

## Overall architecture
Use a single FastAPI application for the assessment. Static frontend assets may be served by FastAPI to simplify local startup. Keep route handlers thin; business logic belongs in services and persistence behind repositories.

## Layers
- **API:** request validation, response schemas, HTTP status codes, dependency wiring.
- **Ingestion:** parsers for JSON, CSV, TXT; source-record extraction and error collection.
- **Normalization:** canonical models, field normalization, duplicate detection, identity conflict flags, audit entries.
- **FHIR mapping:** create and validate resources/Bundles; use stable references and patient subject links.
- **Summarization:** provider adapter, prompt builder, schema parsing, cache, deterministic fallback.
- **Search:** text preparation, embedding generation, vector storage/retrieval, metadata filtering, score conversion.
- **Repositories:** SQLite storage for patients, normalized records, bundles, summaries, and audit; Chroma for vectors.
- **Frontend:** small accessible JS client; no direct DB access.

## Data flow
1. Upload/ingest sample file(s).
2. Parser emits source records with source filename, format, and row/record index.
3. Cleaner maps raw values to canonical schema; emits audit events and warnings.
4. Identity resolution links only exact, trusted identifiers or safe deterministic rules; conflicts are flagged for review.
5. FHIR mapper builds patient resources and media record resources; validation errors are collected.
6. Bundle persisted; document text and summary text are indexed.
7. Summary cache is checked; if miss, call configured LLM provider or deterministic fallback.
8. Search query is embedded; vector results are filtered/ranked; response includes traceable source record IDs.
9. Frontend renders results and details.

## Suggested module boundaries
`app/api/` routes; `app/models/` schemas; `app/services/` logic; `app/repositories/` persistence; `app/ingestion/` parsers; `app/core/` configuration, logging, errors. Use `app/main.py` as composition root.

## Storage choices
- SQLite: normalized records, patient indexes, Bundle JSON, summaries, cache metadata, audit logs.
- ChromaDB: document embeddings and metadata. Persistent local directory, configurable path.
- Keep file paths configurable; don't commit runtime DB/vector-store files.

## Design trade-offs
- Local transformer embeddings avoid paid APIs and demonstrate reproducibility, but first-run model download and CPU latency may be noticeable. Document this and provide a configurable model name.
- Chroma is convenient for metadata filtering; its score semantics must be interpreted consistently.
- Vanilla JS minimizes build tooling and focuses effort on backend features. Use accessible HTML and modular frontend code.
- FHIR library version compatibility can be sensitive; pin a working version and test validation early.
- A deterministic summary fallback ensures app demo works offline, but must be labeled as not LLM-generated.

## Error handling
Return clear validation errors for invalid uploads, parser failures, and malformed query parameters. Partial ingest may be supported, but failed records must be counted and exposed. Avoid swallowing exceptions. Log internal details safely without logging full sensitive record contents.
