"""Semantic search and vector indexing service integrating embeddings and persistent storage."""
import time
from typing import Any, Dict, List, Optional
from app.core.logging import get_logger
from app.models.canonical import IdentityStatus, MediaRecord, RecordType
from app.models.search import (
    SearchFilters,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)
from app.repositories.sqlite_repository import repository
from app.services.embedding import get_embedding_service
from app.services.embedding.base import BaseEmbeddingService
from app.services.vector_store import get_vector_store
from app.services.vector_store.base import BaseVectorStore

logger = get_logger(__name__)


class SearchService:
    """Orchestrates document vectorization, persistent indexing, and semantic search queries."""

    def __init__(
        self,
        embedding_service: Optional[BaseEmbeddingService] = None,
        vector_store: Optional[BaseVectorStore] = None,
    ) -> None:
        self.embedding_service = embedding_service or get_embedding_service()
        self.vector_store = vector_store or get_vector_store()
        self.repo = repository

    @staticmethod
    def _create_embedding_text(record: MediaRecord) -> str:
        """Construct normalized, meaningful text representation for semantic vectorization."""
        date_str = record.record_date or "Undated"
        type_str = record.record_type.value.capitalize()
        return (
            f"Patient: {record.patient_name} | "
            f"Type: {type_str} | "
            f"Title: {record.title} | "
            f"Date: {date_str} | "
            f"Clinical Findings: {record.text}"
        )

    @staticmethod
    def _create_excerpt(text: str, max_length: int = 180) -> str:
        """Extract a faithful excerpt directly from source text without inventing content."""
        if not text:
            return ""
        clean = " ".join(text.split())
        if len(clean) <= max_length:
            return clean
        truncated = clean[:max_length]
        # Truncate at last space if feasible
        last_space = truncated.rfind(" ")
        if last_space > 100:
            truncated = truncated[:last_space]
        return f"{truncated}..."

    @staticmethod
    def _derive_resource_type(record: MediaRecord) -> str:
        """Determine corresponding FHIR resource type."""
        if record.record_type == RecordType.LAB:
            return "DiagnosticReport"
        return "DocumentReference"

    def index_records(self, records: List[MediaRecord]) -> int:
        """Index eligible persisted clinical records into the vector database.

        Excludes quarantined identity-conflict records to prevent contamination.
        """
        eligible = [
            r for r in records
            if r.identity_status != IdentityStatus.CONFLICT_QUARANTINED and r.text and r.text.strip()
        ]
        if not eligible:
            return 0

        ids: List[str] = []
        texts_to_embed: List[str] = []
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for rec in eligible:
            vec_id = f"doc_{rec.record_id}"
            res_type = self._derive_resource_type(rec)
            embed_text = self._create_embedding_text(rec)

            ids.append(vec_id)
            texts_to_embed.append(embed_text)
            documents.append(rec.text)
            metadatas.append({
                "record_id": rec.record_id,
                "patient_id": rec.patient_key,
                "mrn_normalized": rec.mrn_normalized,
                "patient_name": rec.patient_name,
                "title": rec.title,
                "record_type": rec.record_type.value,
                "resource_type": res_type,
                "record_date": rec.record_date or "",
                "source_reference": f"{rec.source_file}#{rec.source_index}",
                "fhir_resource_id": f"{res_type.lower()}_{rec.record_id}",
                "is_synthetic": True,
            })

        try:
            embeddings = self.embedding_service.embed_texts(texts_to_embed)
            self.vector_store.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )
            logger.info("Successfully indexed %d clinical records into vector store.", len(eligible))
            return len(eligible)
        except Exception as exc:
            logger.error("Failed to index clinical records into vector store: %s", exc)
            # Fail gracefully without disrupting caller transactions
            return 0

    def index_record(self, record: MediaRecord) -> bool:
        """Index a single clinical record."""
        return self.index_records([record]) == 1

    def search(self, request: SearchRequest) -> SearchResponse:
        """Execute a natural-language semantic query with optional metadata filters."""
        start_time = time.perf_counter()

        query_str = request.query.strip()
        top_k = min(request.top_k, 20)

        # 1. Embed Query
        query_vector = self.embedding_service.embed_text(query_str)

        # 2. Prepare Filters
        filter_dict: Dict[str, Any] = {}
        if request.filters:
            if request.filters.resource_type:
                filter_dict["resource_type"] = request.filters.resource_type
            if request.filters.date_from:
                filter_dict["date_from"] = request.filters.date_from
            if request.filters.date_to:
                filter_dict["date_to"] = request.filters.date_to
            if request.filters.patient_id:
                filter_dict["patient_id"] = request.filters.patient_id

        # 3. Query Vector Store
        query_result = self.vector_store.query(
            query_embedding=query_vector,
            top_k=top_k,
            filters=filter_dict,
        )

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # 4. Assemble SearchResultItem instances
        items: List[SearchResultItem] = []
        for idx in range(len(query_result.ids)):
            meta = query_result.metadatas[idx] if idx < len(query_result.metadatas) else {}
            doc_text = query_result.documents[idx] if idx < len(query_result.documents) else ""
            sim = query_result.similarities[idx] if idx < len(query_result.similarities) else 0.0
            dist = query_result.distances[idx] if idx < len(query_result.distances) else 1.0

            excerpt = self._create_excerpt(doc_text)

            items.append(
                SearchResultItem(
                    rank=idx + 1,
                    record_id=meta.get("record_id", query_result.ids[idx]),
                    patient_id=meta.get("patient_id", "Unknown"),
                    title=meta.get("title", "Clinical Record"),
                    record_type=meta.get("record_type", "note"),
                    resource_type=meta.get("resource_type", "DocumentReference"),
                    record_date=meta.get("record_date") or None,
                    excerpt=excerpt,
                    similarity_score=sim,
                    distance=dist,
                    source_reference=meta.get("source_reference"),
                    fhir_resource_id=meta.get("fhir_resource_id"),
                )
            )

        return SearchResponse(
            query=query_str,
            total_results=len(items),
            results=items,
            search_latency_ms=latency_ms,
        )

    def reindex_all_persisted_records(self) -> int:
        """Re-index all persisted records from SQLite into vector storage."""
        all_records = self.repo.list_media_records()
        if not all_records:
            return 0
        return self.index_records(all_records)

    def get_index_stats(self) -> Dict[str, Any]:
        """Return diagnostic metrics regarding vector indexing state."""
        return {
            "total_vectors": self.vector_store.count(),
            "embedding_model": self.embedding_service.model_name,
            "embedding_dimension": self.embedding_service.dimension,
            "vector_store_type": type(self.vector_store).__name__,
        }


# Global shared search service instance
search_service = SearchService()
