"""FHIR R4 resource and Bundle mapping and validation service."""
import base64
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from fhir.resources.attachment import Attachment
from fhir.resources.bundle import Bundle, BundleEntry
from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.coding import Coding
from fhir.resources.diagnosticreport import DiagnosticReport
from fhir.resources.documentreference import DocumentReference, DocumentReferenceContent
from fhir.resources.humanname import HumanName
from fhir.resources.identifier import Identifier
from fhir.resources.patient import Patient
from fhir.resources.reference import Reference
from pydantic import ValidationError

from app.models.canonical import AdministrativeGender, MediaRecord, PatientDemographics, RecordType


class FhirMappingError(Exception):
    """Exception raised when FHIR resource mapping fails."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class FhirMapper:
    """Mapper from canonical clinical models to HL7 FHIR R4 resources."""

    DEMO_SYSTEM_MRN = "http://hospital.demo.org/mrn"
    DEMO_SYSTEM_BASE_URL = "http://demo.ehr.org/fhir"

    @classmethod
    def get_patient_fhir_id(cls, patient_key: str) -> str:
        """Derive a deterministic, valid FHIR id string for a patient."""
        # FHIR ID regex: [A-Za-z0-9\-\.]{1,64}
        clean = patient_key.lower().replace("_", "-")
        if not clean.startswith("pat-"):
            clean = f"pat-{clean}"
        return clean[:64]

    @classmethod
    def get_resource_fhir_id(cls, record_id: str, record_type: RecordType) -> str:
        """Derive a deterministic, valid FHIR id string for a media record."""
        clean = record_id.lower().replace("_", "-")
        prefix = "diag" if record_type in (RecordType.LAB, RecordType.PATHOLOGY) else "doc"
        if not clean.startswith(f"{prefix}-"):
            clean = f"{prefix}-{clean}"
        return clean[:64]

    @classmethod
    def map_patient_to_fhir(
        cls,
        patient_key: str,
        display_name: str,
        mrn: Optional[str] = None,
        dob: Optional[str] = None,
        gender: AdministrativeGender = AdministrativeGender.UNKNOWN,
    ) -> Patient:
        """Map canonical patient demographics to a valid FHIR R4 Patient resource."""
        patient_id = cls.get_patient_fhir_id(patient_key)

        # Parse name components safely
        name_parts = display_name.strip().split()
        if len(name_parts) > 1:
            family = name_parts[-1]
            given = name_parts[:-1]
        else:
            family = display_name.strip()
            given = []

        human_name = HumanName(
            text=display_name.strip(),
            family=family,
            given=given if given else None,
        )

        identifiers = []
        if mrn:
            identifiers.append(
                Identifier(
                    system=cls.DEMO_SYSTEM_MRN,
                    value=mrn,
                )
            )

        # Validate gender against FHIR administrative gender codes
        fhir_gender = gender.value if gender in AdministrativeGender else "unknown"

        patient_data: Dict[str, Any] = {
            "id": patient_id,
            "identifier": identifiers if identifiers else None,
            "name": [human_name],
            "gender": fhir_gender,
        }

        # Birth date included only if valid ISO date format
        if dob:
            patient_data["birthDate"] = dob

        try:
            return Patient(**patient_data)
        except ValidationError as exc:
            raise FhirMappingError(f"Validation failed for FHIR Patient: {exc}", {"errors": exc.errors()}) from exc

    @classmethod
    def map_record_to_fhir(
        cls,
        record: MediaRecord,
        patient_fhir_id: Optional[str] = None,
    ) -> Union[DocumentReference, DiagnosticReport]:
        """Map a canonical MediaRecord to either DocumentReference or DiagnosticReport."""
        target_patient_id = patient_fhir_id or cls.get_patient_fhir_id(record.patient_key)
        subject_ref = Reference(
            reference=f"Patient/{target_patient_id}",
            display=record.patient_name,
        )
        resource_id = cls.get_resource_fhir_id(record.record_id, record.record_type)

        # Base64-encode document text for standard FHIR Attachment representation
        encoded_data = base64.b64encode(record.text.encode("utf-8")).decode("utf-8")
        attachment = Attachment(
            contentType="text/plain",
            title=record.title,
            data=encoded_data,
        )

        # 1. Map Lab and Pathology records to DiagnosticReport
        if record.record_type in (RecordType.LAB, RecordType.PATHOLOGY):
            category_code = "LAB" if record.record_type == RecordType.LAB else "PAT"
            category_display = "Laboratory" if record.record_type == RecordType.LAB else "Pathology"

            category = [
                CodeableConcept(
                    coding=[
                        Coding(
                            system="http://terminology.hl7.org/CodeSystem/v2-0074",
                            code=category_code,
                            display=category_display,
                        )
                    ],
                    text=category_display,
                )
            ]

            report_data: Dict[str, Any] = {
                "id": resource_id,
                "status": "final",
                "category": category,
                "code": CodeableConcept(text=record.title),
                "subject": subject_ref,
                "conclusion": record.text[:500],
                "presentedForm": [attachment],
            }

            if record.record_date:
                report_data["effectiveDateTime"] = f"{record.record_date}T00:00:00Z"

            try:
                return DiagnosticReport(**report_data)
            except ValidationError as exc:
                raise FhirMappingError(f"Validation failed for DiagnosticReport {resource_id}: {exc}", {"errors": exc.errors()}) from exc

        # 2. Map Imaging, Clinical Notes, Discharge Summaries to DocumentReference
        else:
            doc_class_code = record.record_type.value
            doc_class_display = record.record_type.value.replace("_", " ").capitalize()

            category = [
                CodeableConcept(
                    coding=[
                        Coding(
                            system="http://hl7.org/fhir/ValueSet/document-classcodes",
                            code=doc_class_code,
                            display=doc_class_display,
                        )
                    ],
                    text=doc_class_display,
                )
            ]

            doc_data: Dict[str, Any] = {
                "id": resource_id,
                "status": "current",
                "category": category,
                "type": CodeableConcept(text=record.title),
                "subject": subject_ref,
                "description": record.title,
                "content": [
                    DocumentReferenceContent(attachment=attachment)
                ],
            }

            if record.record_date:
                doc_data["date"] = f"{record.record_date}T00:00:00Z"
            else:
                doc_data["date"] = datetime.now(timezone.utc).isoformat()

            try:
                return DocumentReference(**doc_data)
            except ValidationError as exc:
                raise FhirMappingError(f"Validation failed for DocumentReference {resource_id}: {exc}", {"errors": exc.errors()}) from exc

    @classmethod
    def build_patient_bundle(
        cls,
        patient: Patient,
        resources: List[Union[DocumentReference, DiagnosticReport]],
        base_url: str = DEMO_SYSTEM_BASE_URL,
    ) -> Tuple[Bundle, Dict[str, Any]]:
        """Construct, validate, and report on a per-patient FHIR R4 Bundle."""
        patient_id = patient.id
        bundle_id = f"bundle-{patient_id}"

        entries: List[BundleEntry] = []
        seen_entry_ids = set()

        # Entry 0: Patient resource
        patient_full_url = f"{base_url}/Patient/{patient_id}"
        entries.append(
            BundleEntry(
                fullUrl=patient_full_url,
                resource=patient,
            )
        )
        seen_entry_ids.add(f"Patient/{patient_id}")

        # Entries 1..N: Associated media resources (deduplicated by resourceType/id)
        for res in resources:
            res_type = res.get_resource_type()
            res_key = f"{res_type}/{res.id}"
            if res_key in seen_entry_ids:
                continue
            seen_entry_ids.add(res_key)

            entries.append(
                BundleEntry(
                    fullUrl=f"{base_url}/{res_type}/{res.id}",
                    resource=res,
                )
            )

        bundle = Bundle(
            id=bundle_id,
            type="collection",
            entry=entries,
        )

        validation_report = cls.validate_fhir_bundle(bundle, expected_patient_id=patient_id)
        return bundle, validation_report

    @classmethod
    def validate_fhir_bundle(
        cls,
        bundle: Bundle,
        expected_patient_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validate FHIR Bundle schema and reference integrity."""
        errors: List[str] = []
        resource_types: List[str] = []

        if not bundle.entry:
            errors.append("Bundle has no entries")
            return {
                "valid": False,
                "errors": errors,
                "resource_count": 0,
                "resource_types": [],
            }

        # Check entry 0 is the Patient
        first_res = bundle.entry[0].resource
        if first_res.get_resource_type() != "Patient":
            errors.append(f"Expected first Bundle entry to be Patient, got {first_res.get_resource_type()}")

        patient_id = expected_patient_id or (first_res.id if first_res else None)
        expected_patient_ref = f"Patient/{patient_id}"

        seen_urls = set()
        for idx, entry in enumerate(bundle.entry):
            if not entry.fullUrl:
                errors.append(f"Entry {idx} is missing fullUrl")
            elif entry.fullUrl in seen_urls:
                errors.append(f"Duplicate fullUrl '{entry.fullUrl}' at entry {idx}")
            else:
                seen_urls.add(entry.fullUrl)

            res = entry.resource
            if not res:
                errors.append(f"Entry {idx} contains null resource")
                continue

            res_type = res.get_resource_type()
            resource_types.append(res_type)

            # Check subject reference integrity
            if res_type in ("DocumentReference", "DiagnosticReport"):
                subject = getattr(res, "subject", None)
                if not subject or not subject.reference:
                    errors.append(f"Resource {res_type}/{res.id} missing subject reference")
                elif patient_id and subject.reference != expected_patient_ref:
                    errors.append(
                        f"Resource {res_type}/{res.id} subject reference '{subject.reference}' "
                        f"does not match Bundle patient '{expected_patient_ref}'"
                    )

        is_valid = len(errors) == 0
        return {
            "valid": is_valid,
            "status": "valid" if is_valid else "invalid",
            "errors": errors,
            "resource_count": len(bundle.entry),
            "resource_types": list(set(resource_types)),
            "validated_at": datetime.now(timezone.utc).isoformat(),
        }
