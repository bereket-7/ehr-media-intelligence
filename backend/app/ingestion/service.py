"""Ingestion service coordinating parsing, cleaning, conflict quarantine, and deduplication."""
from typing import Dict, List, Set
from app.ingestion.cleaner import DataCleaner
from app.ingestion.parsers import CsvParser, JsonParser, PlainTextParser
from app.models.canonical import (
    AuditEntry,
    IdentityStatus,
    IngestError,
    IngestResult,
    MediaRecord,
    PatientIdentity,
)


class IngestionService:
    """Service handling file ingestion, cleaning, deduplication, and identity resolution."""

    def __init__(self) -> None:
        self.records: Dict[str, MediaRecord] = {}
        self.seen_fingerprints: Set[str] = set()
        self.patient_identities: Dict[str, PatientIdentity] = {}
        self.patient_primary_names: Dict[str, str] = {}

    def clear(self) -> None:
        """Clear session state (useful for tests and reset)."""
        self.records.clear()
        self.seen_fingerprints.clear()
        self.patient_identities.clear()
        self.patient_primary_names.clear()

    def ingest_file(self, content: str, filename: str) -> IngestResult:
        """Parse, clean, deduplicate, and validate records from raw file content."""
        lower_name = filename.lower()
        if lower_name.endswith(".json"):
            raw_records = JsonParser.parse(content, filename)
        elif lower_name.endswith(".csv"):
            raw_records = CsvParser.parse(content, filename)
        elif lower_name.endswith((".txt", ".text", ".log")):
            raw_records = PlainTextParser.parse(content, filename)
        else:
            # Fallback auto-detection: try JSON then CSV then TXT
            content_stripped = content.strip()
            if content_stripped.startswith(("[", "{")):
                raw_records = JsonParser.parse(content, filename)
            elif "," in content_stripped.splitlines()[0] if content_stripped else False:
                raw_records = CsvParser.parse(content, filename)
            else:
                raw_records = PlainTextParser.parse(content, filename)

        return self.process_records(raw_records, filename)

    def process_records(
        self,
        raw_records: List[tuple[int, dict]],
        filename: str,
    ) -> IngestResult:
        """Clean and normalize a list of raw records."""
        result = IngestResult()

        for idx, raw in raw_records:
            audit: List[AuditEntry] = []

            # 1. Validate required clinical text
            text_raw = raw.get("text") or raw.get("content") or raw.get("note") or raw.get("narrative")
            clean_text = DataCleaner.normalize_string(text_raw)
            if not clean_text:
                result.rejected += 1
                result.errors.append(
                    IngestError(
                        record_index=idx,
                        code="empty_content",
                        message=f"Record at index {idx} contains empty clinical text; rejected.",
                    )
                )
                continue

            # 2. Normalize patient name
            raw_name = raw.get("patient_name") or raw.get("name") or raw.get("patient")
            norm_name, orig_name = DataCleaner.normalize_name(raw_name, audit)

            # 3. Normalize MRN
            raw_mrn = raw.get("mrn") or raw.get("patient_id") or raw.get("medical_record_number")
            norm_mrn, orig_mrn, id_status = DataCleaner.normalize_mrn(raw_mrn, norm_name, audit)

            # Canonical patient key
            patient_key = f"pat_{norm_mrn.lower().replace('-', '_')}"

            # 4. Normalize Demographics (Gender & DOB)
            raw_gender = raw.get("gender") or raw.get("sex")
            norm_gender, orig_gender = DataCleaner.normalize_gender(raw_gender, audit)

            raw_dob = raw.get("dob") or raw.get("birth_date") or raw.get("date_of_birth")
            norm_dob, orig_dob = DataCleaner.normalize_date(raw_dob, "dob", audit, result.warnings)

            # 5. Normalize Record Date & Category
            raw_date = raw.get("record_date") or raw.get("date") or raw.get("service_date")
            norm_date, orig_date = DataCleaner.normalize_date(raw_date, "record_date", audit, result.warnings)

            raw_type = raw.get("record_type") or raw.get("type") or raw.get("category")
            norm_type = DataCleaner.normalize_record_type(raw_type)

            raw_title = raw.get("title") or raw.get("headline") or raw.get("subject")
            norm_title = DataCleaner.normalize_string(raw_title)
            if not norm_title:
                norm_title = f"Synthetic {norm_type.value.capitalize()} Record"
                audit.append(
                    AuditEntry(
                        action="normalize",
                        field="title",
                        before_value=str(raw_title),
                        after_value=norm_title,
                        reason="Missing record title; derived default title from record type",
                    )
                )

            encounter_id = DataCleaner.normalize_string(raw.get("encounter_id"))

            # 6. Identity Resolution and Conflict Detection
            if norm_mrn in self.patient_primary_names:
                registered_name = self.patient_primary_names[norm_mrn]
                if registered_name.lower() != norm_name.lower():
                    # Flag identity conflict!
                    conflict_reason = (
                        f"Identity conflict: MRN '{norm_mrn}' previously bound to '{registered_name}', "
                        f"received with conflicting patient name '{norm_name}'."
                    )
                    id_status = IdentityStatus.CONFLICT_QUARANTINED
                    result.quarantined += 1
                    result.warnings.append(conflict_reason)
                    audit.append(
                        AuditEntry(
                            action="quarantine",
                            field="patient_identity",
                            before_value=norm_name,
                            after_value=registered_name,
                            reason=conflict_reason,
                        )
                    )
            else:
                self.patient_primary_names[norm_mrn] = norm_name
                self.patient_identities[norm_mrn] = PatientIdentity(
                    patient_key=patient_key,
                    mrn_normalized=norm_mrn,
                    mrn_original=orig_mrn,
                    source_identifiers=[str(raw_mrn)] if raw_mrn else [],
                    identity_status=id_status,
                )

            # 7. Duplicate Fingerprinting
            fingerprint = DataCleaner.compute_fingerprint(
                patient_key=patient_key,
                record_type=norm_type,
                record_date=norm_date,
                text=clean_text,
            )

            if fingerprint in self.seen_fingerprints:
                result.duplicates += 1
                result.warnings.append(
                    f"Record at index {idx} is an exact duplicate of a previously indexed record; suppressed."
                )
                audit.append(
                    AuditEntry(
                        action="deduplicate",
                        field="record",
                        before_value=fingerprint,
                        after_value="suppressed",
                        reason="Exact match for (patient_key, record_type, record_date, text); record deduplicated",
                    )
                )
                result.audit_log.extend(audit)
                continue

            self.seen_fingerprints.add(fingerprint)

            # 8. Deterministic Stable Record ID
            record_id = f"rec_{patient_key}_{norm_type.value}_{fingerprint[:8]}"

            canonical_record = MediaRecord(
                record_id=record_id,
                patient_key=patient_key,
                patient_name=norm_name,
                mrn_normalized=norm_mrn,
                mrn_original=orig_mrn,
                dob=norm_dob,
                gender=norm_gender,
                record_date=norm_date,
                original_record_date=orig_date,
                record_type=norm_type,
                title=norm_title,
                text=clean_text,
                source_file=filename,
                source_index=idx,
                encounter_id=encounter_id,
                fingerprint=fingerprint,
                identity_status=id_status,
                audit_trail=audit,
            )

            self.records[record_id] = canonical_record
            result.accepted += 1
            result.record_ids.append(record_id)
            result.audit_log.extend(audit)

        return result


# Shared singleton instance
ingestion_service = IngestionService()
