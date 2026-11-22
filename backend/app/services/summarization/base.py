"""Abstract base interface for summarization providers."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from app.models.canonical import MediaRecord


class ProviderError(Exception):
    """Exception raised when an LLM provider request fails."""
    def __init__(self, message: str, code: str = "provider_error", status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class BaseSummarizationProvider(ABC):
    """Abstract summarization provider contract."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the provider service."""
        pass

    @property
    @abstractmethod
    def model(self) -> str:
        """Model identifier."""
        pass

    @abstractmethod
    async def summarize(
        self,
        patient_info: Dict[str, Any],
        records: List[MediaRecord],
    ) -> Dict[str, Any]:
        """Generate a structured summary from patient records.

        Must return a dictionary corresponding to ClinicalSummary fields or raise ProviderError.
        """
        pass
