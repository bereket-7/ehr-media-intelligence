"""SQLite repository abstraction for patients, records, FHIR resources, and bundles."""
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.models.canonical import MediaRecord
from app.repositories.database import get_connection, get_db_transaction


class SqliteRepository:
    """Repository handling persistence for canonical entities and FHIR resources."""

    # -------------------------------------------------------------------------
    # Patient Persistence
    # -------------------------------------------------------------------------

    @staticmethod
    def save_patient(
        patient_key: str,
        display_name: str,
        mrn_normalized: Optional[str] = None,
        mrn_original: Optional[str] = None,
        dob: Optional[str] = None,
        gender: str = "unknown",
        identity_status: str = "verified_synthetic",
    ) -> None:
        """Insert or update a canonical patient record."""
        now = datetime.now(timezone.utc).isoformat()
        with get_db_transaction() as conn:
            conn.execute(
                """
                INSERT INTO patients (
                    patient_key, mrn_normalized, mrn_original, display_name, dob, gender, identity_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(patient_key) DO UPDATE SET
                    display_name = excluded.display_name,
                    dob = COALESCE(excluded.dob, patients.dob),
                    gender = excluded.gender,
                    identity_status = excluded.identity_status,
                    updated_at = excluded.updated_at;
                """,
                (patient_key, mrn_normalized, mrn_original, display_name, dob, gender, identity_status, now, now),
            )

    @staticmethod
    def get_patient(patient_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve a canonical patient by key or MRN."""
        with get_connection() as conn:
            # Query by patient_key or mrn_normalized
            row = conn.execute(
                """
                SELECT p.*, COUNT(m.record_id) as record_count
                FROM patients p
                LEFT JOIN media_records m ON p.patient_key = m.patient_key
                WHERE p.patient_key = ? OR p.mrn_normalized = ?
                GROUP BY p.patient_key;
                """,
                (patient_key, patient_key),
            ).fetchone()
            if row:
                return dict(row)
            return None

    @staticmethod
    def list_patients() -> List[Dict[str, Any]]:
        """Retrieve list of all registered patients with their record counts."""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT p.patient_key, p.mrn_normalized, p.display_name, p.dob, p.gender,
                       p.identity_status, COUNT(m.record_id) as record_count, p.created_at, p.updated_at
                FROM patients p
                LEFT JOIN media_records m ON p.patient_key = m.patient_key
                GROUP BY p.patient_key
                ORDER BY p.display_name ASC;
                """
            ).fetchall()
            return [dict(r) for r in rows]

    # -------------------------------------------------------------------------
    # Media Records Persistence
    # -------------------------------------------------------------------------

    @staticmethod
    def save_media_record(record: MediaRecord) -> None:
        """Persist a canonical media record transactionally."""
        now = datetime.now(timezone.utc).isoformat()
        with get_db_transaction() as conn:
            conn.execute(
                """
                INSERT INTO media_records (
                    record_id, patient_key, record_type, record_date, title, text,
                    source_file, source_index, encounter_id, fingerprint, identity_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(record_id) DO UPDATE SET
                    title = excluded.title,
                    text = excluded.text,
                    record_date = excluded.record_date;
                """,
                (
                    record.record_id,
                    record.patient_key,
                    record.record_type.value,
                    record.record_date,
                    record.title,
                    record.text,
                    record.source_file,
                    record.source_index,
                    record.encounter_id,
                    record.fingerprint,
                    record.identity_status.value,
                    now,
                ),
            )

            # Persist associated audit entries
            for entry in record.audit_trail:
                conn.execute(
                    """
                    INSERT INTO audit_logs (
                        record_id, patient_key, action, field, before_value, after_value, reason, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        record.record_id,
                        record.patient_key,
                        entry.action,
                        entry.field,
                        entry.before_value,
                        entry.after_value,
                        entry.reason,
                        entry.timestamp,
                    ),
                )

    @staticmethod
    def get_media_record(record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single canonical media record by ID."""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM media_records WHERE record_id = ?;",
                (record_id,),
            ).fetchone()
            if row:
                return dict(row)
            return None

    @staticmethod
    def list_records_for_patient(patient_key: str) -> List[Dict[str, Any]]:
        """Retrieve all media records linked to a patient."""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM media_records
                WHERE patient_key = ? OR patient_key = (
                    SELECT patient_key FROM patients WHERE mrn_normalized = ?
                )
                ORDER BY record_date DESC, created_at DESC;
                """,
                (patient_key, patient_key),
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def has_fingerprint(fingerprint: str) -> bool:
        """Check if a record fingerprint is already saved in SQLite."""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM media_records WHERE fingerprint = ? LIMIT 1;",
                (fingerprint,),
            ).fetchone()
            return row is not None

    # -------------------------------------------------------------------------
    # FHIR Resource Persistence
    # -------------------------------------------------------------------------

    @staticmethod
    def save_fhir_resource(
        resource_id: str,
        resource_type: str,
        patient_key: str,
        resource_json: str,
        record_id: Optional[str] = None,
    ) -> None:
        """Persist an individual FHIR resource JSON."""
        now = datetime.now(timezone.utc).isoformat()
        with get_db_transaction() as conn:
            conn.execute(
                """
                INSERT INTO fhir_resources (
                    resource_id, resource_type, patient_key, record_id, resource_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(resource_id) DO UPDATE SET
                    resource_json = excluded.resource_json;
                """,
                (resource_id, resource_type, patient_key, record_id, resource_json, now),
            )

    @staticmethod
    def get_fhir_resource(resource_id: str, resource_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve an individual FHIR resource by ID and optional resource type."""
        with get_connection() as conn:
            if resource_type:
                row = conn.execute(
                    "SELECT * FROM fhir_resources WHERE resource_id = ? AND resource_type = ?;",
                    (resource_id, resource_type),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM fhir_resources WHERE resource_id = ?;",
                    (resource_id,),
                ).fetchone()
            if row:
                return dict(row)
            return None

    @staticmethod
    def list_fhir_resources_for_patient(patient_key: str) -> List[Dict[str, Any]]:
        """Retrieve all individual FHIR resources saved for a patient."""
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM fhir_resources WHERE patient_key = ? ORDER BY resource_type ASC, created_at ASC;",
                (patient_key,),
            ).fetchall()
            return [dict(r) for r in rows]

    # -------------------------------------------------------------------------
    # FHIR Bundle Persistence
    # -------------------------------------------------------------------------

    @staticmethod
    def save_fhir_bundle(
        patient_key: str,
        bundle_id: str,
        bundle_json: str,
        resource_count: int,
        validation_status: str,
        validation_report: Dict[str, Any],
    ) -> None:
        """Persist or update a validated per-patient FHIR Bundle."""
        now = datetime.now(timezone.utc).isoformat()
        with get_db_transaction() as conn:
            conn.execute(
                """
                INSERT INTO fhir_bundles (
                    patient_key, bundle_id, bundle_json, resource_count, validation_status, validation_report_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(patient_key) DO UPDATE SET
                    bundle_id = excluded.bundle_id,
                    bundle_json = excluded.bundle_json,
                    resource_count = excluded.resource_count,
                    validation_status = excluded.validation_status,
                    validation_report_json = excluded.validation_report_json,
                    updated_at = excluded.updated_at;
                """,
                (
                    patient_key,
                    bundle_id,
                    bundle_json,
                    resource_count,
                    validation_status,
                    json.dumps(validation_report),
                    now,
                ),
            )

    @staticmethod
    def get_fhir_bundle(patient_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve the persisted FHIR Bundle for a patient."""
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT b.* FROM fhir_bundles b
                WHERE b.patient_key = ? OR b.patient_key = (
                    SELECT patient_key FROM patients WHERE mrn_normalized = ?
                );
                """,
                (patient_key, patient_key),
            ).fetchone()
            if row:
                return dict(row)
            return None

    # -------------------------------------------------------------------------
    # Summary Cache Persistence
    # -------------------------------------------------------------------------

    @staticmethod
    def save_summary_cache(
        cache_key: str,
        patient_key: str,
        records_hash: str,
        provider: str,
        model: str,
        prompt_version: str,
        summary_json: str,
    ) -> None:
        """Persist or update a clinical summary in the cache."""
        now = datetime.now(timezone.utc).isoformat()
        with get_db_transaction() as conn:
            conn.execute(
                """
                INSERT INTO summary_cache (
                    cache_key, patient_key, records_hash, provider, model, prompt_version, summary_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    summary_json = excluded.summary_json,
                    created_at = excluded.created_at;
                """,
                (cache_key, patient_key, records_hash, provider, model, prompt_version, summary_json, now),
            )

    @staticmethod
    def get_summary_cache(cache_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve a cached summary by its unique deterministic cache key."""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM summary_cache WHERE cache_key = ?;",
                (cache_key,),
            ).fetchone()
            if row:
                return dict(row)
            return None

    # -------------------------------------------------------------------------
    # Audit Logs
    # -------------------------------------------------------------------------

    @staticmethod
    def list_audit_logs(patient_key: Optional[str] = None, record_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query audit log entries."""
        with get_connection() as conn:
            if record_id:
                rows = conn.execute(
                    "SELECT * FROM audit_logs WHERE record_id = ? ORDER BY id ASC;",
                    (record_id,),
                ).fetchall()
            elif patient_key:
                rows = conn.execute(
                    "SELECT * FROM audit_logs WHERE patient_key = ? ORDER BY id ASC;",
                    (patient_key,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 100;").fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def clear_all() -> None:
        """Clear all database tables (used for test teardown)."""
        with get_db_transaction() as conn:
            conn.execute("DELETE FROM summary_cache;")
            conn.execute("DELETE FROM audit_logs;")
            conn.execute("DELETE FROM fhir_resources;")
            conn.execute("DELETE FROM fhir_bundles;")
            conn.execute("DELETE FROM media_records;")
            conn.execute("DELETE FROM patients;")


repository = SqliteRepository()
