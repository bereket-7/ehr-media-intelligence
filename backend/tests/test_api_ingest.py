"""Integration tests for the /ingest endpoint."""
from pathlib import Path
from fastapi import status
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data" / "synthetic"


def test_api_ingest_json_synthetic_fixture(client: TestClient) -> None:
    """Verify ingestion of the synthetic JSON dataset."""
    json_path = DATA_DIR / "patients_records.json"
    assert json_path.exists(), f"Synthetic JSON fixture not found at {json_path}"

    with open(json_path, "rb") as f:
        response = client.post(
            "/ingest",
            files={"file": ("patients_records.json", f, "application/json")},
        )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["accepted"] >= 10
    assert data["duplicates"] >= 1  # Near-duplicate chest X-ray suppressed
    assert len(data["record_ids"]) == data["accepted"]
    assert len(data["audit_log"]) > 0


def test_api_ingest_csv_synthetic_fixture(client: TestClient) -> None:
    """Verify ingestion of the synthetic CSV dataset."""
    csv_path = DATA_DIR / "clinical_records.csv"
    assert csv_path.exists(), f"Synthetic CSV fixture not found at {csv_path}"

    with open(csv_path, "rb") as f:
        response = client.post(
            "/ingest",
            files={"file": ("clinical_records.csv", f, "text/csv")},
        )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["accepted"] >= 6
    assert data["rejected"] == 1  # Empty text row rejected
    assert data["duplicates"] >= 1  # Duplicate CMP lab suppressed
    assert any(err["code"] == "empty_content" for err in data["errors"])


def test_api_ingest_txt_synthetic_fixture(client: TestClient) -> None:
    """Verify ingestion of the plain-text notes dataset."""
    txt_path = DATA_DIR / "notes.txt"
    assert txt_path.exists(), f"Synthetic TXT fixture not found at {txt_path}"

    with open(txt_path, "rb") as f:
        response = client.post(
            "/ingest",
            files={"file": ("notes.txt", f, "text/plain")},
        )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["accepted"] >= 4
    # The conflicting Logan Thorne record triggers identity quarantine
    assert data["quarantined"] >= 1
    assert any("Identity conflict" in w for w in data["warnings"])


def test_api_ingest_invalid_json(client: TestClient) -> None:
    """Verify that syntactically invalid JSON returns structured rejection and error log."""
    bad_json = b"{\"patient_name\": \"Corrupted\""  # missing closing brace
    response = client.post(
        "/ingest",
        files={"file": ("broken.json", bad_json, "application/json")},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["accepted"] == 0
    assert data["rejected"] == 1
    assert any(err["code"] == "invalid_json" for err in data["errors"])


def test_api_ingest_oversized_file(client: TestClient) -> None:
    """Verify that files exceeding the maximum size limit are rejected with 413."""
    oversized = b"0" * (11 * 1024 * 1024)
    response = client.post(
        "/ingest",
        files={"file": ("huge.txt", oversized, "text/plain")},
    )
    assert response.status_code == 413
