"""Ingestion API route handling file uploads."""
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from app.ingestion.parsers import ParseException
from app.ingestion.service import ingestion_service
from app.models.canonical import IngestError, IngestResult

router = APIRouter()

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit


@router.post(
    "/ingest",
    response_model=IngestResult,
    status_code=status.HTTP_200_OK,
    summary="Ingest and clean clinical records",
    description="Upload a JSON, CSV, or TXT file of clinical media records for parsing, normalization, and deduplication.",
)
async def ingest_file(file: UploadFile = File(...)) -> IngestResult:
    """Ingest, parse, normalize, and deduplicate clinical media records from an uploaded file."""
    filename = file.filename or "uploaded_data.txt"

    # Enforce file size limit
    content_bytes = await file.read()
    if len(content_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413),
            detail=f"Uploaded file exceeds maximum size limit of {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB",
        )

    try:
        content_str = content_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        try:
            content_str = content_bytes.decode("latin-1")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unable to decode file '{filename}' with UTF-8 or Latin-1 encoding",
            ) from exc

    try:
        result = ingestion_service.ingest_file(content_str, filename)
        return result
    except ParseException as pe:
        return IngestResult(
            accepted=0,
            rejected=1,
            duplicates=0,
            quarantined=0,
            warnings=[f"Parse error in {filename}: {pe.message}"],
            record_ids=[],
            errors=[IngestError(record_index=pe.record_index, code=pe.code, message=pe.message)],
            audit_log=[],
        )
