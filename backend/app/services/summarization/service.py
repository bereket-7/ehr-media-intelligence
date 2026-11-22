"""Clinical summarization service with caching, provider switching, and deterministic fallback."""
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.models.canonical import MediaRecord
from app.models.summary import ClinicalSummary, RecentRecordSummary
from app.repositories.sqlite_repository import repository
from app.services.summarization.base import BaseSummarizationProvider, ProviderError
from app.services.summarization.deterministic_fallback import DeterministicFallbackSummarizer
from app.services.summarization.openai_provider import OpenAISummarizationProvider

logger = get_logger(__name__)


class SummarizationService:
    """Service managing clinical summary generation, caching, and fallback execution."""

    def __init__(
        self,
        provider: Optional[BaseSummarizationProvider] = None,
        prompt_version: Optional[str] = None,
    ) -> None:
        self.provider = provider
        self.prompt_version = prompt_version or settings.SUMMARY_PROMPT_VERSION

    def compute_records_hash(self, records: List[MediaRecord]) -> str:
        """Compute stable SHA-256 hash across all patient records and their content."""
        if not records:
            return "empty_records"
        sorted_records = sorted(records, key=lambda r: r.record_id)
        content_tokens = [f"{r.record_id}:{r.fingerprint}:{r.record_date or ''}" for r in sorted_records]
        return hashlib.sha256("|".join(content_tokens).encode("utf-8")).hexdigest()

    def compute_cache_key(
        self,
        patient_key: str,
        records_hash: str,
        provider_name: str,
        model_name: str,
    ) -> str:
        """Generate deterministic cache key combining patient, records hash, model, and prompt version."""
        key_raw = f"{patient_key}:{records_hash}:{provider_name}:{model_name}:{self.prompt_version}"
        return hashlib.sha256(key_raw.encode("utf-8")).hexdigest()

    async def get_or_generate_summary(
        self,
        patient_info: Dict[str, Any],
        records: List[MediaRecord],
        force_refresh: bool = False,
    ) -> ClinicalSummary:
        """Retrieve cached summary or generate a fresh structured summary with fallback guarantees."""
        patient_key = patient_info["patient_key"]
        display_name = patient_info.get("display_name", "Unknown Patient")
        mrn = patient_info.get("mrn_normalized")

        records_hash = self.compute_records_hash(records)

        # 1. Determine active provider
        active_provider = self.provider
        if not active_provider:
            if settings.OPENAI_API_KEY and settings.LLM_PROVIDER.lower() == "openai":
                active_provider = OpenAISummarizationProvider()

        provider_name = active_provider.name if active_provider else "deterministic_fallback"
        model_name = active_provider.model if active_provider else "none"

        # 2. Check Cache
        cache_key = self.compute_cache_key(
            patient_key=patient_key,
            records_hash=records_hash,
            provider_name=provider_name,
            model_name=model_name,
        )

        if not force_refresh:
            cached_row = repository.get_summary_cache(cache_key)
            if cached_row:
                logger.info("Summary cache hit for patient %s (key: %s)", patient_key, cache_key[:12])
                cached_data = json.loads(cached_row["summary_json"])
                cached_data["cache_status"] = "hit"
                return ClinicalSummary.model_validate(cached_data)

        logger.info("Summary cache miss for patient %s (key: %s)", patient_key, cache_key[:12])

        # 3. Attempt Generation via Active Provider
        generated_by = "fallback"
        is_ai_generated = False
        summary_payload: Dict[str, Any] = {}

        if active_provider:
            try:
                summary_payload = await active_provider.summarize(patient_info, records)
                generated_by = "llm"
                is_ai_generated = True
                logger.info("LLM summary generated successfully for patient %s", patient_key)
            except ProviderError as pe:
                logger.warning("LLM provider '%s' failed (%s); reverting to deterministic fallback.", active_provider.name, pe.message)
                summary_payload = DeterministicFallbackSummarizer.generate(patient_info, records)
                provider_name = "deterministic_fallback"
                model_name = "none"
            except Exception as exc:
                logger.error("Unexpected error during LLM summarization: %s; using deterministic fallback.", exc)
                summary_payload = DeterministicFallbackSummarizer.generate(patient_info, records)
                provider_name = "deterministic_fallback"
                model_name = "none"
        else:
            # Deterministic offline fallback
            summary_payload = DeterministicFallbackSummarizer.generate(patient_info, records)
            provider_name = "deterministic_fallback"
            model_name = "none"

        # 4. Assemble Validated ClinicalSummary Model
        recent_records = [
            RecentRecordSummary(
                record_id=r["record_id"],
                record_type=r["record_type"],
                title=r["title"],
                record_date=r.get("record_date"),
                brief_finding=r["brief_finding"],
            )
            for r in summary_payload.get("recent_records", [])
        ]

        narrative = summary_payload.get("narrative_summary", "")

        clinical_summary = ClinicalSummary(
            patient_id=patient_key,
            patient_name=display_name,
            mrn=mrn,
            chief_concern=summary_payload.get("chief_concern", "Not stated in source records"),
            key_diagnoses=summary_payload.get("key_diagnoses", []),
            recent_records=recent_records,
            key_findings=summary_payload.get("key_findings", []),
            flagged_anomalies=summary_payload.get("flagged_anomalies", []),
            data_quality_issues=summary_payload.get("data_quality_issues", []),
            narrative_summary=narrative,
            word_count=len(narrative.split()),
            confidence_or_limitations=summary_payload.get(
                "confidence_or_limitations",
                "Summary compiled from indexed media records.",
            ),
            generated_at=datetime.now(timezone.utc).isoformat(),
            generated_by=generated_by,
            is_ai_generated=is_ai_generated,
            provider=provider_name,
            model=model_name,
            cache_status="miss",
            source_record_ids=[r.record_id for r in records],
            source_records_hash=records_hash,
        )

        # 5. Persist to SQLite Summary Cache
        repository.save_summary_cache(
            cache_key=cache_key,
            patient_key=patient_key,
            records_hash=records_hash,
            provider=provider_name,
            model=model_name,
            prompt_version=self.prompt_version,
            summary_json=clinical_summary.model_dump_json(),
        )

        return clinical_summary


summarization_service = SummarizationService()
