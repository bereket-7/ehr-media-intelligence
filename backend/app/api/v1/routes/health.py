"""Health check and system statistics endpoints."""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.core.config import settings
from app.services.patient_service import patient_service
from app.services.search_service import search_service

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response payload."""
    status: str = Field(default="ok", description="Service health status")
    version: str = Field(default="0.1.0", description="Application version")
    environment: str = Field(default="development", description="Current runtime environment")


class SystemStatsResponse(BaseModel):
    """Real system and index statistics payload."""
    total_patients: int = Field(..., description="Total registered patients")
    total_records: int = Field(..., description="Total canonical clinical media records")
    total_vectors: int = Field(..., description="Total vectorized documents in vector storage")
    embedding_model: str = Field(..., description="Configured embedding model identifier")
    vector_store_type: str = Field(..., description="Active vector store adapter name")
    environment: str = Field(..., description="Current runtime environment")


@router.get("/health", response_model=HealthResponse, summary="Service health status")
async def get_health() -> HealthResponse:
    """Return basic service readiness and health."""
    return HealthResponse(
        status="ok",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
    )


@router.get("/stats", response_model=SystemStatsResponse, summary="System intelligence statistics")
async def get_system_stats() -> SystemStatsResponse:
    """Return live metrics regarding persisted patients, records, and vector indices."""
    patients = patient_service.list_patients()
    total_patients = len(patients)
    total_records = sum(p.get("record_count", 0) for p in patients)
    index_stats = search_service.get_index_stats()

    return SystemStatsResponse(
        total_patients=total_patients,
        total_records=total_records,
        total_vectors=index_stats.get("total_vectors", 0),
        embedding_model=index_stats.get("embedding_model", settings.EMBEDDING_MODEL_NAME),
        vector_store_type=index_stats.get("vector_store_type", "Unknown"),
        environment=settings.ENVIRONMENT,
    )
