"""Patient service orchestrating canonical persistence, FHIR mapping, and bundle assembly."""
import json
from typing import Any, Dict, List, Optional
from app.models.canonical import IdentityStatus, MediaRecord, PatientIdentity
from app.repositories.sqlite_repository import repository
from app.services.fhir_mapper import FhirMapper


class PatientService:
    """Service managing patient queries, FHIR generation, and Bundle lifecycle."""

    def __init__(self) -> None:
        self.repo = repository

    def persist_ingestion_data(
        self,
        accepted_records: List[MediaRecord],
        patient_identities: Dict[str, PatientIdentity],
    ) -> None:
        """Persist canonical records, map to FHIR resources, and build per-patient Bundles."""
        # 1. Group records by patient_key
        records_by_patient: Dict[str, List[MediaRecord]] = {}
        for rec in accepted_records:
            records_by_patient.setdefault(rec.patient_key, []).append(rec)

        # 2. Process each patient
        for patient_key, records in records_by_patient.items():
            first_rec = records[0]
            display_name = first_rec.patient_name
            norm_mrn = first_rec.mrn_normalized
            orig_mrn = first_rec.mrn_original
            dob = first_rec.dob
            gender = first_rec.gender
            id_status = first_rec.identity_status.value

            # Save canonical patient
            self.repo.save_patient(
                patient_key=patient_key,
                display_name=display_name,
                mrn_normalized=norm_mrn,
                mrn_original=orig_mrn,
                dob=dob,
                gender=gender.value,
                identity_status=id_status,
            )

            # Generate FHIR Patient resource
            patient_fhir = FhirMapper.map_patient_to_fhir(
                patient_key=patient_key,
                display_name=display_name,
                mrn=norm_mrn,
                dob=dob,
                gender=gender,
            )
            self.repo.save_fhir_resource(
                resource_id=patient_fhir.id,
                resource_type="Patient",
                patient_key=patient_key,
                resource_json=patient_fhir.model_dump_json(),
            )

            # Map and persist media records & FHIR resources
            patient_fhir_resources = []
            for rec in records:
                # Persist canonical media record
                self.repo.save_media_record(rec)

                # Skip generating valid FHIR resources for quarantined records to prevent medical record contamination
                if rec.identity_status == IdentityStatus.CONFLICT_QUARANTINED:
                    continue

                fhir_res = FhirMapper.map_record_to_fhir(rec, patient_fhir_id=patient_fhir.id)
                self.repo.save_fhir_resource(
                    resource_id=fhir_res.id,
                    resource_type=fhir_res.get_resource_type(),
                    patient_key=patient_key,
                    resource_json=fhir_res.model_dump_json(),
                    record_id=rec.record_id,
                )
                patient_fhir_resources.append(fhir_res)

            # Build and persist per-patient FHIR Bundle
            bundle, validation_report = FhirMapper.build_patient_bundle(
                patient=patient_fhir,
                resources=patient_fhir_resources,
            )

            self.repo.save_fhir_bundle(
                patient_key=patient_key,
                bundle_id=bundle.id,
                bundle_json=bundle.model_dump_json(),
                resource_count=len(bundle.entry),
                validation_status=validation_report["status"],
                validation_report=validation_report,
            )

    def list_patients(self) -> List[Dict[str, Any]]:
        """List all patients registered in the system."""
        return self.repo.list_patients()

    def get_patient(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """Get canonical patient metadata by key or MRN."""
        return self.repo.get_patient(patient_id)

    def get_patient_records(self, patient_id: str) -> List[Dict[str, Any]]:
        """Retrieve all media records linked to a patient."""
        return self.repo.list_records_for_patient(patient_id)

    def get_patient_bundle(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the persisted FHIR Bundle and validation report for a patient."""
        row = self.repo.get_fhir_bundle(patient_id)
        if not row:
            return None
        return {
            "bundle_id": row["bundle_id"],
            "patient_key": row["patient_key"],
            "bundle": json.loads(row["bundle_json"]),
            "resource_count": row["resource_count"],
            "validation_status": row["validation_status"],
            "validation_report": json.loads(row["validation_report_json"]),
            "updated_at": row["updated_at"],
        }

    def get_fhir_resource(self, resource_type: str, resource_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an individual raw FHIR resource JSON by type and ID."""
        row = self.repo.get_fhir_resource(resource_id=resource_id, resource_type=resource_type)
        if not row:
            return None
        return json.loads(row["resource_json"])

    async def get_patient_summary(
        self,
        patient_id: str,
        force_refresh: bool = False,
    ) -> Optional[Any]:
        """Generate or retrieve cached clinical summary for a patient."""
        from app.models.canonical import AdministrativeGender, MediaRecord, RecordType
        from app.services.summarization.service import summarization_service

        patient = self.get_patient(patient_id)
        if not patient:
            return None

        # Fetch records
        raw_records = self.get_patient_records(patient["patient_key"])
        media_records: List[MediaRecord] = []
        for r in raw_records:
            media_records.append(
                MediaRecord(
                    record_id=r["record_id"],
                    patient_key=r["patient_key"],
                    patient_name=patient["display_name"],
                    mrn_normalized=patient.get("mrn_normalized"),
                    mrn_original=patient.get("mrn_original"),
                    dob=patient.get("dob"),
                    gender=AdministrativeGender(patient.get("gender", "unknown")),
                    record_date=r.get("record_date"),
                    record_type=RecordType(r.get("record_type", "other")),
                    title=r.get("title", "Clinical Record"),
                    text=r.get("text", ""),
                    source_file=r.get("source_file", "db"),
                    source_index=r.get("source_index", 0),
                    encounter_id=r.get("encounter_id"),
                    fingerprint=r.get("fingerprint", "fp"),
                    identity_status=IdentityStatus(r.get("identity_status", "verified_synthetic")),
                )
            )

        summary = await summarization_service.get_or_generate_summary(
            patient_info=patient,
            records=media_records,
            force_refresh=force_refresh,
        )
        return summary


patient_service = PatientService()
