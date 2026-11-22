"""Patient and Bundle API routes."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from app.models.summary import ClinicalSummary
from app.services.patient_service import patient_service

router = APIRouter()


@router.get(
    "/patients",
    summary="List patients",
    description="Retrieve all registered synthetic patients and their record counts.",
)
async def list_patients() -> List[Dict[str, Any]]:
    """Return patient list with canonical identifiers and record counts."""
    return patient_service.list_patients()


@router.get(
    "/patients/{patient_id}",
    summary="Get patient details",
    description="Retrieve patient demographic metadata and linked record count.",
)
async def get_patient(patient_id: str) -> Dict[str, Any]:
    """Return patient metadata by key or MRN."""
    patient = patient_service.get_patient(patient_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient '{patient_id}' not found",
        )
    return patient


@router.get(
    "/patients/{patient_id}/records",
    summary="List patient media records",
    description="Retrieve all canonical media records linked to a patient.",
)
async def get_patient_records(patient_id: str) -> List[Dict[str, Any]]:
    """Return media records for patient by key or MRN."""
    patient = patient_service.get_patient(patient_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient '{patient_id}' not found",
        )
    return patient_service.get_patient_records(patient_id)


@router.get(
    "/patients/{patient_id}/bundle",
    summary="Get patient FHIR Bundle",
    description="Retrieve the persisted FHIR R4 Bundle JSON and validation report for a patient.",
)
async def get_patient_bundle(patient_id: str) -> Dict[str, Any]:
    """Return the saved FHIR Bundle JSON and validation report."""
    bundle_data = patient_service.get_patient_bundle(patient_id)
    if not bundle_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FHIR Bundle for patient '{patient_id}' not found",
        )
    return bundle_data


@router.get(
    "/patients/{patient_id}/summary",
    response_model=ClinicalSummary,
    summary="Get patient clinical summary",
    description="Retrieve or generate a structured, grounded clinical summary for a patient.",
)
async def get_patient_summary(
    patient_id: str,
    force_refresh: bool = Query(default=False, description="Bypass cache and force summary regeneration"),
) -> ClinicalSummary:
    """Return cached or newly generated patient summary with fallback guarantees."""
    summary = await patient_service.get_patient_summary(patient_id=patient_id, force_refresh=force_refresh)
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient '{patient_id}' not found",
        )
    return summary
