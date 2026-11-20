"""API v1 router."""
from fastapi import APIRouter
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.ingest import router as ingest_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health_router, tags=["Health"])
api_v1_router.include_router(ingest_router, tags=["Ingestion"])

__all__ = ["api_v1_router"]
