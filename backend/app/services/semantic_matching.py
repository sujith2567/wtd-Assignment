"""
semantic_matching.py
====================
Hybrid Semantic Matching Service using Sentence-BERT (SBERT) for PlaceMatch AI.

Uses `all-MiniLM-L6-v2` model from `sentence-transformers`:
- Lightweight (80MB), fast, CPU-friendly (no GPU needed).
- Singleton pattern for lazy loading at application startup.
- In-memory text-hash caching for embedding vectors to avoid duplicate computations.
- Sentence-level semantic alignment between Job Description requirements and Student Resume sentences.
"""

from __future__ import annotations

import re
import hashlib
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from functools import lru_cache

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None


MODEL_NAME = "all-MiniLM-L6-v2"

# --------------------------------------------------------------------------- #
# Singleton Model Manager                                                      #
# --------------------------------------------------------------------------- #

class SemanticModelManager:
    _instance: Optional[SemanticModelManager] = None
    _model: Optional[Any] = None

    def __new__(cls) -> SemanticModelManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_model(self) -> Any:
        if self._model is None:
            if SentenceTransformer is None:
                raise ImportError(
                    "sentence-transformers is not installed. "
                    "Please run `pip install sentence-transformers`."
                )
            # Load model lazily
            self._model = SentenceTransformer(MODEL_NAME)
        return self._model


# Global in-memory cache for text embeddings: md5_hash -> np.ndarray
_EMBEDDING_CACHE: Dict[str, np.ndarray] = {}


def get_embedding_cache_stats() -> Dict[str, int]:
    """Return count of cached embeddings."""
    return {"cached_embeddings": len(_EMBEDDING_CACHE)}


def clear_embedding_cache() -> None:
    """Clear in-memory embedding cache."""
    _EMBEDDING_CACHE.clear()


# --------------------------------------------------------------------------- #
# Core Embedding & Cosine Similarity Functions                                 #
# --------------------------------------------------------------------------- #

def embed_text(text: str) -> np.ndarray:
    """
    Compute or retrieve SBERT embedding vector for input text.
    Uses MD5 text hash caching. Empty/whitespace text returns a zero vector.
    """
    clean_text = (text or "").strip()
    if not clean_text:
        return np.zeros(384, dtype=np.float32)

    text_hash = hashlib.md5(clean_text.encode("utf-8")).hexdigest()
    if text_hash in _EMBEDDING_CACHE:
        return _EMBEDDING_CACHE[text_hash]

    model = SemanticModelManager().get_model()
    # SentenceTransformer encode returns ndarray or tensor
    vec = model.encode(clean_text, convert_to_numpy=True, show_progress_bar=False)
    vec = vec.astype(np.float32)

    _EMBEDDING_CACHE[text_hash] = vec
    return vec


def embed_batch(texts: List[str]) -> List[np.ndarray]:
    """
    Batch embed multiple texts utilizing cache where possible.
    """
    results: List[Optional[np.ndarray]] = [None] * len(texts)
    uncached_indices: List[int] = []
    uncached_texts: List[str] = []

    for i, t in enumerate(texts):
        clean_t = (t or "").strip()
        if not clean_t:
            results[i] = np.zeros(384, dtype=np.float32)
            continue
        h = hashlib.md5(clean_t.encode("utf-8")).hexdigest()
        if h in _EMBEDDING_CACHE:
            results[i] = _EMBEDDING_CACHE[h]
        else:
            uncached_indices.append(i)
            uncached_texts.append(clean_t)

    if uncached_texts:
        model = SemanticModelManager().get_model()
        vectors = model.encode(uncached_texts, convert_to_numpy=True, show_progress_bar=False)
        for idx, clean_t, vec in zip(uncached_indices, uncached_texts, vectors):
            vec_f32 = vec.astype(np.float32)
            h = hashlib.md5(clean_t.encode("utf-8")).hexdigest()
            _EMBEDDING_CACHE[h] = vec_f32
            results[idx] = vec_f32

    return [r if r is not None else np.zeros(384, dtype=np.float32) for r in results]


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """
    Compute cosine similarity between two embedding vectors.
    Returns float in range [0.0, 1.0].
    """
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    sim = float(np.dot(vec_a, vec_b) / (norm_a * norm_b))
    # Clip to valid probability/similarity range [0.0, 1.0]
    sim = max(0.0, min(1.0, sim))
    return round(sim, 4)


def compute_semantic_score(resume_text: str, job_description: str) -> float:
    """
    Embed both resume text and job description and return their cosine similarity score (0.0 to 1.0).
    """
    if not resume_text or not job_description:
        return 0.0

    vec_resume = embed_text(resume_text)
    vec_job = embed_text(job_description)
    return cosine_similarity(vec_resume, vec_job)


def compute_hybrid_score(
    domain_confidence: float,
    semantic_score: float,
    weight_domain: float = 0.6,
    weight_semantic: float = 0.4,
) -> float:
    """
    Compute weighted hybrid score combining domain classifier confidence and SBERT semantic match score.

    Hybrid Score = (weight_domain * domain_confidence) + (weight_semantic * semantic_score)
    Default weights: 0.6 domain_confidence + 0.4 semantic_score.
    """
    w_domain = float(weight_domain)
    w_sem = float(weight_semantic)
    total_w = w_domain + w_sem
    if total_w > 0:
        w_domain /= total_w
        w_sem /= total_w

    score = (w_domain * float(domain_confidence)) + (w_sem * float(semantic_score))
    return round(max(0.0, min(1.0, score)), 4)


# --------------------------------------------------------------------------- #
# Sentence-Level Explainability Alignment                                      #
# --------------------------------------------------------------------------- #

def _split_into_sentences(text: str) -> List[str]:
    """
    Split document text into clean, non-trivial sentences.
    """
    if not text:
        return []
    # Split by newline or sentence punctuation
    raw_sentences = re.split(r"(?<=[.!?\n])\s+", text)
    cleaned = []
    for s in raw_sentences:
        clean = re.sub(r"\s+", " ", s).strip("-•* \t\r\n")
        # Filter out very short non-informative lines (e.g. single words or numbers)
        if len(clean) >= 10 and any(c.isalpha() for c in clean):
            cleaned.append(clean)
    return cleaned


def explain_sentence_alignment(
    resume_text: str,
    job_description: str,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """
    Perform sentence-level semantic alignment between JD requirements and resume text.

    1. Splits job description and resume into sentences.
    2. For each JD sentence, finds the resume sentence with highest cosine similarity.
    3. Sorts alignment pairs by similarity score descending and returns top_k alignments.

    Returns:
        List of dicts: [
            {
                "jd_requirement": str,
                "best_matching_resume_sentence": str,
                "similarity_score": float
            },
            ...
        ]
    """
    jd_sentences = _split_into_sentences(job_description)
    resume_sentences = _split_into_sentences(resume_text)

    if not jd_sentences or not resume_sentences:
        return []

    # Batch embed sentences
    jd_vecs = embed_batch(jd_sentences)
    res_vecs = embed_batch(resume_sentences)

    alignments: List[Tuple[float, str, str]] = []

    for jd_sent, jd_v in zip(jd_sentences, jd_vecs):
        best_sim = -1.0
        best_res_sent = ""
        for res_sent, res_v in zip(resume_sentences, res_vecs):
            sim = cosine_similarity(jd_v, res_v)
            if sim > best_sim:
                best_sim = sim
                best_res_sent = res_sent

        if best_sim > 0 and best_res_sent:
            alignments.append((best_sim, jd_sent, best_res_sent))

    # Sort alignments by highest similarity first
    alignments.sort(key=lambda x: x[0], reverse=True)

    results = []
    seen_jd = set()
    for sim, jd_sent, res_sent in alignments:
        if jd_sent in seen_jd:
            continue
        seen_jd.add(jd_sent)
        results.append({
            "jd_requirement": jd_sent,
            "best_matching_resume_sentence": res_sent,
            "similarity_score": sim,
        })
        if len(results) >= top_k:
            break

    return results
