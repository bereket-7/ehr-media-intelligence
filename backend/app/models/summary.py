"""Pydantic v2 models for clinical summarization."""
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class RecentRecordSummary(BaseModel):
    """Concise metadata reference to an individual clinical record."""
    record_id: str = Field(..., description="Canonical ID of the source record")
    record_type: str = Field(..., description="Normalized record category/type")
    title: str = Field(..., description="Record headline or title")
    record_date: Optional[str] = Field(default=None, description="Document date in ISO format or None")
    brief_finding: str = Field(..., description="Brief one-line factual finding from the record")


class ClinicalSummary(BaseModel):
    """Validated patient-level clinical intelligence summary."""
    patient_id: str = Field(..., description="Canonical patient identifier/key")
    patient_name: str = Field(..., description="Normalized patient display name")
    mrn: Optional[str] = Field(default=None, description="Normalized MRN or None")
    chief_concern: str = Field(..., description="Chief concern or primary clinical context")
    key_diagnoses: List[str] = Field(
        default_factory=list,
        description="Documented clinical diagnoses strictly extracted from records",
    )
    recent_records: List[RecentRecordSummary] = Field(
        default_factory=list,
        description="Structured references to recent records",
    )
    key_findings: List[str] = Field(
        default_factory=list,
        description="Notable objective clinical observations and test findings",
    )
    flagged_anomalies: List[str] = Field(
        default_factory=list,
        description="Document-stated abnormalities or out-of-range lab markers",
    )
    data_quality_issues: List[str] = Field(
        default_factory=list,
        description="Inconsistencies, missing dates/DOB, or ambiguities in source data",
    )
    narrative_summary: str = Field(
        ...,
        description="Structured clinical narrative summary strictly under 200 words",
    )
    word_count: int = Field(
        default=0,
        description="Word count of the narrative summary",
    )
    confidence_or_limitations: str = Field(
        ...,
        description="Explanation of missing, sparse, or ambiguous information in source records",
    )
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of summary generation",
    )
    generated_by: str = Field(
        ...,
        description="Generator category: 'llm' or 'fallback'",
    )
    is_ai_generated: bool = Field(
        ...,
        description="Boolean indicating whether an external LLM was utilized",
    )
    provider: str = Field(..., description="Provider name e.g. 'openai' or 'deterministic_fallback'")
    model: str = Field(..., description="Model identifier used for generation")
    cache_status: str = Field(
        default="miss",
        description="Cache status for this request: 'hit' or 'miss'",
    )
    source_record_ids: List[str] = Field(
        default_factory=list,
        description="IDs of all patient source records grounded in this summary",
    )
    source_records_hash: str = Field(
        ...,
        description="SHA-256 fingerprint hash of input records",
    )
    disclaimer: str = Field(
        default=(
            "ADVISORY NOTICE: This summary is generated for prototype demonstration purposes only, "
            "may contain inaccuracies or omissions, and does NOT constitute clinical advice, diagnosis, "
            "or a medical decision."
        ),
        description="Clinical prototype advisory disclaimer",
    )

    @field_validator("word_count", mode="before")
    @classmethod
    def calculate_word_count(cls, v: int, info) -> int:
        """Automatically calculate word count from narrative_summary if not provided or 0."""
        narrative = info.data.get("narrative_summary", "")
        calculated = len(narrative.split()) if narrative else 0
        return calculated if (v is None or v == 0) else v
