"""Comprehensive unit and integration tests for semantic search, vector storage, and filtering."""
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.models.canonical import AdministrativeGender, IdentityStatus, MediaRecord, RecordType
from app.models.search import SearchFilters, SearchRequest, SearchResponse
from app.services.embedding.deterministic_service import DeterministicClinicalEmbeddingService
from app.services.search_service import SearchService, search_service
from app.services.vector_store.embedded_store import EmbeddedVectorStore


def sample_media_records() -> list[MediaRecord]:
    """Synthetic clinical records covering diverse clinical categories and dates."""
    return [
        MediaRecord(
            record_id="rec_sugar_01",
            patient_key="pat_001",
            patient_name="John Doe",
            mrn_normalized="MRN-001",
            gender=AdministrativeGender.MALE,
            record_date="2024-03-15",
            record_type=RecordType.LAB,
            title="Comprehensive Metabolic Panel",
            text="Fasting blood sugar glucose: 184 mg/dL [High, Ref: 70-99]. Elevated HbA1c: 8.8%. Uncontrolled hyperglycemia.",
            source_file="lab.json",
            source_index=0,
            fingerprint="fp_sugar_01",
        ),
        MediaRecord(
            record_id="rec_brain_01",
            patient_key="pat_001",
            patient_name="John Doe",
            mrn_normalized="MRN-001",
            gender=AdministrativeGender.MALE,
            record_date="2024-05-10",
            record_type=RecordType.IMAGING,
            title="MRI Brain without Contrast",
            text="Magnetic resonance imaging (MRI brain) reveals chronic microvascular ischemic changes in periventricular white matter. No acute stroke or intracranial hemorrhage.",
            source_file="imaging.json",
            source_index=1,
            fingerprint="fp_brain_01",
        ),
        MediaRecord(
            record_id="rec_lung_01",
            patient_key="pat_002",
            patient_name="Jane Smith",
            mrn_normalized="MRN-002",
            gender=AdministrativeGender.FEMALE,
            record_date="2024-09-22",
            record_type=RecordType.IMAGING,
            title="PA and Lateral Chest Radiograph",
            text="Focal patchy consolidation in right middle lobe consistent with community-acquired pneumonia. Significant pulmonary disease infiltrate.",
            source_file="notes.txt",
            source_index=2,
            fingerprint="fp_lung_01",
        ),
        MediaRecord(
            record_id="rec_kidney_01",
            patient_key="pat_002",
            patient_name="Jane Smith",
            mrn_normalized="MRN-002",
            gender=AdministrativeGender.FEMALE,
            record_date="2025-01-18",
            record_type=RecordType.LAB,
            title="Urinalysis and Renal Function Panel",
            text="Severe acute pyelonephritis and urinary kidney infection. Elevated serum creatinine: 2.1 mg/dL, BUN: 34 mg/dL. Costovertebral angle tenderness.",
            source_file="lab.csv",
            source_index=3,
            fingerprint="fp_kidney_01",
        ),
        MediaRecord(
            record_id="rec_cardiac_01",
            patient_key="pat_003",
            patient_name="Robert Brown",
            mrn_normalized="MRN-003",
            gender=AdministrativeGender.MALE,
            record_date="2025-03-05",
            record_type=RecordType.CLINICAL_NOTE,
            title="Cardiology Consultation Note",
            text="Patient evaluated for exertional angina and cardiovascular disease. Serial cardiac troponins negative. ECG demonstrates normal sinus rhythm with non-specific ST changes.",
            source_file="cardio.txt",
            source_index=4,
            fingerprint="fp_cardiac_01",
        ),
    ]


# -------------------------------------------------------------------------
# 1. Embedding Service Tests
# -------------------------------------------------------------------------

def test_embedding_generation_valid_text() -> None:
    embedder = DeterministicClinicalEmbeddingService()
    vec = embedder.embed_text("Elevated blood sugar glucose level")
    assert len(vec) == 384
    # Check unit vector normalization
    magnitude = sum(x * x for x in vec) ** 0.5
    assert abs(magnitude - 1.0) < 1e-4


def test_embedding_empty_text_returns_zero_vector() -> None:
    embedder = DeterministicClinicalEmbeddingService()
    vec_empty = embedder.embed_text("")
    vec_spaces = embedder.embed_text("   \n\t  ")
    assert len(vec_empty) == 384
    assert all(x == 0.0 for x in vec_empty)
    assert all(x == 0.0 for x in vec_spaces)


def test_batch_embedding() -> None:
    embedder = DeterministicClinicalEmbeddingService()
    texts = [
        "Chest radiograph consolidation",
        "Elevated serum creatinine kidney failure",
        "",
    ]
    vectors = embedder.embed_texts(texts)
    assert len(vectors) == 3
    assert len(vectors[0]) == 384
    assert len(vectors[1]) == 384
    assert all(x == 0.0 for x in vectors[2])


# -------------------------------------------------------------------------
# 2. Vector Store Persistence & Upsert Tests
# -------------------------------------------------------------------------

def test_vector_persistence_across_reconnect(tmp_path: Path) -> None:
    store1 = EmbeddedVectorStore(persist_directory=str(tmp_path), collection_name="test_col")
    embedder = DeterministicClinicalEmbeddingService()

    vec = embedder.embed_text("Brain MRI")
    store1.upsert(
        ids=["doc_rec_001"],
        embeddings=[vec],
        documents=["MRI Brain scan findings."],
        metadatas=[{"resource_type": "DocumentReference", "record_id": "rec_001", "patient_id": "pat_001"}],
    )
    assert store1.count() == 1

    # Reconnect with new instance targeting same storage
    store2 = EmbeddedVectorStore(persist_directory=str(tmp_path), collection_name="test_col")
    assert store2.count() == 1
    stored = store2.get(["doc_rec_001"])
    assert len(stored) == 1
    assert stored[0]["id"] == "doc_rec_001"
    assert stored[0]["document"] == "MRI Brain scan findings."


def test_upsert_existing_record_avoids_duplicate_vectors(tmp_path: Path) -> None:
    store = EmbeddedVectorStore(persist_directory=str(tmp_path), collection_name="test_upsert")
    embedder = DeterministicClinicalEmbeddingService()

    vec1 = embedder.embed_text("Initial pulmonary radiograph")
    store.upsert(
        ids=["doc_1"],
        embeddings=[vec1],
        documents=["Initial radiograph text"],
        metadatas=[{"record_id": "1", "resource_type": "DocumentReference"}],
    )
    assert store.count() == 1

    # Update the same ID with modified content
    vec2 = embedder.embed_text("Updated pulmonary radiograph with pneumonia")
    store.upsert(
        ids=["doc_1"],
        embeddings=[vec2],
        documents=["Updated radiograph text"],
        metadatas=[{"record_id": "1", "resource_type": "DocumentReference", "status": "updated"}],
    )
    assert store.count() == 1
    item = store.get(["doc_1"])[0]
    assert item["document"] == "Updated radiograph text"
    assert item["metadata"]["status"] == "updated"


# -------------------------------------------------------------------------
# 3. Semantic Concept Retrieval Tests
# -------------------------------------------------------------------------

def test_semantic_retrieval_related_clinical_concepts() -> None:
    service = SearchService(
        embedding_service=DeterministicClinicalEmbeddingService(),
        vector_store=EmbeddedVectorStore(persist_directory="./chroma_db", collection_name="test_concepts"),
    )
    service.vector_store.clear()
    service.index_records(sample_media_records())

    # 1. "Patient with signs of elevated blood sugar" -> glucose / HbA1c
    res_sugar = service.search(SearchRequest(query="Patient with signs of elevated blood sugar", top_k=5))
    assert len(res_sugar.results) > 0
    top_sugar = res_sugar.results[0]
    assert top_sugar.record_id == "rec_sugar_01"
    assert "glucose" in top_sugar.excerpt.lower() or "hyperglycemia" in top_sugar.excerpt.lower()
    assert top_sugar.similarity_score > 0.6

    # 2. "Brain imaging" -> MRI Brain
    res_brain = service.search(SearchRequest(query="Brain imaging and neurological evaluation", top_k=5))
    assert len(res_brain.results) > 0
    top_brain = res_brain.results[0]
    assert top_brain.record_id == "rec_brain_01"
    assert "mri brain" in top_brain.title.lower()

    # 3. "Evidence of lung disease" -> PA and Lateral Chest Radiograph / pneumonia
    res_lung = service.search(SearchRequest(query="Evidence of acute lung disease and pulmonary consolidation", top_k=5))
    assert len(res_lung.results) > 0
    top_lung = res_lung.results[0]
    assert top_lung.record_id == "rec_lung_01"

    # 4. "Kidney infection" -> Pyelonephritis
    res_kidney = service.search(SearchRequest(query="Patient suffering from kidney infection and renal distress", top_k=5))
    assert len(res_kidney.results) > 0
    top_kidney = res_kidney.results[0]
    assert top_kidney.record_id == "rec_kidney_01"
    assert "pyelonephritis" in top_kidney.excerpt.lower()


# -------------------------------------------------------------------------
# 4. Ranking, Filtering, and Parameter Tests
# -------------------------------------------------------------------------

def test_top_k_default_and_limit() -> None:
    service = SearchService(
        embedding_service=DeterministicClinicalEmbeddingService(),
        vector_store=EmbeddedVectorStore(persist_directory="./chroma_db", collection_name="test_topk"),
    )
    service.vector_store.clear()
    # Add 8 synthetic records
    records = sample_media_records()
    for i in range(3):
        records.append(
            MediaRecord(
                record_id=f"rec_extra_{i}",
                patient_key=f"pat_extra_{i}",
                patient_name="Extra Patient",
                mrn_normalized=f"MRN-EXTRA-{i}",
                gender=AdministrativeGender.OTHER,
                record_date="2025-02-01",
                record_type=RecordType.CLINICAL_NOTE,
                title=f"Clinical Follow-up Note {i}",
                text=f"Routine clinical assessment note for extra patient {i}.",
                source_file="extra.txt",
                source_index=i,
                fingerprint=f"fp_extra_{i}",
            )
        )
    service.index_records(records)

    # Default top_k is 5
    req_default = SearchRequest(query="clinical evaluation")
    assert req_default.top_k == 5
    res_default = service.search(req_default)
    assert len(res_default.results) == 5

    # Explicit top_k=3
    req_3 = SearchRequest(query="clinical evaluation", top_k=3)
    res_3 = service.search(req_3)
    assert len(res_3.results) == 3


def test_resource_type_filter() -> None:
    service = SearchService(
        embedding_service=DeterministicClinicalEmbeddingService(),
        vector_store=EmbeddedVectorStore(persist_directory="./chroma_db", collection_name="test_res_filter"),
    )
    service.vector_store.clear()
    service.index_records(sample_media_records())

    # Filter for DiagnosticReport (lab records)
    req_diag = SearchRequest(
        query="laboratory blood analysis",
        filters=SearchFilters(resource_type="DiagnosticReport"),
    )
    res_diag = service.search(req_diag)
    assert len(res_diag.results) > 0
    assert all(r.resource_type == "DiagnosticReport" for r in res_diag.results)

    # Filter for DocumentReference (imaging / notes)
    req_doc = SearchRequest(
        query="imaging radiograph findings",
        filters=SearchFilters(resource_type="DocumentReference"),
    )
    res_doc = service.search(req_doc)
    assert len(res_doc.results) > 0
    assert all(r.resource_type == "DocumentReference" for r in res_doc.results)


def test_date_range_filter() -> None:
    service = SearchService(
        embedding_service=DeterministicClinicalEmbeddingService(),
        vector_store=EmbeddedVectorStore(persist_directory="./chroma_db", collection_name="test_date_filter"),
    )
    service.vector_store.clear()
    service.index_records(sample_media_records())

    # Records in sample: 2024-03-15, 2024-05-10, 2024-09-22, 2025-01-18, 2025-03-05
    req_2024 = SearchRequest(
        query="clinical assessment",
        filters=SearchFilters(date_from="2024-01-01", date_to="2024-12-31"),
    )
    res_2024 = service.search(req_2024)
    assert len(res_2024.results) == 3
    assert all(r.record_date.startswith("2024") for r in res_2024.results)

    req_2025 = SearchRequest(
        query="clinical assessment",
        filters=SearchFilters(date_from="2025-01-01", date_to="2025-12-31"),
    )
    res_2025 = service.search(req_2025)
    assert len(res_2025.results) == 2
    assert all(r.record_date.startswith("2025") for r in res_2025.results)


def test_patient_filter() -> None:
    service = SearchService(
        embedding_service=DeterministicClinicalEmbeddingService(),
        vector_store=EmbeddedVectorStore(persist_directory="./chroma_db", collection_name="test_pat_filter"),
    )
    service.vector_store.clear()
    service.index_records(sample_media_records())

    req_pat1 = SearchRequest(
        query="clinical diagnosis",
        filters=SearchFilters(patient_id="pat_001"),
    )
    res_pat1 = service.search(req_pat1)
    assert len(res_pat1.results) == 2
    assert all(r.patient_id == "pat_001" for r in res_pat1.results)


def test_no_results_response() -> None:
    service = SearchService(
        embedding_service=DeterministicClinicalEmbeddingService(),
        vector_store=EmbeddedVectorStore(persist_directory="./chroma_db", collection_name="test_no_results"),
    )
    service.vector_store.clear()
    service.index_records(sample_media_records())

    # Query with a patient ID that has zero indexed records
    req = SearchRequest(
        query="pneumonia",
        filters=SearchFilters(patient_id="non_existent_pat_999"),
    )
    res = service.search(req)
    assert res.total_results == 0
    assert len(res.results) == 0
    assert res.query == "pneumonia"
    assert res.search_latency_ms >= 0.0


# -------------------------------------------------------------------------
# 5. Validation and Safety Tests
# -------------------------------------------------------------------------

def test_empty_query_raises_validation_error() -> None:
    with pytest.raises(ValueError):
        SearchRequest(query="")

    with pytest.raises(ValueError):
        SearchRequest(query="   \n\t ")


def test_top_k_bounds_validation() -> None:
    with pytest.raises(ValueError):
        SearchRequest(query="valid", top_k=0)

    with pytest.raises(ValueError):
        SearchRequest(query="valid", top_k=25)


def test_invalid_date_range_raises_validation_error() -> None:
    with pytest.raises(ValueError, match="cannot be after date_to"):
        SearchFilters(date_from="2025-12-31", date_to="2024-01-01")

    with pytest.raises(ValueError, match="valid ISO format"):
        SearchFilters(date_from="01-15-2024")


def test_quarantined_identity_conflict_records_excluded_from_indexing() -> None:
    service = SearchService(
        embedding_service=DeterministicClinicalEmbeddingService(),
        vector_store=EmbeddedVectorStore(persist_directory="./chroma_db", collection_name="test_quarantine"),
    )
    service.vector_store.clear()

    quarantined_record = MediaRecord(
        record_id="rec_conflict_01",
        patient_key="pat_conflict_01",
        patient_name="Conflicting Name",
        mrn_normalized="SYN-PAT-001",
        gender=AdministrativeGender.MALE,
        record_date="2025-01-10",
        record_type=RecordType.CLINICAL_NOTE,
        title="Quarantined Clinical Note",
        text="This record has an unresolved MRN-to-name conflict and must never be indexed.",
        source_file="conflict.txt",
        source_index=0,
        fingerprint="fp_conflict_01",
        identity_status=IdentityStatus.CONFLICT_QUARANTINED,
    )

    indexed_count = service.index_records([quarantined_record])
    assert indexed_count == 0
    assert service.vector_store.count() == 0


def test_indexing_failure_does_not_corrupt_database(client: TestClient) -> None:
    """Verify that vector store failure during ingestion does not break persistence."""
    with patch.object(EmbeddedVectorStore, "upsert", side_effect=RuntimeError("Simulated vector DB failure")):
        payload = [
            {
                "patient_name": "Resilient Ingest",
                "mrn": "SYN-RESILIENT-01",
                "dob": "1990-01-01",
                "gender": "male",
                "record_date": "2025-01-01",
                "record_type": "note",
                "title": "Resilience Test Note",
                "text": "Clinical note indexed despite vector store failure.",
            }
        ]
        import json
        resp = client.post(
            "/api/v1/ingest",
            files={"file": ("resilience.json", json.dumps(payload).encode("utf-8"), "application/json")},
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["accepted"] == 1


# -------------------------------------------------------------------------
# 6. End-to-End Search API Endpoint Tests
# -------------------------------------------------------------------------

def test_api_search_endpoint_happy_path(client: TestClient) -> None:
    # First ingest sample records so vector index has data
    sample_json = [
        {
            "patient_name": "API Search Patient",
            "mrn": "SYN-SEARCH-01",
            "dob": "1985-05-15",
            "gender": "female",
            "record_date": "2025-02-14",
            "record_type": "imaging",
            "title": "Head CT Scan",
            "text": "Computed tomography (CT head) demonstrates no intracranial bleed or mass effect.",
        }
    ]
    import json
    ingest_resp = client.post(
        "/api/v1/ingest",
        files={"file": ("search_sample.json", json.dumps(sample_json).encode("utf-8"), "application/json")},
    )
    assert ingest_resp.status_code == status.HTTP_200_OK

    search_payload = {
        "query": "intracranial bleed head ct",
        "top_k": 5,
        "filters": {
            "resource_type": "DocumentReference",
        },
    }
    resp = client.post("/api/v1/search", json=search_payload)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["query"] == "intracranial bleed head ct"
    assert data["total_results"] >= 1
    assert "ADVISORY NOTICE" in data["disclaimer"]
    first = data["results"][0]
    assert "rank" in first
    assert "similarity_score" in first
    assert "distance" in first
    assert "head ct" in first["title"].lower()


def test_api_search_endpoint_validation_errors(client: TestClient) -> None:
    # 1. Empty query
    resp1 = client.post("/api/v1/search", json={"query": ""})
    assert resp1.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 2. Invalid date range
    resp2 = client.post(
        "/api/v1/search",
        json={"query": "test", "filters": {"date_from": "2025-01-01", "date_to": "2024-01-01"}},
    )
    assert resp2.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 3. Invalid top_k
    resp3 = client.post("/api/v1/search", json={"query": "test", "top_k": 50})
    assert resp3.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
