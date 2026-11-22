"""SQLite database connection and schema management."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def get_db_path() -> Path:
    """Return resolved SQLite database file path."""
    db_path = Path(settings.SQLITE_DB_PATH)
    if not db_path.is_absolute():
        # Resolve relative to repo root or backend directory
        backend_dir = Path(__file__).resolve().parent.parent.parent
        db_path = backend_dir / db_path.name
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """Create a SQLite connection with foreign keys and Row factory enabled."""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_db_transaction() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite transactions with automatic commit and rollback."""
    with get_connection() as conn:
        try:
            conn.execute("BEGIN;")
            yield conn
            conn.commit()
        except Exception as exc:
            conn.rollback()
            logger.error("Transaction rolled back due to error: %s", exc)
            raise


def initialize_database() -> None:
    """Initialize SQLite schema, tables, and indexes idempotently."""
    db_path = get_db_path()
    logger.info("Initializing SQLite database at: %s", db_path)

    with get_connection() as conn:
        cursor = conn.cursor()
        fks = cursor.execute("PRAGMA foreign_key_list(summary_cache);").fetchall()
        if fks:
            cursor.execute("DROP TABLE IF EXISTS summary_cache;")
        cursor.close()

    schema_sql = """
    -- Canonical Patients Table
    CREATE TABLE IF NOT EXISTS patients (
        patient_key TEXT PRIMARY KEY,
        mrn_normalized TEXT UNIQUE,
        mrn_original TEXT,
        display_name TEXT NOT NULL,
        dob TEXT,
        gender TEXT NOT NULL,
        identity_status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_patients_mrn ON patients(mrn_normalized);

    -- Canonical Media Records Table
    CREATE TABLE IF NOT EXISTS media_records (
        record_id TEXT PRIMARY KEY,
        patient_key TEXT NOT NULL,
        record_type TEXT NOT NULL,
        record_date TEXT,
        title TEXT NOT NULL,
        text TEXT NOT NULL,
        source_file TEXT NOT NULL,
        source_index INTEGER NOT NULL,
        encounter_id TEXT,
        fingerprint TEXT UNIQUE NOT NULL,
        identity_status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (patient_key) REFERENCES patients(patient_key) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_records_patient ON media_records(patient_key);
    CREATE INDEX IF NOT EXISTS idx_records_type ON media_records(record_type);
    CREATE INDEX IF NOT EXISTS idx_records_date ON media_records(record_date);
    CREATE INDEX IF NOT EXISTS idx_records_fingerprint ON media_records(fingerprint);

    -- FHIR Individual Resources Table
    CREATE TABLE IF NOT EXISTS fhir_resources (
        resource_id TEXT PRIMARY KEY,
        resource_type TEXT NOT NULL,
        patient_key TEXT NOT NULL,
        record_id TEXT,
        resource_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (patient_key) REFERENCES patients(patient_key) ON DELETE CASCADE,
        FOREIGN KEY (record_id) REFERENCES media_records(record_id) ON DELETE SET NULL
    );
    CREATE INDEX IF NOT EXISTS idx_fhir_type ON fhir_resources(resource_type);
    CREATE INDEX IF NOT EXISTS idx_fhir_patient ON fhir_resources(patient_key);
    CREATE INDEX IF NOT EXISTS idx_fhir_record ON fhir_resources(record_id);

    -- FHIR Bundles Table (Per-Patient)
    CREATE TABLE IF NOT EXISTS fhir_bundles (
        patient_key TEXT PRIMARY KEY,
        bundle_id TEXT UNIQUE NOT NULL,
        bundle_json TEXT NOT NULL,
        resource_count INTEGER NOT NULL,
        validation_status TEXT NOT NULL,
        validation_report_json TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (patient_key) REFERENCES patients(patient_key) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_bundles_patient ON fhir_bundles(patient_key);

    -- Summary Cache Table
    CREATE TABLE IF NOT EXISTS summary_cache (
        cache_key TEXT PRIMARY KEY,
        patient_key TEXT NOT NULL,
        records_hash TEXT NOT NULL,
        provider TEXT NOT NULL,
        model TEXT NOT NULL,
        prompt_version TEXT NOT NULL,
        summary_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_summary_patient ON summary_cache(patient_key);
    CREATE INDEX IF NOT EXISTS idx_summary_hash ON summary_cache(records_hash);

    -- Audit Logs Table
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        record_id TEXT,
        patient_key TEXT,
        action TEXT NOT NULL,
        field TEXT NOT NULL,
        before_value TEXT,
        after_value TEXT,
        reason TEXT NOT NULL,
        timestamp TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_audit_record ON audit_logs(record_id);
    CREATE INDEX IF NOT EXISTS idx_audit_patient ON audit_logs(patient_key);
    """

    with get_connection() as conn:
        conn.executescript(schema_sql)
        conn.commit()
    logger.info("SQLite schema initialized successfully.")
