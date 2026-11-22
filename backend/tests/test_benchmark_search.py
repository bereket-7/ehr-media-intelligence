"""Performance benchmark measuring query latency across 50+ synthetic clinical records."""
import time
import pytest
from app.models.canonical import AdministrativeGender, MediaRecord, RecordType
from app.models.search import SearchRequest
from app.services.embedding.deterministic_service import DeterministicClinicalEmbeddingService
from app.services.search_service import SearchService
from app.services.vector_store.embedded_store import EmbeddedVectorStore


def generate_50_synthetic_records() -> list[MediaRecord]:
    """Generate 50 distinct synthetic clinical records covering diverse clinical categories."""
    records = []
    clinical_scenarios = [
        ("Type 2 Diabetes Mellitus with elevated fasting glucose and HbA1c 9.2%", RecordType.LAB, "Metabolic Panel"),
        ("PA and Lateral Chest Radiograph demonstrating right lower lobe infiltrate", RecordType.IMAGING, "Chest X-Ray"),
        ("MRI Brain revealing chronic small vessel ischemic disease", RecordType.IMAGING, "MRI Brain"),
        ("Acute pyelonephritis with flank pain and high leukocyte esterase", RecordType.LAB, "Renal Function Panel"),
        ("Cardiology evaluation for exertional chest tightness and angina", RecordType.CLINICAL_NOTE, "Cardiology Note"),
        ("Complete Blood Count showing marked leukocytosis with WBC 16.5", RecordType.LAB, "CBC with Differential"),
        ("CT Abdomen and Pelvis showing uncomplicated acute appendicitis", RecordType.IMAGING, "CT Abdomen"),
        ("Dermatology note evaluating erythematous macular rash", RecordType.CLINICAL_NOTE, "Dermatology Note"),
        ("Lipid panel showing severe hypertriglyceridemia and LDL 175 mg/dL", RecordType.LAB, "Lipid Profile"),
        ("Orthopedic note assessing left knee osteoarthritis and joint effusion", RecordType.CLINICAL_NOTE, "Orthopedic Consult"),
    ]

    for i in range(50):
        scenario_idx = i % len(clinical_scenarios)
        desc, rec_type, title_prefix = clinical_scenarios[scenario_idx]
        pat_id = f"pat_bench_{i // 5:03d}"
        rec_id = f"rec_bench_{i:03d}"
        record_date = f"2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}"

        records.append(
            MediaRecord(
                record_id=rec_id,
                patient_key=pat_id,
                patient_name=f"Benchmark Patient {i // 5}",
                mrn_normalized=f"BENCH-MRN-{i // 5:03d}",
                gender=AdministrativeGender.MALE if i % 2 == 0 else AdministrativeGender.FEMALE,
                record_date=record_date,
                record_type=rec_type,
                title=f"{title_prefix} Batch #{i}",
                text=f"Synthetic record {i}: Patient assessment findings: {desc}. Clinical follow-up required.",
                source_file="benchmark_batch.json",
                source_index=i,
                fingerprint=f"fp_bench_{i:04d}",
            )
        )
    return records


def test_benchmark_search_latency_50_records(tmp_path) -> None:
    """Benchmark: Index 50 records and verify query execution is completed well under 2.0 seconds."""
    store = EmbeddedVectorStore(persist_directory=str(tmp_path), collection_name="bench_collection")
    service = SearchService(
        embedding_service=DeterministicClinicalEmbeddingService(),
        vector_store=store,
    )

    records = generate_50_synthetic_records()
    assert len(records) == 50

    # Index 50 records
    t0_index = time.perf_counter()
    indexed_count = service.index_records(records)
    index_duration = time.perf_counter() - t0_index
    assert indexed_count == 50
    assert service.vector_store.count() == 50

    # Execute 5 distinct clinical search queries (measuring warm query latency)
    queries = [
        "Patient with signs of elevated blood sugar",
        "Brain imaging and neurological evaluation",
        "Evidence of lung disease and pneumonia infiltrate",
        "Kidney infection and renal pain",
        "Cardiovascular disease and chest pain",
    ]

    latencies = []
    for q in queries:
        t0_query = time.perf_counter()
        response = service.search(SearchRequest(query=q, top_k=5))
        duration = time.perf_counter() - t0_query
        latencies.append(duration)

        # Basic assertions
        assert response.total_results == 5
        assert len(response.results) == 5
        # The assessment criteria requires < 2.0 seconds per query across 50 records
        assert duration < 2.0, f"Query '{q}' took {duration:.4f}s, exceeding 2.0s target"

    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)

    print(f"\n--- BENCHMARK RESULTS (50 Synthetic Records) ---")
    print(f"Indexing duration for 50 records: {index_duration:.4f}s")
    print(f"Average query latency: {avg_latency * 1000:.2f}ms")
    print(f"Maximum query latency: {max_latency * 1000:.2f}ms")
    print(f"Assessment target (< 2000ms): {'PASS' if max_latency < 2.0 else 'FAIL'}")

    assert max_latency < 2.0
