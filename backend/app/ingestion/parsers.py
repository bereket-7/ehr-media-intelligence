"""Parsers for JSON, CSV, and Plain Text clinical media inputs."""
import csv
import io
import json
import re
from typing import Any, Dict, List, Tuple


class ParseException(Exception):
    """Exception raised when file parsing fails."""
    def __init__(self, message: str, record_index: int = -1, code: str = "parse_error"):
        super().__init__(message)
        self.message = message
        self.record_index = record_index
        self.code = code


class JsonParser:
    """Parser for JSON clinical record datasets."""

    @staticmethod
    def parse(content: str, filename: str = "data.json") -> List[Tuple[int, Dict[str, Any]]]:
        """Parse JSON string into indexed dictionary records.

        Supports:
        - List of records: [{"patient_name": ...}, ...]
        - Dict with 'records' or 'patients' key: {"records": [...]}
        - Single record object: {"patient_name": ...}
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ParseException(f"Invalid JSON in {filename}: {exc.msg} at line {exc.lineno}", -1, "invalid_json") from exc

        raw_list: List[Dict[str, Any]] = []
        if isinstance(data, list):
            raw_list = data
        elif isinstance(data, dict):
            if "records" in data and isinstance(data["records"], list):
                raw_list = data["records"]
            elif "patients" in data and isinstance(data["patients"], list):
                raw_list = data["patients"]
            elif "data" in data and isinstance(data["data"], list):
                raw_list = data["data"]
            else:
                # Single record object
                raw_list = [data]
        else:
            raise ParseException(f"Expected JSON object or list in {filename}, got {type(data).__name__}", -1, "invalid_json_shape")

        records: List[Tuple[int, Dict[str, Any]]] = []
        for idx, item in enumerate(raw_list):
            if not isinstance(item, dict):
                raise ParseException(f"Record at index {idx} must be a JSON object", idx, "invalid_record_type")
            records.append((idx, item))

        return records


class CsvParser:
    """Parser for CSV clinical record files."""

    @staticmethod
    def parse(content: str, filename: str = "data.csv") -> List[Tuple[int, Dict[str, Any]]]:
        """Parse CSV string into indexed dictionary records.

        Automatically cleans headers and handles blank lines.
        """
        cleaned_content = content.lstrip("\ufeff")  # Strip UTF-8 BOM
        stream = io.StringIO(cleaned_content)

        # Detect delimiter if possible, default to comma
        sample = cleaned_content[:2048]
        delimiter = ","
        if sample:
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
                delimiter = dialect.delimiter
            except Exception:
                delimiter = ","

        reader = csv.DictReader(stream, delimiter=delimiter)
        if not reader.fieldnames:
            raise ParseException(f"CSV file {filename} is empty or missing headers", -1, "empty_csv")

        # Normalize field names (trim whitespace)
        fieldnames = [f.strip() if f else f"col_{i}" for i, f in enumerate(reader.fieldnames)]
        reader.fieldnames = fieldnames

        records: List[Tuple[int, Dict[str, Any]]] = []
        for row_idx, row in enumerate(reader):
            # Skip empty rows
            if not any(val and str(val).strip() for val in row.values()):
                continue
            records.append((row_idx, dict(row)))

        return records


class PlainTextParser:
    """Parser for plain-text clinical notes with documented format assumptions.

    Format Assumptions:
    1. Multiple records may be separated by '---', '===', or lines starting with 'RECORD'.
    2. Within a record, key-value metadata headers may precede narrative text:
       - PATIENT / NAME: <patient display name>
       - MRN: <medical record number>
       - DOB: <birth date>
       - GENDER: <gender>
       - DATE / RECORD_DATE: <date of record>
       - TYPE / CATEGORY: <imaging | lab | clinical_note | discharge_summary | pathology>
       - TITLE: <record headline or title>
       - CONTENT / TEXT / NOTE: <narrative body, or remainder of text block>
    """

    HEADER_PATTERN = re.compile(
        r"^(PATIENT|NAME|MRN|DOB|GENDER|DATE|RECORD_DATE|TYPE|CATEGORY|TITLE|ENCOUNTER_ID)\s*:\s*(.*)$",
        re.IGNORECASE,
    )
    SEPARATOR_PATTERN = re.compile(r"^(?:-{3,}|={3,}|RECORD\s*\d*)\r?$", re.MULTILINE)

    @classmethod
    def parse(cls, content: str, filename: str = "data.txt") -> List[Tuple[int, Dict[str, Any]]]:
        """Parse structured plain-text file into indexed dictionary records."""
        cleaned_content = content.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff").strip()
        if not cleaned_content:
            return []

        # Split into record chunks by delimiter
        chunks = cls.SEPARATOR_PATTERN.split(cleaned_content)
        chunks = [c.strip() for c in chunks if c.strip()]

        if not chunks:
            chunks = [cleaned_content]

        records: List[Tuple[int, Dict[str, Any]]] = []
        for idx, chunk in enumerate(chunks):
            record_dict = cls._parse_chunk(chunk, idx, filename)
            records.append((idx, record_dict))

        return records

    @classmethod
    def _parse_chunk(cls, chunk: str, index: int, filename: str) -> Dict[str, Any]:
        """Parse a single text chunk into headers and body."""
        lines = chunk.splitlines()
        data: Dict[str, Any] = {}
        body_lines: List[str] = []
        parsing_headers = True

        for line in lines:
            line_str = line.strip()
            if parsing_headers:
                match = cls.HEADER_PATTERN.match(line_str)
                if match:
                    key = match.group(1).upper()
                    val = match.group(2).strip()
                    if key in ("PATIENT", "NAME"):
                        data["patient_name"] = val
                    elif key == "MRN":
                        data["mrn"] = val
                    elif key == "DOB":
                        data["dob"] = val
                    elif key == "GENDER":
                        data["gender"] = val
                    elif key in ("DATE", "RECORD_DATE"):
                        data["record_date"] = val
                    elif key in ("TYPE", "CATEGORY"):
                        data["record_type"] = val
                    elif key == "TITLE":
                        data["title"] = val
                    elif key == "ENCOUNTER_ID":
                        data["encounter_id"] = val
                    continue
                elif line_str.upper().startswith(("CONTENT:", "TEXT:", "NOTE:")):
                    # Explicit transition to body
                    parsing_headers = False
                    prefix_len = line_str.index(":") + 1
                    initial_body = line_str[prefix_len:].strip()
                    if initial_body:
                        body_lines.append(initial_body)
                    continue
                elif line_str == "":
                    # Empty line can delimit headers from body
                    if data:
                        parsing_headers = False
                    continue
                else:
                    # Non-header line reached; switch to body
                    parsing_headers = False
                    body_lines.append(line)
            else:
                body_lines.append(line)

        text_content = "\n".join(body_lines).strip()
        data["text"] = text_content
        return data
