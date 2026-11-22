"""Abstract base interface for semantic embedding services."""
from abc import ABC, abstractmethod
from typing import List


class BaseEmbeddingService(ABC):
    """Abstract embedding service interface for clinical document and query vectorization."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector dimensionality of the generated embeddings."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Identifier of the embedding model."""
        pass

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Generate a normalized semantic vector for a single text string."""
        pass

    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate normalized semantic vectors for a batch of text strings."""
        pass
