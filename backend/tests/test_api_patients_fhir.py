"""Integration tests for Patient and FHIR endpoints."""
from pathlib import Path
from fastapi import status
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data" / "synthetic"


def ingest_sample_data(client: TestClient) -> None:
    """Helper to seed synthetic patient records into the database."""
    json_path = DATA_DIR / "patients_records.json"
    with open(json_path, "rb") as f:
        client.post(
            "/ingest",
            files={"file": ("patients_records.json", f, "application/json")},
        )


def test_get_patients_list_returns_records(client: TestClient) -> None:
    """Verify GET /api/v1/patients returns populated patient list after ingestion."""
    ingest_sample_data(client)

    response = client.get("/api/v1/patients")
    assert response.status_code == status.HTTP_200_OK

    patients = response.json()
    assert len(patients) >= 4
    alex = next((p for p in patients if p["mrn_normalized"] == "SYN-PAT-001"), None)
    assert alex is not None
    assert alex["display_name"] == "Alex Rivera"
    assert alex["record_count"] >= 3


def test_get_patient_detail(client: TestClient) -> None:
    """Verify GET /api/v1/patients/{patient_id} returns single patient metadata."""
    ingest_sample_data(client)

    response = client.get("/api/v1/patients/pat_syn_pat_001")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["display_name"] == "Alex Rivera"
    assert data["mrn_normalized"] == "SYN-PAT-001"
    assert data["record_count"] >= 3


def test_get_patient_not_found(client: TestClient) -> None:
    """Verify GET /api/v1/patients/{patient_id} returns 404 for nonexistent patient."""
    response = client.get("/api/v1/patients/pat_nonexistent_999")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_patient_records(client: TestClient) -> None:
    """Verify GET /api/v1/patients/{patient_id}/records returns list of records."""
    ingest_sample_data(client)

    response = client.get("/api/v1/patients/pat_syn_pat_001/records")
    assert response.status_code == status.HTTP_200_OK
    records = response.json()
    assert len(records) >= 3
    assert any(r["record_type"] == "imaging" for r in records)
    assert any(r["record_type"] == "lab" for r in records)


def test_get_patient_bundle(client: TestClient) -> None:
    """Verify GET /api/v1/patients/{patient_id}/bundle returns valid FHIR Bundle."""
    ingest_sample_data(client)

    response = client.get("/api/v1/patients/pat_syn_pat_001/bundle")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["bundle_id"] == "bundle-pat-syn-pat-001"
    assert data["validation_status"] == "valid"
    assert data["resource_count"] >= 4

    bundle = data["bundle"]
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    assert bundle["entry"][0]["resource"]["resourceType"] == "Patient"


def test_get_fhir_patient_resource(client: TestClient) -> None:
    """Verify GET /api/v1/fhir/Patient/{resource_id} returns raw FHIR Patient JSON."""
    ingest_sample_data(client)

    response = client.get("/api/v1/fhir/Patient/pat-syn-pat-001")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["resourceType"] == "Patient"
    assert data["id"] == "pat-syn-pat-001"
    assert data["name"][0]["family"] == "Rivera"


def test_get_fhir_document_reference_resource(client: TestClient) -> None:
    """Verify GET /api/v1/fhir/DocumentReference/{resource_id} returns DocumentReference."""
    ingest_sample_data(client)

    # Alex Rivera's note generates a DocumentReference
    bundle_resp = client.get("/api/v1/patients/pat_syn_pat_001/bundle")
    bundle = bundle_resp.json()["bundle"]
    doc_entry = next((e for e in bundle["entry"] if e["resource"]["resourceType"] == "DocumentReference"), None)
    assert doc_entry is not None
    doc_id = doc_entry["resource"]["id"]

    response = client.get(f"/api/v1/fhir/DocumentReference/{doc_id}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["resourceType"] == "DocumentReference"
    assert data["id"] == doc_id
    assert data["status"] == "current"


def test_get_fhir_diagnostic_report_resource(client: TestClient) -> None:
    """Verify GET /api/v1/fhir/DiagnosticReport/{resource_id} returns DiagnosticReport."""
    ingest_sample_data(client)

    # Alex Rivera's CBC lab generates a DiagnosticReport
    bundle_resp = client.get("/api/v1/patients/pat_syn_pat_001/bundle")
    bundle = bundle_resp.json()["bundle"]
    diag_entry = next((e for e in bundle["entry"] if e["resource"]["resourceType"] == "DiagnosticReport"), None)
    assert diag_entry is not None
    diag_id = diag_entry["resource"]["id"]

    response = client.get(f"/api/v1/fhir/DiagnosticReport/{diag_id}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["resourceType"] == "DiagnosticReport"
    assert data["id"] == diag_id
    assert data["status"] == "final"


def test_get_fhir_resource_not_found(client: TestClient) -> None:
    """Verify 404 for nonexistent FHIR resource."""
    response = client.get("/api/v1/fhir/Patient/pat-nonexistent-999")
    assert response.status_code == status.HTTP_404_NOT_FOUND
