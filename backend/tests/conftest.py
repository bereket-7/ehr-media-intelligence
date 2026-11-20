"""Pytest test configuration and fixtures."""
from typing import Generator
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    """Test client fixture configured with the application instance."""
    with TestClient(app=app, base_url="http://testserver") as test_client:
        yield test_client
