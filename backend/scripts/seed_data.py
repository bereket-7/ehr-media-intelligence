"""Synthetic dataset seeding script for the EHR Media Intelligence Platform.

Usage:
    python backend/scripts/seed_data.py [--reset]

Loads synthetic demo data (JSON, CSV, TXT) into SQLite persistence,
generates FHIR R4 Bundles, and indexes clinical records for semantic search.
"""
import argparse
import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.logging import configure_logging, get_logger
from app.ingestion.service import ingestion_service
from app.repositories.database import get_connection, initialize_database
from app.repositories.sqlite_repository import repository
from app.services.vector_store import get_vector_store

logger = get_logger("seed_data")


def seed_database(reset: bool = False) -> None:
    """Seed the database with all synthetic fixtures."""
    configure_logging()
    initialize_database()

    if reset:
        logger.info("Reset flag provided. Clearing existing database and vector storage...")
        ingestion_service.clear()
        vector_store = get_vector_store()
        vector_store.clear()
        logger.info("Database and vector storage cleared.")

    data_dir = backend_dir / "data" / "synthetic"
    if not data_dir.exists():
        logger.error("Synthetic data directory not found at: %s", data_dir)
        sys.exit(1)

    seed_files = [
        "patients_records.json",
        "clinical_records.csv",
        "notes.txt",
    ]

    print("\n" + "=" * 65)
    print("  EHR Media Intelligence Platform — Synthetic Data Seeder")
    print("=" * 65)

    total_accepted = 0
    total_quarantined = 0
    total_duplicates = 0
    total_rejected = 0

    for filename in seed_files:
        file_path = data_dir / filename
        if not file_path.exists():
            print(f"[-] Skipping missing file: {filename}")
            continue

        print(f"[*] Ingesting fixture: {filename} ({file_path.stat().st_size} bytes)...")
        content = file_path.read_text(encoding="utf-8")
        result = ingestion_service.ingest_file(content, filename)

        total_accepted += result.accepted
        total_quarantined += result.quarantined
        total_duplicates += result.duplicates
        total_rejected += result.rejected

        print(
            f"    -> Accepted: {result.accepted} | Duplicates: {result.duplicates} | "
            f"Quarantined: {result.quarantined} | Rejected: {result.rejected}"
        )

    # Fetch final summary counts from repositories
    all_patients = repository.list_patients()
    with get_connection() as conn:
        record_count = conn.execute("SELECT COUNT(*) FROM media_records;").fetchone()[0]
    vector_store = get_vector_store()
    vector_count = vector_store.count()

    print("\n" + "-" * 65)
    print("  SEEDING COMPLETE — Database Summary")
    print("-" * 65)
    print(f"  • Unique Synthetic Patients : {len(all_patients)}")
    print(f"  • Canonical Media Records   : {record_count}")
    print(f"  • Indexed Semantic Vectors  : {vector_count}")
    print(f"  • Total Accepted Records    : {total_accepted}")
    print(f"  • Total Duplicates Handled  : {total_duplicates}")
    print(f"  • Quarantined Identities    : {total_quarantined}")
    print("=" * 65)
    print("Reviewer can now start the API and search synthetic records immediately:\n")
    print("    cd backend")
    print("    uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload")
    print("    Browse dashboard at: http://127.0.0.1:8000\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed EHR Media Intelligence Platform with synthetic data.")
    parser.add_argument("--reset", action="store_true", help="Clear existing data before seeding.")
    args = parser.parse_args()

    seed_database(reset=args.reset)
