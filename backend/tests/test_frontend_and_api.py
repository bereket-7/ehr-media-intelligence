"""Integration tests for frontend asset serving, UI endpoints, and system stats.

Verifies Milestone 5 requirements:
- Single-page application serving at GET /
- Static asset availability (/static/css/styles.css, /static/js/app.js)
- System statistics endpoint (GET /api/v1/stats)
- UI-consumed endpoints for search, patient exploration, AI summarization, and ingestion.
"""
from fastapi import status
from fastapi.testclient import TestClient


def test_index_html_has_accessible_structure(client: TestClient) -> None:
    """Verify that GET / returns the HTML containing accessibility landmarks and required UI containers."""
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert "text/html" in response.headers.get("content-type", "")

    html = response.text

    # Verify accessibility landmarks
    assert 'href="#main-content"' in html
    assert 'id="main-content"' in html
    assert 'aria-label="Application Sections"' in html
    assert 'aria-live="polite"' in html

    # Verify safety disclaimer
    assert "ENGINEERING PROTOTYPE" in html
    assert "Synthetic Demo Data Only" in html

    # Verify tab navigation buttons
    assert 'id="nav-search-btn"' in html
    assert 'id="nav-patients-btn"' in html
    assert 'id="nav-ingest-btn"' in html
    assert 'id="nav-fhir-btn"' in html

    # Verify modal dialog structure
    assert 'id="detail-modal"' in html
    assert 'role="dialog"' in html
    assert 'aria-modal="true"' in html


def test_static_css_and_js_served(client: TestClient) -> None:
    """Verify CSS and JavaScript client files are reachable via /static mount."""
    css_res = client.get("/static/css/styles.css")
    assert css_res.status_code == status.HTTP_200_OK
    assert len(css_res.text) > 50
    assert "focus-visible" in css_res.text

    js_res = client.get("/static/js/app.js")
    assert js_res.status_code == status.HTTP_200_OK
    assert len(js_res.text) > 1000
    assert "DOMContentLoaded" in js_res.text


def test_stats_endpoints(client: TestClient) -> None:
    """Verify system metrics endpoint returns accurate structural statistics."""
    for path in ["/api/v1/stats", "/stats"]:
        res = client.get(path)
        assert res.status_code == status.HTTP_200_OK
        data = res.json()

        assert "total_patients" in data
        assert "total_records" in data
        assert "total_vectors" in data
        assert "embedding_model" in data
        assert "vector_store_type" in data
        assert isinstance(data["total_patients"], int)
        assert isinstance(data["total_records"], int)
        assert isinstance(data["total_vectors"], int)


def test_frontend_search_integration(client: TestClient) -> None:
    """Verify the search endpoint used by the frontend search view returns well-formed results."""
    payload = {
        "query": "Patient with elevated blood glucose and diabetes",
        "top_k": 5,
    }
    res = client.post("/api/v1/search", json=payload)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()

    assert "query" in data
    assert "total_results" in data
    assert "results" in data
    assert isinstance(data["results"], list)

    for item in data["results"]:
        assert "record_id" in item
        assert "similarity_score" in item
        assert 0.0 <= item["similarity_score"] <= 1.0


def test_frontend_patient_workflow(client: TestClient) -> None:
    """Verify patient directory and detail endpoints consumed by the modal."""
    # 1. Fetch patient list
    patients_res = client.get("/api/v1/patients")
    assert patients_res.status_code == status.HTTP_200_OK
    patients = patients_res.json()
    assert isinstance(patients, list)

    if len(patients) > 0:
        patient_id = patients[0]["id"]

        # 2. Fetch records
        rec_res = client.get(f"/api/v1/patients/{patient_id}/records")
        assert rec_res.status_code == status.HTTP_200_OK
        assert isinstance(rec_res.json(), list)

        # 3. Fetch summary
        sum_res = client.get(f"/api/v1/patients/{patient_id}/summary")
        assert sum_res.status_code == status.HTTP_200_OK
        summary_data = sum_res.json()
        assert "chief_concern" in summary_data
        assert "disclaimer" in summary_data
        assert "is_ai_generated" in summary_data

        # 4. Fetch FHIR Bundle
        bundle_res = client.get(f"/api/v1/patients/{patient_id}/bundle")
        assert bundle_res.status_code == status.HTTP_200_OK
        bundle_data = bundle_res.json()
        assert bundle_data.get("resourceType") == "Bundle"
