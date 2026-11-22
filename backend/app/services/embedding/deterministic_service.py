"""Deterministic clinical embedding service for offline, reproducible semantic search."""
import hashlib
import math
import re
from typing import Dict, List, Set
from app.services.embedding.base import BaseEmbeddingService

# Semantic clinical clusters mapping related terminology to dedicated feature dimensions
CLINICAL_CLUSTERS: Dict[str, Set[str]] = {
    "endocrine_glucose": {
        "blood sugar", "glucose", "hba1c", "a1c", "diabetes", "diabetic", "glycemic",
        "hyperglycemia", "hypoglycemia", "insulin", "metformin", "fasting glucose"
    },
    "neurology_brain": {
        "brain", "mri brain", "mri", "head", "neuro", "neurology", "ct head", "stroke",
        "cerebral", "intracranial", "seizure", "infarct", "neurological", "temporal"
    },
    "pulmonary_lung": {
        "lung", "lungs", "pulmonary", "respiratory", "pneumonia", "cough", "chest x-ray",
        "radiograph", "consolidation", "infiltrate", "dyspnea", "wheezing", "sputum", "bronchial"
    },
    "nephrology_kidney": {
        "kidney", "renal", "pyelonephritis", "creatinine", "bun", "urinary", "uti",
        "flank pain", "glomerular", "nephrology", "costovertebral", "dysuria"
    },
    "cardiovascular_heart": {
        "cardiac", "heart", "coronary", "troponin", "ecg", "ekg", "hypertension",
        "angina", "myocardial", "arrhythmia", "cardiovascular", "edema"
    },
    "hematology_infection": {
        "infection", "leukocytosis", "wbc", "white blood cell", "fever", "septic",
        "sepsis", "bacteremia", "neutrophils", "platelets", "cbc"
    },
    "gastroenterology_liver": {
        "liver", "hepatic", "cirrhosis", "alt", "ast", "bilirubin", "abdominal",
        "hepatitis", "jaundice", "gallbladder"
    },
}


class DeterministicClinicalEmbeddingService(BaseEmbeddingService):
    """Generates deterministic 384-dimensional normalized vectors grounded in clinical semantic clusters.

    Operates completely offline with zero network calls, sub-millisecond execution,
    and semantic clustering for clinical synonyms.
    """

    def __init__(self, model_name: str = "deterministic-clinical-v1") -> None:
        self._model_name = model_name
        self._dimension = 384

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_text(self, text: str) -> List[float]:
        """Generate a 384-dimensional unit vector for a given text."""
        if not text or not text.strip():
            return [0.0] * self._dimension

        raw_lower = text.lower()
        # Clean punctuation for tokenization
        tokens = re.findall(r"\b[a-z0-9_-]+\b", raw_lower)
        if not tokens:
            return [0.0] * self._dimension

        vec = [0.0] * self._dimension

        # 1. Project Clinical Clusters into Dedicated Vector Subspaces
        # 7 clusters assigned to 24 dimensions each = 168 dimensions
        cluster_names = list(CLINICAL_CLUSTERS.keys())
        for c_idx, c_name in enumerate(cluster_names):
            cluster_terms = CLINICAL_CLUSTERS[c_name]
            cluster_score = 0.0
            for term in cluster_terms:
                if " " in term:
                    if term in raw_lower:
                        cluster_score += 2.5
                elif term in tokens:
                    cluster_score += 1.5

            if cluster_score > 0:
                start_dim = c_idx * 24
                for d in range(24):
                    # Deterministic spread across the cluster subspace
                    weight = math.sin((d + 1) * 1.618) * cluster_score
                    vec[start_dim + d] += weight

        # 2. General Token & Bigram Hashing for Remaining Vector Subspaces (dims 168..383)
        hash_subspace_start = len(cluster_names) * 24  # 168
        hash_subspace_size = self._dimension - hash_subspace_start  # 216 dims

        # Unigrams
        for token in tokens:
            thash = int(hashlib.md5(token.encode("utf-8")).hexdigest()[:8], 16)
            idx = hash_subspace_start + (thash % hash_subspace_size)
            sign = 1.0 if (thash & 1) == 0 else -1.0
            vec[idx] += sign * 1.0

        # Bigrams for local phrase structure
        for i in range(len(tokens) - 1):
            bigram = f"{tokens[i]}_{tokens[i+1]}"
            bhash = int(hashlib.sha256(bigram.encode("utf-8")).hexdigest()[:8], 16)
            idx = hash_subspace_start + (bhash % hash_subspace_size)
            sign = 1.0 if (bhash & 1) == 0 else -1.0
            vec[idx] += sign * 1.5

        # 3. L2 Unit Normalization (so cosine_sim(u, v) == dot_product(u, v))
        norm = math.sqrt(sum(x * x for x in vec))
        if norm < 1e-9:
            return [0.0] * self._dimension

        return [round(x / norm, 6) for x in vec]

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate 384-dimensional unit vectors for a list of texts."""
        return [self.embed_text(t) for t in texts]
