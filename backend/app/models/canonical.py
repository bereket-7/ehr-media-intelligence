"""Canonical intermediate data models using Pydantic v2."""
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class AdministrativeGender(str, Enum):
    """FHIR R4 Administrative Gender codes."""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    UNKNOWN = "unknown"


class RecordType(str, Enum):
    """Categorization for clinical media records."""
    IMAGING = "imaging"
    LAB = "lab"
    CLINICAL_NOTE = "clinical_note"
    DISCHARGE_SUMMARY = "discharge_summary"
    PATHOLOGY = "pathology"
    OTHER = "other"


class IdentityStatus(str, Enum):
    """Identity resolution and quarantine status."""
    VERIFIED_SYNTHETIC = "verified_synthetic"
    MISSING_MRN = "missing"
    CONFLICT_QUARANTINED = "quarantined"


class AuditEntry(BaseModel):
    """Record-level transformation audit log entry."""
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of transformation",
    )
    action: str = Field(..., description="Action taken, e.g., 'normalize', 'quarantine', 'deduplicate'")
    field: str = Field(..., description="Target field transformed")
    before_value: Optional[str] = Field(default=None, description="Original raw value prior to transformation")
    after_value: Optional[str] = Field(default=None, description="Canonical value after transformation")
    reason: str = Field(..., description="Rationale for the transformation")


class PatientDemographics(BaseModel):
    """Normalized patient demographics."""
    display_name: str = Field(..., description="Normalized display name")
    original_name: Optional[str] = Field(default=None, description="Raw name as supplied")
    dob: Optional[str] = Field(default=None, description="Date of birth in ISO YYYY-MM-DD format")
    original_dob: Optional[str] = Field(default=None, description="Raw date of birth as supplied")
    gender: AdministrativeGender = Field(
        default=AdministrativeGender.UNKNOWN,
        description="FHIR administrative gender code",
    )
    original_gender: Optional[str] = Field(default=None, description="Raw gender as supplied")


class PatientIdentity(BaseModel):
    """Patient identifier resolution and conflict status."""
    patient_key: str = Field(..., description="Canonical internal patient key")
    mrn_normalized: Optional[str] = Field(default=None, description="Normalized MRN")
    mrn_original: Optional[str] = Field(default=None, description="Original raw MRN")
    source_identifiers: List[str] = Field(
        default_factory=list,
        description="List of raw source identifiers associated with patient",
    )
    identity_status: IdentityStatus = Field(
        default=IdentityStatus.VERIFIED_SYNTHETIC,
        description="Identity status (verified, missing MRN, or quarantined)",
    )
    conflict_reason: Optional[str] = Field(
        default=None,
        description="Reason if quarantined due to identifier conflict",
    )


class MediaRecord(BaseModel):
    """Canonical intermediate media record representation."""
    record_id: str = Field(..., description="Unique deterministic canonical record ID")
    patient_key: str = Field(..., description="Canonical internal patient key")
    patient_name: str = Field(..., description="Normalized patient display name")
    mrn_normalized: Optional[str] = Field(default=None, description="Normalized MRN")
    mrn_original: Optional[str] = Field(default=None, description="Original raw MRN")
    dob: Optional[str] = Field(default=None, description="Date of birth in ISO YYYY-MM-DD format")
    gender: AdministrativeGender = Field(
        default=AdministrativeGender.UNKNOWN,
        description="FHIR administrative gender",
    )
    record_date: Optional[str] = Field(default=None, description="Record date in ISO YYYY-MM-DD format")
    original_record_date: Optional[str] = Field(default=None, description="Raw record date")
    record_type: RecordType = Field(default=RecordType.OTHER, description="Normalized media category")
    title: str = Field(..., description="Record title or headline")
    text: str = Field(..., description="Traceable content text of the clinical record")
    source_file: str = Field(..., description="Filename of source data")
    source_index: int = Field(..., description="0-based row or item index in source file")
    encounter_id: Optional[str] = Field(default=None, description="Optional clinical encounter reference")
    fingerprint: str = Field(..., description="SHA-256 duplicate detection fingerprint")
    identity_status: IdentityStatus = Field(default=IdentityStatus.VERIFIED_SYNTHETIC)
    audit_trail: List[AuditEntry] = Field(
        default_factory=list,
        description="Audit entries documenting all transformations for this record",
    )


class IngestError(BaseModel):
    """Error encountered during parsing or record validation."""
    record_index: int = Field(..., description="Index of failed record in source")
    code: str = Field(..., description="Error classification code")
    message: str = Field(..., description="Descriptive error message")


class IngestResult(BaseModel):
    """Summary result of an ingestion operation."""
    accepted: int = Field(default=0, description="Count of accepted records")
    rejected: int = Field(default=0, description="Count of rejected or malformed records")
    duplicates: int = Field(default=0, description="Count of exact duplicate records suppressed")
    quarantined: int = Field(default=0, description="Count of records quarantined due to identity conflict")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings emitted")
    record_ids: List[str] = Field(default_factory=list, description="IDs of accepted records")
    errors: List[IngestError] = Field(default_factory=list, description="Fatal parse/validation errors")
    audit_log: List[AuditEntry] = Field(
        default_factory=list,
        description="Complete list of audit entries emitted during ingestion",
    )
