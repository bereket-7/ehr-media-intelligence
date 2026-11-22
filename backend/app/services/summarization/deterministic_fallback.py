"""Deterministic offline fallback summarizer requiring no API keys or external models."""
import re
from typing import Any, Dict, List
from app.models.canonical import MediaRecord
from app.models.summary import RecentRecordSummary


class DeterministicFallbackSummarizer:
    """Rule-based clinical summarizer producing predictable, grounded summaries."""

    @classmethod
    def generate(
        cls,
        patient_info: Dict[str, Any],
        records: List[MediaRecord],
    ) -> Dict[str, Any]:
        """Generate structured summary from records deterministically."""
        patient_id = patient_info.get("patient_key", "unknown")
        patient_name = patient_info.get("display_name", "Unknown Patient")
        mrn = patient_info.get("mrn_normalized")

        if not records:
            narrative = f"No clinical media records are currently indexed for patient {patient_name}."
            return {
                "chief_concern": "Not stated in source records",
                "key_diagnoses": [],
                "recent_records": [],
                "key_findings": [],
                "flagged_anomalies": [],
                "data_quality_issues": ["Patient has zero indexed clinical media records in the platform."],
                "narrative_summary": narrative,
                "confidence_or_limitations": "No source records available to establish clinical context or diagnoses.",
            }

        # 1. Chief Concern Extraction
        chief_concern = "Not stated in source records"
        for rec in records:
            match = re.search(r"(?:CLINICAL INDICATION|CHIEF COMPLAINT|SUBJECTIVE|HISTORY|ADMISSION):\s*([^\n\.]+)", rec.text, re.IGNORECASE)
            if match:
                chief_concern = match.group(1).strip()
                break
        if chief_concern == "Not stated in source records" and records:
            chief_concern = f"Evaluation regarding {records[0].title.lower()}"

        # 2. Key Diagnoses Extraction
        key_diagnoses: List[str] = []
        diag_seen = set()
        for rec in records:
            matches = re.findall(r"(?:IMPRESSION|ASSESSMENT|DIAGNOSIS):\s*([^\n]+)", rec.text, re.IGNORECASE)
            for m in matches:
                clean_diag = m.strip().rstrip(".")
                # Filter out boilerplates
                if len(clean_diag) > 3 and clean_diag.lower() not in diag_seen:
                    diag_seen.add(clean_diag.lower())
                    key_diagnoses.append(clean_diag)

        # 3. Recent Records Extraction
        # Sort by record_date descending
        sorted_records = sorted(
            records,
            key=lambda r: (r.record_date or "0000-00-00", r.source_index),
            reverse=True,
        )

        recent_records: List[Dict[str, Any]] = []
        for r in sorted_records[:5]:
            # Extract first sentence as brief finding
            first_sentence = r.text.split("\n")[0].split(".")[0].strip()
            if len(first_sentence) > 120:
                first_sentence = first_sentence[:117] + "..."
            recent_records.append({
                "record_id": r.record_id,
                "record_type": r.record_type.value,
                "title": r.title,
                "record_date": r.record_date,
                "brief_finding": first_sentence or r.title,
            })

        # 4. Key Findings
        key_findings: List[str] = []
        finding_seen = set()
        for rec in sorted_records:
            matches = re.findall(r"(?:FINDINGS|FINDINGS:|HISTOPATHOLOGIC EVALUATION):\s*([^\n\.]+)", rec.text, re.IGNORECASE)
            for m in matches:
                cleaned = m.strip()
                if len(cleaned) > 5 and cleaned.lower() not in finding_seen:
                    finding_seen.add(cleaned.lower())
                    key_findings.append(cleaned)
        if not key_findings:
            key_findings = [r["brief_finding"] for r in recent_records[:3]]

        # 5. Flagged Anomalies
        flagged_anomalies: List[str] = []
        anomaly_seen = set()
        for rec in records:
            # Match explicit abnormal tags or clinical anomaly keywords
            lines = rec.text.splitlines()
            for line in lines:
                if any(tag in line for tag in ("[High", "[Low", "[Abnormal", "[Borderline High", "leukocytosis", "pneumonia", "ischemia", "diverticulitis", "dysplasia")):
                    clean_line = line.strip().lstrip("-").strip()
                    if clean_line.lower() not in anomaly_seen and len(clean_line) < 180:
                        anomaly_seen.add(clean_line.lower())
                        flagged_anomalies.append(clean_line)

        # 6. Data Quality Issues
        data_quality_issues: List[str] = []
        if not patient_info.get("dob"):
            data_quality_issues.append("Patient date of birth is absent from demographics.")
        if any(not r.record_date for r in records):
            data_quality_issues.append("One or more records lack an explicit document date.")
        if any(r.mrn_normalized and r.mrn_normalized.startswith("SYN-MISSING-") for r in records):
            data_quality_issues.append("Patient lacked a hospital MRN; operating under an internal synthetic identifier.")

        # 7. Narrative Summary (< 200 words)
        type_counts: Dict[str, int] = {}
        for r in records:
            type_counts[r.record_type.value] = type_counts.get(r.record_type.value, 0) + 1
        breakdown = ", ".join(f"{cnt} {t.replace('_', ' ')}" for t, cnt in type_counts.items())

        diagnoses_phrase = f" Key documented findings include {'; '.join(key_diagnoses[:3])}." if key_diagnoses else ""
        anomaly_phrase = f" Noted laboratory/imaging abnormalities include: {'; '.join(flagged_anomalies[:2])}." if flagged_anomalies else " No severe acute anomalies flagged in source records."

        narrative = (
            f"Patient {patient_name} has {len(records)} documented clinical media records ({breakdown}). "
            f"Primary clinical context: {chief_concern}.{diagnoses_phrase}{anomaly_phrase} "
            f"This summary was deterministically compiled from source records."
        )

        words = narrative.split()
        if len(words) > 190:
            narrative = " ".join(words[:185]) + "... [Deterministic summary constrained to word limit]"

        return {
            "chief_concern": chief_concern,
            "key_diagnoses": key_diagnoses[:5],
            "recent_records": recent_records,
            "key_findings": key_findings[:5],
            "flagged_anomalies": flagged_anomalies[:5],
            "data_quality_issues": data_quality_issues,
            "narrative_summary": narrative,
            "confidence_or_limitations": (
                "Deterministic summary extracted directly from source record text without clinical inference. "
                "Consult original documents for full clinical detail."
            ),
        }
