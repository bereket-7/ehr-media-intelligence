"""Unit and smoke tests for the health check and root endpoints."""
from fastapi import status
from fastapi.testclient import TestClient


def test_health_endpoint_returns_ok(client: TestClient) -> None:
    """Verify that GET /health returns 200 and valid status payload per API spec."""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "environment" in data


def test_api_v1_health_endpoint(client: TestClient) -> None:
    """Verify that GET /api/v1/health is also routed and consistent."""
    response = client.get("/api/v1/health")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["status"] == "ok"


def test_root_serves_frontend(client: TestClient) -> None:
    """Verify that GET / returns the frontend single-page application."""
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert "text/html" in response.headers.get("content-type", "")
    assert "EHR Media Intelligence" in response.text
    assert "ENGINEERING PROTOTYPE" in response.text


def test_static_assets_mounted(client: TestClient) -> None:
    """Verify that static CSS and JS assets are served properly."""
    css_response = client.get("/static/css/styles.css")
    assert css_response.status_code == status.HTTP_200_OK

    js_response = client.get("/static/js/app.js")
    assert js_response.status_code == status.HTTP_200_OK


def test_openapi_documentation_accessible(client: TestClient) -> None:
    """Verify that OpenAPI documentation is exposed at /docs and /openapi.json."""
    docs_response = client.get("/docs")
    assert docs_response.status_code == status.HTTP_200_OK

    openapi_response = client.get("/openapi.json")
    assert openapi_response.status_code == status.HTTP_200_OK
    schema = openapi_response.json()
    assert schema["info"]["title"] == "EHR Media Intelligence Platform"
