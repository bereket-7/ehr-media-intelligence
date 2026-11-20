"""Unit tests for clinical record ingestion, parsing, normalization, and edge cases."""
import pytest
from app.ingestion.cleaner import DataCleaner
from app.ingestion.parsers import CsvParser, JsonParser, ParseException, PlainTextParser
from app.ingestion.service import IngestionService
from app.models.canonical import AdministrativeGender, IdentityStatus, RecordType


# -------------------------------------------------------------------------
# Parser Unit Tests
# -------------------------------------------------------------------------

def test_json_parser_valid_list() -> None:
    content = '[{"patient_name": "Test Patient", "text": "Clinical note text"}]'
    records = JsonParser.parse(content, "test.json")
    assert len(records) == 1
    assert records[0][0] == 0
    assert records[0][1]["patient_name"] == "Test Patient"


def test_json_parser_invalid_syntax_raises_parse_exception() -> None:
    with pytest.raises(ParseException) as exc_info:
        JsonParser.parse("INVALID_JSON{", "bad.json")
    assert exc_info.value.code == "invalid_json"


def test_json_parser_invalid_shape_raises_parse_exception() -> None:
    with pytest.raises(ParseException) as exc_info:
        JsonParser.parse('"just a string"', "scalar.json")
    assert exc_info.value.code == "invalid_json_shape"


def test_csv_parser_valid_and_whitespace_cleaning() -> None:
    csv_content = (
        "patient_name , mrn , text \n"
        "Alex Rivera , MRN-001 , Chest radiograph clear \n"
    )
    records = CsvParser.parse(csv_content, "test.csv")
    assert len(records) == 1
    assert records[0][1]["patient_name"] == "Alex Rivera "
    assert records[0][1]["mrn"] == " MRN-001 "


def test_csv_parser_empty_raises_parse_exception() -> None:
    with pytest.raises(ParseException) as exc_info:
        CsvParser.parse("", "empty.csv")
    assert exc_info.value.code == "empty_csv"


def test_plain_text_parser_multi_chunk() -> None:
    txt = (
        "PATIENT: Jane Doe\n"
        "MRN: SYN-001\n"
        "DATE: 2025-01-10\n"
        "TYPE: imaging\n"
        "NOTE:\n"
        "Normal chest X-ray.\n"
        "---\n"
        "PATIENT: John Smith\n"
        "MRN: SYN-002\n"
        "NOTE:\n"
        "Normal ECG tracing.\n"
    )
    records = PlainTextParser.parse(txt, "test.txt")
    assert len(records) == 2
    assert records[0][1]["patient_name"] == "Jane Doe"
    assert records[0][1]["mrn"] == "SYN-001"
    assert "Normal chest X-ray." in records[0][1]["text"]
    assert records[1][1]["patient_name"] == "John Smith"
    assert "Normal ECG tracing." in records[1][1]["text"]


# -------------------------------------------------------------------------
# Cleaner & Normalizer Unit Tests
# -------------------------------------------------------------------------

def test_gender_normalization_variants() -> None:
    audit = []
    # Male variants
    g, _ = DataCleaner.normalize_gender("m", audit)
    assert g == AdministrativeGender.MALE

    # Female variants
    g, _ = DataCleaner.normalize_gender("woman", audit)
    assert g == AdministrativeGender.FEMALE

    # Nonbinary variants
    g, _ = DataCleaner.normalize_gender("nonbinary", audit)
    assert g == AdministrativeGender.OTHER

    # Unknown / Unrecognized variants
    g, _ = DataCleaner.normalize_gender("X", audit)
    assert g == AdministrativeGender.UNKNOWN


def test_date_normalization_formats() -> None:
    audit, warnings = [], []
    # ISO
    d1, _ = DataCleaner.normalize_date("2025-01-15", "record_date", audit, warnings)
    assert d1 == "2025-01-15"

    # US slash MM/DD/YYYY
    d2, _ = DataCleaner.normalize_date("01/15/2025", "record_date", audit, warnings)
    assert d2 == "2025-01-15"

    # European dash DD-MM-YYYY
    d3, _ = DataCleaner.normalize_date("15-01-2025", "record_date", audit, warnings)
    assert d3 == "2025-01-15"

    # Invalid / Unparseable date
    d4, _ = DataCleaner.normalize_date("32-99-2025", "record_date", audit, warnings)
    assert d4 is None
    assert len(warnings) > 0


# -------------------------------------------------------------------------
# Required Edge Case Tests (Ingestion Pipeline)
# -------------------------------------------------------------------------

def test_edge_case_1_missing_mrn_assigned_synthetic_key() -> None:
    """Edge Case 1: Missing MRN receives a deterministic synthetic key and missing flag."""
    service = IngestionService()
    raw = [
        (0, {
            "patient_name": "Unregistered Patient",
            "mrn": "",
            "text": "Walk-in urgent care visit note without prior hospital MRN.",
            "record_type": "clinical_note",
        })
    ]
    result = service.process_records(raw, "test_missing_mrn.json")
    assert result.accepted == 1
    record = list(service.records.values())[0]
    assert record.identity_status == IdentityStatus.MISSING_MRN
    assert record.mrn_normalized.startswith("SYN-MISSING-")
    # Verify audit trail recorded this
    assert any(entry.action == "impute_synthetic_key" for entry in record.audit_trail)


def test_edge_case_2_duplicate_fingerprint_suppression() -> None:
    """Edge Case 2: Near-duplicate documents are detected via SHA-256 fingerprint and suppressed."""
    service = IngestionService()
    raw = [
        (0, {
            "patient_name": "Alex Rivera",
            "mrn": "SYN-PAT-001",
            "record_date": "2025-01-10",
            "record_type": "imaging",
            "text": "Focal patchy consolidation in right middle lobe consistent with pneumonia.",
        }),
        (1, {
            "patient_name": "Alex Rivera",
            "mrn": "SYN-PAT-001",
            "record_date": "2025-01-10",
            "record_type": "imaging",
            "text": "Focal   patchy consolidation in right middle lobe consistent with pneumonia. ",
        }),
    ]
    result = service.process_records(raw, "test_duplicates.json")
    assert result.accepted == 1
    assert result.duplicates == 1
    assert len(service.records) == 1
    assert any("Exact match" in entry.reason for entry in result.audit_log)


def test_edge_case_3_identifier_conflict_quarantine() -> None:
    """Edge Case 3: Conflicting patient identities sharing an MRN are quarantined, not merged by name."""
    service = IngestionService()
    raw = [
        (0, {
            "patient_name": "Alex Rivera",
            "mrn": "SYN-PAT-001",
            "text": "Initial pulmonary clinic note.",
            "record_type": "clinical_note",
        }),
        (1, {
            "patient_name": "Logan Thorne",  # Conflicting name on existing MRN
            "mrn": "SYN-PAT-001",
            "text": "Conflicting visit record erroneously filed under Alex's MRN.",
            "record_type": "clinical_note",
        }),
    ]
    result = service.process_records(raw, "test_conflict.json")
    assert result.accepted == 2
    assert result.quarantined == 1
    assert any("Identity conflict" in w for w in result.warnings)

    records = list(service.records.values())
    quarantined_record = records[1]
    assert quarantined_record.identity_status == IdentityStatus.CONFLICT_QUARANTINED
    assert any(entry.action == "quarantine" for entry in quarantined_record.audit_trail)


def test_edge_case_4_empty_text_rejection() -> None:
    """Edge Case 4: Records with blank or whitespace-only clinical text are rejected with validation error."""
    service = IngestionService()
    raw = [
        (0, {
            "patient_name": "Avery Kim",
            "mrn": "SYN-PAT-006",
            "text": "   ",  # Blank
        })
    ]
    result = service.process_records(raw, "test_empty.json")
    assert result.accepted == 0
    assert result.rejected == 1
    assert len(result.errors) == 1
    assert result.errors[0].code == "empty_content"
