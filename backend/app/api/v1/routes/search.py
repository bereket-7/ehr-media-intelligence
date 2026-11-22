"""Semantic search API routes."""
from fastapi import APIRouter, HTTPException, status
from app.core.logging import get_logger
from app.models.search import SearchRequest, SearchResponse
from app.services.search_service import search_service

logger = get_logger(__name__)
router = APIRouter()


@router.post(
    "/search",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic clinical record search",
    description=(
        "Executes natural language semantic queries against persisted synthetic EHR media records. "
        "Supports optional filtering by FHIR resource type, ISO date ranges, and patient ID."
    ),
)
async def semantic_search(request: SearchRequest) -> SearchResponse:
    """Execute natural language semantic search across clinical records."""
    try:
        response = search_service.search(request)
        return response
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        ) from ve
    except Exception as exc:
        logger.error("Unhandled error during semantic search query: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while executing semantic search.",
        ) from exc
