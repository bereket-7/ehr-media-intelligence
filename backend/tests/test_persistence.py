"""Tests for SQLite persistence, transactions, and schema management."""
import pytest
from app.models.canonical import AdministrativeGender, AuditEntry, IdentityStatus, MediaRecord, RecordType
from app.repositories.database import get_connection, get_db_transaction, initialize_database
from app.repositories.sqlite_repository import SqliteRepository
from app.services.patient_service import PatientService


def test_sqlite_patient_persistence() -> None:
    """Verify storing and retrieving canonical patients."""
    repo = SqliteRepository()
    repo.save_patient(
        patient_key="pat_syn_pat_001",
        display_name="Alex Rivera",
        mrn_normalized="SYN-PAT-001",
        mrn_original=" syn-pat-001 ",
        dob="1980-04-12",
        gender="male",
        identity_status="verified_synthetic",
    )

    patient = repo.get_patient("pat_syn_pat_001")
    assert patient is not None
    assert patient["display_name"] == "Alex Rivera"
    assert patient["mrn_normalized"] == "SYN-PAT-001"
    assert patient["gender"] == "male"


def test_sqlite_media_record_and_audit_persistence() -> None:
    """Verify persisting media records along with their audit trails."""
    repo = SqliteRepository()
    repo.save_patient(
        patient_key="pat_syn_pat_001",
        display_name="Alex Rivera",
        mrn_normalized="SYN-PAT-001",
    )

    audit = [
        AuditEntry(
            action="normalize",
            field="mrn",
            before_value="syn-001",
            after_value="SYN-001",
            reason="Uppercased MRN",
        )
    ]

    record = MediaRecord(
        record_id="rec_test_001",
        patient_key="pat_syn_pat_001",
        patient_name="Alex Rivera",
        mrn_normalized="SYN-PAT-001",
        record_type=RecordType.IMAGING,
        title="Chest Radiograph",
        text="Normal findings.",
        source_file="test.json",
        source_index=0,
        fingerprint="fp_unique_12345",
        audit_trail=audit,
    )

    repo.save_media_record(record)

    fetched = repo.get_media_record("rec_test_001")
    assert fetched is not None
    assert fetched["title"] == "Chest Radiograph"
    assert fetched["fingerprint"] == "fp_unique_12345"

    # Verify audit log was stored
    audit_logs = repo.list_audit_logs(record_id="rec_test_001")
    assert len(audit_logs) == 1
    assert audit_logs[0]["action"] == "normalize"
    assert audit_logs[0]["field"] == "mrn"


def test_sqlite_transaction_rollback_on_failure() -> None:
    """Verify that failures inside get_db_transaction trigger a complete rollback."""
    repo = SqliteRepository()

    with pytest.raises(RuntimeError):
        with get_db_transaction() as conn:
            conn.execute(
                """
                INSERT INTO patients (
                    patient_key, mrn_normalized, display_name, dob, gender, identity_status, created_at, updated_at
                ) VALUES ('pat_rollback_test', 'SYN-ROLLBACK', 'Rollback Patient', '1990-01-01', 'other', 'verified', 'now', 'now');
                """
            )
            # Intentionally raise an error before commit
            raise RuntimeError("Simulated transaction failure")

    # Patient should NOT exist in database
    patient = repo.get_patient("pat_rollback_test")
    assert patient is None


def test_persistence_survives_reconnect() -> None:
    """Verify that stored data persists across separate connection instances (simulating restarts)."""
    repo = SqliteRepository()
    repo.save_patient(
        patient_key="pat_persist_test",
        display_name="Persistent Patient",
        mrn_normalized="SYN-PERSIST-001",
    )

    # Open a completely fresh connection and verify record exists
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM patients WHERE patient_key = 'pat_persist_test';").fetchone()
        assert row is not None
        assert row["display_name"] == "Persistent Patient"


def test_quarantined_record_handling_in_service() -> None:
    """Verify that quarantined conflict records do not create FHIR resources or corrupt bundles."""
    service = PatientService()
    repo = SqliteRepository()

    # Create primary verified patient
    normal_record = MediaRecord(
        record_id="rec_alex_001",
        patient_key="pat_syn_pat_001",
        patient_name="Alex Rivera",
        mrn_normalized="SYN-PAT-001",
        record_type=RecordType.CLINICAL_NOTE,
        title="Alex's Note",
        text="Alex's verified note content.",
        source_file="notes.txt",
        source_index=0,
        fingerprint="fp_alex_001",
        identity_status=IdentityStatus.VERIFIED_SYNTHETIC,
    )

    # Conflicting identity sharing the same MRN
    quarantined_record = MediaRecord(
        record_id="rec_conflict_002",
        patient_key="pat_syn_pat_001",
        patient_name="Logan Thorne",
        mrn_normalized="SYN-PAT-001",
        record_type=RecordType.CLINICAL_NOTE,
        title="Conflict Note",
        text="Logan's conflicting note.",
        source_file="notes.txt",
        source_index=1,
        fingerprint="fp_conflict_002",
        identity_status=IdentityStatus.CONFLICT_QUARANTINED,
    )

    service.persist_ingestion_data([normal_record, quarantined_record], {})

    # The quarantined record IS saved to canonical media_records for audit/review
    q_rec = repo.get_media_record("rec_conflict_002")
    assert q_rec is not None
    assert q_rec["identity_status"] == "quarantined"

    # But the FHIR Bundle for Alex only contains Alex's Patient + Alex's verified note (2 entries, not 3)
    bundle_data = service.get_patient_bundle("pat_syn_pat_001")
    assert bundle_data is not None
    assert bundle_data["resource_count"] == 2
    entries = bundle_data["bundle"]["entry"]
    assert len(entries) == 2
    assert entries[0]["resource"]["resourceType"] == "Patient"
    assert entries[1]["resource"]["resourceType"] == "DocumentReference"
    assert entries[1]["resource"]["description"] == "Alex's Note"
