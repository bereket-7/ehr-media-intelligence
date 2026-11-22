"""Sentence-Transformers embedding service implementation using all-MiniLM-L6-v2."""
from typing import List, Optional
from app.core.config import settings
from app.core.logging import get_logger
from app.services.embedding.base import BaseEmbeddingService

logger = get_logger(__name__)


class SentenceTransformersEmbeddingService(BaseEmbeddingService):
    """Generates dense vector embeddings using sentence-transformers (all-MiniLM-L6-v2)."""

    def __init__(self, model_name: Optional[str] = None, device: str = "cpu") -> None:
        self._model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self._device = device
        self._model = None  # Lazy-loaded on first embedding request
        self._dimension = 384

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def _get_model(self):
        """Lazy load the sentence-transformer model to avoid startup overhead."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info("Loading sentence-transformers model '%s' on %s...", self._model_name, self._device)
                self._model = SentenceTransformer(self._model_name, device=self._device)
            except Exception as exc:
                logger.error("Failed to load SentenceTransformer model '%s': %s", self._model_name, exc)
                raise RuntimeError(f"Embedding model '{self._model_name}' could not be loaded: {exc}") from exc
        return self._model

    def embed_text(self, text: str) -> List[float]:
        """Generate a 384-dimensional unit embedding for a single text."""
        if not text or not text.strip():
            # Return zero vector for empty or unusable text
            return [0.0] * self._dimension

        model = self._get_model()
        vector = model.encode(text.strip(), normalize_embeddings=True)
        return vector.tolist()

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate 384-dimensional unit embeddings for a batch of texts."""
        if not texts:
            return []

        cleaned_texts = [t.strip() if t and t.strip() else "" for t in texts]
        non_empty = [t for t in cleaned_texts if t]

        if not non_empty:
            return [[0.0] * self._dimension for _ in texts]

        model = self._get_model()
        vectors = model.encode(cleaned_texts, batch_size=32, normalize_embeddings=True)
        return [v.tolist() for v in vectors]
