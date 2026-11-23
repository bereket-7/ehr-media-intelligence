# Testing and Quality Plan

## Test categories
### Unit tests
- Normalization of name, MRN, gender, dates.
- Missing identifiers and required content handling.
- Ambiguous date policy.
- Duplicate fingerprints and duplicate detection.
- Conflicting identifier quarantine.
- Audit entries emitted for transformations.
- FHIR resource construction and field validation.
- Bundle reference resolution.
- Summary word limit, disclaimer, source grounding/schema validation.
- Summary cache hit and invalidation.
- Search filters, top-five cap, metadata correctness.

### API tests
- Health route.
- Ingest valid JSON/CSV/TXT.
- Ingest invalid upload and parser errors.
- Patient list/detail, summary, bundle retrieval.
- Search request validation and filtering.
- Error responses avoid stack trace disclosure.

### Frontend/manual smoke test
- Search query submit and results display.
- Type/date filters and reset.
- Loading state and disabled repeat-submit behavior.
- Empty/error/retry states.
- Open/close detail modal, Escape, focus return.
- Keyboard-only search and result activation.
- Responsive viewport.

## Commands
Use the project's actual environment and configured tools. At minimum:
```bash
pytest
```
If lint/type-check/format commands are configured, run them and document results. Do not report a test as passed unless the command was executed and passed.

## Performance test
Measure semantic search with 50 synthetic records after model load and vector initialization. Run multiple warm queries, report median (and optionally p95), machine/environment, vector count, and what the measurement includes. Keep cold startup/download separate.

## Summary quality rubric (synthetic only)
Score each sample 0–2 for: source factuality, key information coverage, date correctness, uncertainty handling, unsupported assertions (reverse-scored), structure/disclaimer. Record evaluator notes. Do not claim clinical validation; this is an engineering sanity check.
