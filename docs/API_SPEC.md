# API Specification (MVP)
Base URL in local development: `http://127.0.0.1:8000`. FastAPI OpenAPI docs at `/docs`.


## `GET /health`
Returns service status and basic readiness (avoid implying external model readiness unless checked).

Example response:
```json
{"status":"ok"}
```

## `POST /ingest`
Accept file uploads for supported JSON, CSV, or TXT types. Process records through parsing and cleaning. Return counts, successful record IDs, warnings, and validation failures. Decide and document whether this endpoint is single-file or multi-file; prefer single-file initially for simplicity.

Suggested response:
```json
{
  "accepted": 12,
  "rejected": 1,
  "duplicates": 2,
  "warnings": ["Record 4 missing date; retained with unknown date"],
  "record_ids": ["rec_..."],
  "errors": [{"record_index": 8, "code": "invalid_record", "message": "..."}]
}
```

## `GET /patients`
Return patient list with canonical identifiers and record counts. Only synthetic fixture data is expected in the assessment environment.


## `GET /patients/{patient_id}`
Return patient metadata and linked record summary metadata. Do not expose raw internals unless appropriate for the prototype.


## `GET /patients/{patient_id}/summary`
Return cached/generated summary object. Include `generated_by` (`llm` or `fallback`), generated timestamp, source hash, disclaimer, and structured fields.


## `GET /patients/{patient_id}/bundle`
Return the saved FHIR Bundle JSON and validation status/report. If no Bundle exists, return a clear 404 or regenerate only if documented.


## `POST /search`
Request:
```json
{
  "query": "recent chest imaging with possible pneumonia",
  "top_k": 5
}
```
Query parameters:
- `resource_type` optional; accepted FHIR resource types, validate values.
- `date_from` optional ISO date inclusive.
- `date_to` optional ISO date inclusive.
- `top_k` body value; cap at 5 regardless of request.

Response shape:
```json
{
  "query": "recent chest imaging with possible pneumonia",
  "results": [
    {
      "patient_id": "synthetic-patient-01",
      "patient_name": "Example Synthetic Patient",
      "mrn": "SYN-001",
      "record_id": "record-001",
      "resource_type": "DocumentReference",
      "record_date": "2025-01-12",
      "score": 0.72,
      "score_type": "normalized_relevance",
      "snippet": "Synthetic record excerpt ...",
      "summary_snippet": "...",
      "bundle_reference": "DocumentReference/doc-001"
    }
  ]
}
```

## API conventions
- Use Pydantic request/response schemas.
- Return `400` for invalid inputs, `413` for upload size limits, `422` for validation errors, and `500` for unexpected server errors without exposing stack traces.
- Return empty `results` rather than an error when a valid query has no matches.
- Keep date filter semantics inclusive and document them.
- Do not return raw embedding vectors.
