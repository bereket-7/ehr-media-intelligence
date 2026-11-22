"""Embedding service package and factory."""
from typing import Optional
from app.core.config import settings
from app.services.embedding.base import BaseEmbeddingService
from app.services.embedding.deterministic_service import DeterministicClinicalEmbeddingService
from app.services.embedding.sentence_transformers_service import SentenceTransformersEmbeddingService

_default_embedding_service: Optional[BaseEmbeddingService] = None


def get_embedding_service(force_deterministic: bool = False) -> BaseEmbeddingService:
    """Return the configured embedding service instance (cached singleton)."""
    global _default_embedding_service
    if force_deterministic:
        return DeterministicClinicalEmbeddingService()

    if _default_embedding_service is None:
        # Check if sentence-transformers can be imported and initialized
        try:
            import sentence_transformers  # noqa: F401
            _default_embedding_service = SentenceTransformersEmbeddingService(
                model_name=settings.EMBEDDING_MODEL_NAME
            )
        except Exception:
            # Fall back safely to DeterministicClinicalEmbeddingService
            _default_embedding_service = DeterministicClinicalEmbeddingService()

    return _default_embedding_service


__all__ = [
    "BaseEmbeddingService",
    "DeterministicClinicalEmbeddingService",
    "SentenceTransformersEmbeddingService",
    "get_embedding_service",
]
