"""Composition root for the EHR Media Intelligence Platform FastAPI application."""
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import api_v1_router
from app.api.v1.routes.health import router as root_health_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown events."""
    configure_logging()
    logger.info(
        "Starting %s v%s [env=%s, debug=%s]",
        settings.PROJECT_NAME,
        settings.VERSION,
        settings.ENVIRONMENT,
        settings.DEBUG,
    )
    yield
    logger.info("Shutting down %s", settings.PROJECT_NAME)


def create_application() -> FastAPI:
    """Application factory for FastAPI."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=(
            "A local-first assessment prototype for ingesting synthetic, "
            "unstructured EHR media records, cleaning and normalizing them, "
            "mapping to FHIR R4, and enabling semantic search."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Root health endpoint (per docs/API_SPEC.md: GET /health)
    app.include_router(root_health_router, tags=["Health"])

    # API v1 routes
    app.include_router(api_v1_router)

    # Error Handlers: Protect against stack trace leaks
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning("Validation error on %s %s: %s", request.method, request.url.path, exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "Validation Error",
                "details": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled exception processing %s %s: %s", request.method, request.url.path, str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred. Please consult server logs.",
            },
        )

    # Static frontend assets
    frontend_dir = Path(settings.FRONTEND_DIR)
    if frontend_dir.exists() and frontend_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

        @app.get("/", include_in_schema=False)
        async def serve_index() -> FileResponse:
            index_path = frontend_dir / "index.html"
            if index_path.exists():
                return FileResponse(str(index_path))
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"message": "Frontend index.html not found"},
            )

    return app


app = create_application()
