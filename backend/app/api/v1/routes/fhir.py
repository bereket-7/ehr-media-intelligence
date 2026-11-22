"""Direct FHIR R4 resource retrieval endpoints."""
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Response, status
from app.services.patient_service import patient_service

router = APIRouter(prefix="/fhir", tags=["FHIR"])


@router.get(
    "/Patient/{resource_id}",
    summary="Get FHIR Patient resource",
    description="Retrieve a raw FHIR R4 Patient resource by ID.",
)
async def get_fhir_patient(resource_id: str) -> Dict[str, Any]:
    """Return raw FHIR Patient resource JSON."""
    res = patient_service.get_fhir_resource(resource_type="Patient", resource_id=resource_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FHIR Patient resource '{resource_id}' not found",
        )
    return res


@router.get(
    "/DocumentReference/{resource_id}",
    summary="Get FHIR DocumentReference resource",
    description="Retrieve a raw FHIR R4 DocumentReference resource by ID.",
)
async def get_fhir_document_reference(resource_id: str) -> Dict[str, Any]:
    """Return raw FHIR DocumentReference resource JSON."""
    res = patient_service.get_fhir_resource(resource_type="DocumentReference", resource_id=resource_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FHIR DocumentReference resource '{resource_id}' not found",
        )
    return res


@router.get(
    "/DiagnosticReport/{resource_id}",
    summary="Get FHIR DiagnosticReport resource",
    description="Retrieve a raw FHIR R4 DiagnosticReport resource by ID.",
)
async def get_fhir_diagnostic_report(resource_id: str) -> Dict[str, Any]:
    """Return raw FHIR DiagnosticReport resource JSON."""
    res = patient_service.get_fhir_resource(resource_type="DiagnosticReport", resource_id=resource_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FHIR DiagnosticReport resource '{resource_id}' not found",
        )
    return res
