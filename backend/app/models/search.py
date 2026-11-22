"""Pydantic v2 models for semantic search requests, responses, and filtering."""
from datetime import date
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class SearchFilters(BaseModel):
    """Optional search filters applied prior to or during vector retrieval."""

    resource_type: Optional[str] = Field(
        default=None,
        description="Filter by FHIR resource type: 'DocumentReference', 'DiagnosticReport', etc.",
    )
    date_from: Optional[str] = Field(
        default=None,
        description="Inclusive start date filter in ISO YYYY-MM-DD format",
    )
    date_to: Optional[str] = Field(
        default=None,
        description="Inclusive end date filter in ISO YYYY-MM-DD format",
    )
    patient_id: Optional[str] = Field(
        default=None,
        description="Optional filter by patient_key or normalized MRN",
    )

    @field_validator("date_from", "date_to", mode="before")
    @classmethod
    def validate_iso_date(cls, value: Optional[str]) -> Optional[str]:
        """Ensure date strings conform to ISO YYYY-MM-DD syntax."""
        if value is None or str(value).strip() == "":
            return None
        val_str = str(value).strip()
        try:
            date.fromisoformat(val_str)
        except ValueError as exc:
            raise ValueError(f"Date '{val_str}' must be a valid ISO format (YYYY-MM-DD)") from exc
        return val_str

    @model_validator(mode="after")
    def validate_date_range(self) -> "SearchFilters":
        """Verify that date_from does not occur after date_to."""
        if self.date_from and self.date_to:
            d_from = date.fromisoformat(self.date_from)
            d_to = date.fromisoformat(self.date_to)
            if d_from > d_to:
                raise ValueError(
                    f"date_from ({self.date_from}) cannot be after date_to ({self.date_to})"
                )
        return self


class SearchRequest(BaseModel):
    """Search request payload for semantic clinical record discovery."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Natural language query string describing clinical findings or record concepts",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of semantically ranked results to retrieve (default: 5, max: 20)",
    )
    filters: Optional[SearchFilters] = Field(
        default=None,
        description="Optional search filters for resource type, date range, and patient ID",
    )

    @field_validator("query", mode="before")
    @classmethod
    def validate_non_empty_query(cls, value: str) -> str:
        """Reject empty or whitespace-only queries."""
        if not value or not str(value).strip():
            raise ValueError("Query string cannot be empty or whitespace-only")
        return str(value).strip()


class SearchResultItem(BaseModel):
    """Individual ranked search match grounded in a persisted clinical record."""

    rank: int = Field(..., description="1-based relevance rank")
    record_id: str = Field(..., description="Unique canonical record identifier")
    patient_id: str = Field(..., description="Canonical patient key or MRN")
    title: str = Field(..., description="Clinical record or document title")
    record_type: str = Field(..., description="Record category: imaging, lab, note, summary")
    resource_type: str = Field(..., description="Mapped FHIR resource type: DocumentReference or DiagnosticReport")
    record_date: Optional[str] = Field(default=None, description="Clinical record date in YYYY-MM-DD format")
    excerpt: str = Field(..., description="Verbatim source text excerpt grounded in the persisted record")
    similarity_score: float = Field(
        ...,
        description="Cosine similarity score in range [0, 1] reflecting vector proximity (not clinical probability)",
    )
    distance: float = Field(
        ...,
        description="Cosine distance (1 - similarity_score)",
    )
    source_reference: Optional[str] = Field(
        default=None,
        description="Reference to origin file or ingestion batch",
    )
    fhir_resource_id: Optional[str] = Field(
        default=None,
        description="Identifier of the mapped FHIR resource in SQLite persistence",
    )


class SearchResponse(BaseModel):
    """Validated structured response for semantic search queries."""

    query: str = Field(..., description="The evaluated search query")
    total_results: int = Field(..., description="Total number of results returned")
    results: List[SearchResultItem] = Field(default_factory=list, description="Ranked list of relevant records")
    disclaimer: str = Field(
        default=(
            "ADVISORY NOTICE: Search scores reflect geometric vector similarity across synthetic records, "
            "not clinical confidence, diagnostic probability, or medical verification."
        ),
        description="Mandatory advisory notice regarding semantic ranking scores",
    )
    search_latency_ms: float = Field(
        ...,
        description="Measured query search latency in milliseconds (excluding model loading)",
    )
