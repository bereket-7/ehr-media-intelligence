"""Pytest test configuration and fixtures."""
from typing import Generator
import pytest
from fastapi.testclient import TestClient

from app.ingestion.service import ingestion_service
from app.main import app
from app.repositories.database import initialize_database
from app.repositories.sqlite_repository import repository
from app.services.search_service import search_service


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    """Test client fixture configured with the application instance."""
    with TestClient(app=app, base_url="http://testserver") as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_database_and_services() -> Generator[None, None, None]:
    """Reset database tables, vector index, and ingestion caches before and after each test."""
    initialize_database()
    repository.clear_all()
    ingestion_service.clear()
    try:
        search_service.vector_store.clear()
    except Exception:
        pass
    yield
    repository.clear_all()
    ingestion_service.clear()
    try:
        search_service.vector_store.clear()
    except Exception:
        pass
