"""Data normalization, demographic resolution, duplicate fingerprinting, and audit logging."""
import hashlib
import re
from datetime import datetime
from typing import Any, List, Optional, Tuple

from app.models.canonical import (
    AdministrativeGender,
    AuditEntry,
    IdentityStatus,
    RecordType,
)


class DataCleaner:
    """Clinical record cleaner and normalizer."""

    DATE_FORMATS = [
        "%Y-%m-%d",       # 2025-01-15
        "%m/%d/%Y",       # 01/15/2025 (Standard US clinical format)
        "%Y/%m/%d",       # 2025/01/15
        "%d-%m-%Y",       # 15-01-2025
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
    ]

    GENDER_MAP = {
        "m": AdministrativeGender.MALE,
        "male": AdministrativeGender.MALE,
        "man": AdministrativeGender.MALE,
        "boy": AdministrativeGender.MALE,
        "f": AdministrativeGender.FEMALE,
        "female": AdministrativeGender.FEMALE,
        "woman": AdministrativeGender.FEMALE,
        "girl": AdministrativeGender.FEMALE,
        "other": AdministrativeGender.OTHER,
        "nonbinary": AdministrativeGender.OTHER,
        "non-binary": AdministrativeGender.OTHER,
        "o": AdministrativeGender.OTHER,
        "u": AdministrativeGender.UNKNOWN,
        "unknown": AdministrativeGender.UNKNOWN,
        "unk": AdministrativeGender.UNKNOWN,
    }

    RECORD_TYPE_MAP = {
        "imaging": RecordType.IMAGING,
        "radiology": RecordType.IMAGING,
        "x-ray": RecordType.IMAGING,
        "ct": RecordType.IMAGING,
        "mri": RecordType.IMAGING,
        "ultrasound": RecordType.IMAGING,
        "lab": RecordType.LAB,
        "laboratory": RecordType.LAB,
        "blood": RecordType.LAB,
        "pathology": RecordType.PATHOLOGY,
        "biopsy": RecordType.PATHOLOGY,
        "clinical_note": RecordType.CLINICAL_NOTE,
        "note": RecordType.CLINICAL_NOTE,
        "progress_note": RecordType.CLINICAL_NOTE,
        "discharge_summary": RecordType.DISCHARGE_SUMMARY,
        "discharge": RecordType.DISCHARGE_SUMMARY,
    }

    @classmethod
    def normalize_string(cls, val: Any) -> Optional[str]:
        """Trim surrounding whitespace and collapse internal duplicate spaces."""
        if val is None:
            return None
        text = str(val).strip()
        if not text:
            return None
        return re.sub(r"\s+", " ", text)

    @classmethod
    def normalize_name(cls, raw_name: Optional[str], audit: List[AuditEntry]) -> Tuple[str, Optional[str]]:
        """Normalize patient display name while preserving original."""
        clean = cls.normalize_string(raw_name)
        if not clean:
            clean = "Unknown Patient"
            audit.append(
                AuditEntry(
                    action="normalize",
                    field="patient_name",
                    before_value=str(raw_name),
                    after_value=clean,
                    reason="Missing patient name; assigned fallback label",
                )
            )
        elif clean != raw_name:
            audit.append(
                AuditEntry(
                    action="normalize",
                    field="patient_name",
                    before_value=str(raw_name),
                    after_value=clean,
                    reason="Normalized excessive or leading/trailing whitespace",
                )
            )
        return clean, raw_name

    @classmethod
    def normalize_mrn(
        cls,
        raw_mrn: Optional[str],
        patient_name: str,
        audit: List[AuditEntry],
    ) -> Tuple[str, Optional[str], IdentityStatus]:
        """Normalize medical record number or assign synthetic key if missing."""
        clean = cls.normalize_string(raw_mrn)
        if not clean:
            name_hash = hashlib.sha256(patient_name.encode("utf-8")).hexdigest()[:8].upper()
            fallback_mrn = f"SYN-MISSING-{name_hash}"
            audit.append(
                AuditEntry(
                    action="impute_synthetic_key",
                    field="mrn",
                    before_value=str(raw_mrn),
                    after_value=fallback_mrn,
                    reason="MRN absent; assigned deterministic synthetic placeholder key",
                )
            )
            return fallback_mrn, raw_mrn, IdentityStatus.MISSING_MRN

        normalized = re.sub(r"[^\w\-]", "", clean).upper()
        if normalized != clean:
            audit.append(
                AuditEntry(
                    action="normalize",
                    field="mrn",
                    before_value=str(raw_mrn),
                    after_value=normalized,
                    reason="Removed non-standard punctuation and uppercased MRN",
                )
            )
        return normalized, raw_mrn, IdentityStatus.VERIFIED_SYNTHETIC

    @classmethod
    def normalize_gender(
        cls,
        raw_gender: Optional[str],
        audit: List[AuditEntry],
    ) -> Tuple[AdministrativeGender, Optional[str]]:
        """Map recognized gender representations to FHIR administrative code."""
        clean = cls.normalize_string(raw_gender)
        if not clean:
            return AdministrativeGender.UNKNOWN, raw_gender

        key = clean.lower()
        if key in cls.GENDER_MAP:
            mapped = cls.GENDER_MAP[key]
            if clean != mapped.value:
                audit.append(
                    AuditEntry(
                        action="normalize",
                        field="gender",
                        before_value=str(raw_gender),
                        after_value=mapped.value,
                        reason=f"Mapped '{clean}' to standard FHIR administrative gender '{mapped.value}'",
                    )
                )
            return mapped, raw_gender

        audit.append(
            AuditEntry(
                action="normalize",
                field="gender",
                before_value=str(raw_gender),
                after_value=AdministrativeGender.UNKNOWN.value,
                reason=f"Unrecognized gender representation '{raw_gender}'; defaulted to 'unknown'",
            )
        )
        return AdministrativeGender.UNKNOWN, raw_gender

    @classmethod
    def normalize_date(
        cls,
        raw_date: Optional[str],
        field_name: str,
        audit: List[AuditEntry],
        warnings: List[str],
    ) -> Tuple[Optional[str], Optional[str]]:
        """Normalize date strings into ISO YYYY-MM-DD.

        If parsing is ambiguous or invalid, retains None and logs an audit entry.
        """
        clean = cls.normalize_string(raw_date)
        if not clean:
            return None, raw_date

        for fmt in cls.DATE_FORMATS:
            try:
                parsed = datetime.strptime(clean, fmt)
                iso_date = parsed.strftime("%Y-%m-%d")
                if iso_date != clean:
                    audit.append(
                        AuditEntry(
                            action="normalize",
                            field=field_name,
                            before_value=clean,
                            after_value=iso_date,
                            reason=f"Converted date format '{fmt}' to ISO YYYY-MM-DD",
                        )
                    )
                return iso_date, raw_date
            except ValueError:
                continue

        warning_msg = f"{field_name} '{raw_date}' could not be parsed as a supported unambiguous date format"
        warnings.append(warning_msg)
        audit.append(
            AuditEntry(
                action="quarantine_field",
                field=field_name,
                before_value=clean,
                after_value=None,
                reason="Unambiguous date parsing failed; field left empty to prevent incorrect clinical dates",
            )
        )
        return None, raw_date

    @classmethod
    def normalize_record_type(cls, raw_type: Optional[str]) -> RecordType:
        """Map record category string to RecordType enum."""
        clean = cls.normalize_string(raw_type)
        if not clean:
            return RecordType.OTHER
        key = clean.lower().replace(" ", "_")
        return cls.RECORD_TYPE_MAP.get(key, RecordType.OTHER)

    @classmethod
    def compute_fingerprint(
        cls,
        patient_key: str,
        record_type: RecordType,
        record_date: Optional[str],
        text: str,
    ) -> str:
        """Compute stable SHA-256 duplicate fingerprint."""
        norm_text = re.sub(r"\s+", " ", text.lower().strip())
        content_key = f"{patient_key}|{record_type.value}|{record_date or ''}|{norm_text}"
        return hashlib.sha256(content_key.encode("utf-8")).hexdigest()
