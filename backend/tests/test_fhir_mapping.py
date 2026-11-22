"""Unit tests for HL7 FHIR R4 resource mapping and Bundle assembly."""
import json
from fhir.resources.bundle import Bundle
from fhir.resources.diagnosticreport import DiagnosticReport
from fhir.resources.documentreference import DocumentReference
from fhir.resources.patient import Patient

from app.models.canonical import AdministrativeGender, MediaRecord, RecordType
from app.services.fhir_mapper import FhirMapper


def test_map_patient_to_fhir_valid() -> None:
    """Verify mapping of patient demographics to valid FHIR Patient."""
    patient = FhirMapper.map_patient_to_fhir(
        patient_key="pat_syn_pat_001",
        display_name="Alex Rivera",
        mrn="SYN-PAT-001",
        dob="1980-04-12",
        gender=AdministrativeGender.MALE,
    )

    assert isinstance(patient, Patient)
    assert patient.id == "pat-syn-pat-001"
    assert patient.gender == "male"
    assert str(patient.birthDate) == "1980-04-12"
    assert len(patient.name) == 1
    assert patient.name[0].family == "Rivera"
    assert patient.name[0].given == ["Alex"]
    assert len(patient.identifier) == 1
    assert patient.identifier[0].value == "SYN-PAT-001"
    assert patient.identifier[0].system == FhirMapper.DEMO_SYSTEM_MRN

    # Ensure schema can serialize to valid JSON
    dumped = json.loads(patient.model_dump_json())
    assert dumped["resourceType"] == "Patient"


def test_map_document_reference_from_clinical_note() -> None:
    """Verify mapping of a clinical note to a valid DocumentReference."""
    record = MediaRecord(
        record_id="rec_pat_001_note_12345678",
        patient_key="pat_syn_pat_001",
        patient_name="Alex Rivera",
        mrn_normalized="SYN-PAT-001",
        dob="1980-04-12",
        gender=AdministrativeGender.MALE,
        record_date="2025-01-15",
        record_type=RecordType.CLINICAL_NOTE,
        title="Follow-Up Progress Note",
        text="Patient feeling much better, fever resolved.",
        source_file="test.json",
        source_index=0,
        fingerprint="fp12345678",
    )

    doc_ref = FhirMapper.map_record_to_fhir(record)
    assert isinstance(doc_ref, DocumentReference)
    assert doc_ref.status == "current"
    assert doc_ref.subject.reference == "Patient/pat-syn-pat-001"
    assert doc_ref.subject.display == "Alex Rivera"
    assert doc_ref.description == "Follow-Up Progress Note"
    assert len(doc_ref.content) == 1
    assert doc_ref.content[0].attachment.contentType == "text/plain"


def test_map_diagnostic_report_from_lab_record() -> None:
    """Verify mapping of a lab test record to a valid DiagnosticReport."""
    record = MediaRecord(
        record_id="rec_pat_001_lab_87654321",
        patient_key="pat_syn_pat_001",
        patient_name="Alex Rivera",
        mrn_normalized="SYN-PAT-001",
        dob="1980-04-12",
        gender=AdministrativeGender.MALE,
        record_date="2025-01-10",
        record_type=RecordType.LAB,
        title="Complete Blood Count",
        text="WBC: 14.8 x10^3/uL [High]. Hemoglobin: 14.2 g/dL [Normal].",
        source_file="test.json",
        source_index=1,
        fingerprint="fp87654321",
    )

    diag = FhirMapper.map_record_to_fhir(record)
    assert isinstance(diag, DiagnosticReport)
    assert diag.status == "final"
    assert diag.subject.reference == "Patient/pat-syn-pat-001"
    assert diag.code.text == "Complete Blood Count"
    assert diag.category[0].coding[0].code == "LAB"
    assert "WBC: 14.8" in diag.conclusion


def test_build_patient_bundle_collection_and_reference_integrity() -> None:
    """Verify that per-patient Bundle has valid collection structure and reference integrity."""
    patient = FhirMapper.map_patient_to_fhir(
        patient_key="pat_syn_pat_001",
        display_name="Alex Rivera",
        mrn="SYN-PAT-001",
    )

    record_doc = MediaRecord(
        record_id="rec_pat_001_img_11111111",
        patient_key="pat_syn_pat_001",
        patient_name="Alex Rivera",
        record_type=RecordType.IMAGING,
        title="Chest X-Ray",
        text="Focal pneumonia consolidation.",
        source_file="test.json",
        source_index=0,
        fingerprint="fp11111111",
    )
    doc_res = FhirMapper.map_record_to_fhir(record_doc)

    record_lab = MediaRecord(
        record_id="rec_pat_001_lab_22222222",
        patient_key="pat_syn_pat_001",
        patient_name="Alex Rivera",
        record_type=RecordType.LAB,
        title="CBC Lab",
        text="Leukocytosis noted.",
        source_file="test.json",
        source_index=1,
        fingerprint="fp22222222",
    )
    lab_res = FhirMapper.map_record_to_fhir(record_lab)

    bundle, report = FhirMapper.build_patient_bundle(
        patient=patient,
        resources=[doc_res, lab_res],
    )

    assert isinstance(bundle, Bundle)
    assert bundle.type == "collection"
    assert len(bundle.entry) == 3
    assert bundle.entry[0].resource.get_resource_type() == "Patient"
    assert report["valid"] is True
    assert report["status"] == "valid"
    assert report["resource_count"] == 3
    assert set(report["resource_types"]) == {"Patient", "DocumentReference", "DiagnosticReport"}


def test_bundle_validation_detects_mismatched_subject() -> None:
    """Verify that Bundle reference validator flags broken or mismatched subject references."""
    patient = FhirMapper.map_patient_to_fhir(
        patient_key="pat_syn_pat_001",
        display_name="Alex Rivera",
    )

    # Document pointing to a different patient
    bad_record = MediaRecord(
        record_id="rec_foreign_001",
        patient_key="pat_foreign_999",
        patient_name="Foreign Patient",
        record_type=RecordType.CLINICAL_NOTE,
        title="Unrelated Note",
        text="Note belonging to another patient.",
        source_file="test.json",
        source_index=0,
        fingerprint="fpforeign",
    )
    mismatched_doc = FhirMapper.map_record_to_fhir(bad_record, patient_fhir_id="pat-foreign-999")

    bundle, report = FhirMapper.build_patient_bundle(
        patient=patient,
        resources=[mismatched_doc],
    )

    assert report["valid"] is False
    assert report["status"] == "invalid"
    assert any("does not match Bundle patient" in err for err in report["errors"])
