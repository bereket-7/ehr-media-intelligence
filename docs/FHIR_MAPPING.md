# FHIR R4 Mapping and Validation

Use the R4 version of `fhir.resources`; pin a compatible release and test resource construction early. All examples/data must be synthetic.


## Minimum resources
### Patient
- `id`: deterministic internal resource ID (FHIR-safe).
- `identifier`: MRN as identifier with an explicit system URI for the demo namespace.
- `name`: `HumanName` from normalized name.
- `birthDate`: include only if valid.
- `gender`: one of FHIR administrative gender codes (`male`, `female`, `other`, `unknown`).

### DocumentReference
Use for source media/document metadata and content. Populate required fields for the pinned library version, including status, type/category where applicable, date, subject reference, and description. Avoid embedding large raw document bodies unless justified; for local demo, a clearly synthetic excerpt or attachment content can be used with safe handling.

### DiagnosticReport
Use for lab or diagnostic report records where appropriate. Set required status/category/code/date/subject and results as appropriate for the record type. For textual results that cannot be safely mapped to a standardized Observation, retain narrative in the appropriate text representation and do not invent codes. If `Observation` resources are added, they are optional and should be documented.


## Bundle
- Bundle type: use `collection` for a package of related resources unless a different transaction semantics is truly needed.
- Include Patient and relevant record resources.
- Each `entry.fullUrl` must be unique and valid (e.g., `urn:uuid:<uuid>`). Resource IDs must be deterministic where practical.
- References such as `DocumentReference.subject` and `DiagnosticReport.subject` must resolve to the Patient in the Bundle.
- If Encounter is not implemented, do not create an encounter reference. The assessment mentions encounter references conditionally; no Encounter resource is required unless added.
- Ensure subject reference consistency and no broken references.

## Validation
- Validate each resource and Bundle using the library, not only custom checks.
- Collect failures by patient and resource with path/message; return readable report and do not silently skip invalid resources.
- Add project-level Bundle reference checks for entries/fullUrls and subjects, in addition to schema validation.
- Report the library's supported validation scope honestly; don't claim official validator/terminology validation unless actually performed.

## Persistence
Store serialized Bundle JSON and validation report in SQLite or file storage. Ensure retrieval round-trips and tests verify stored JSON parses and retains references.
