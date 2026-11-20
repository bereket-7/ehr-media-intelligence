"""Health check endpoint."""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.core.config import settings

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response payload."""
    status: str = Field(default="ok", description="Service health status")
    version: str = Field(default="0.1.0", description="Application version")
    environment: str = Field(default="development", description="Current runtime environment")


@router.get("/health", response_model=HealthResponse, summary="Service health status")
async def get_health() -> HealthResponse:
    """Return basic service readiness and health."""
    return HealthResponse(
        status="ok",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
    )
