"""API v1 router."""
from fastapi import APIRouter
from app.api.v1.routes.fhir import router as fhir_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.ingest import router as ingest_router
from app.api.v1.routes.patients import router as patients_router
from app.api.v1.routes.search import router as search_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health_router, tags=["Health"])
api_v1_router.include_router(ingest_router, tags=["Ingestion"])
api_v1_router.include_router(patients_router, tags=["Patients"])
api_v1_router.include_router(search_router, tags=["Search"])
api_v1_router.include_router(fhir_router)

__all__ = ["api_v1_router"]
