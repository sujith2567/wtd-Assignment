"""
semantic_match.py
=================
Pydantic schemas for Hybrid Semantic Matching (Sentence-BERT) & Ablation study.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class SentenceAlignmentItem(BaseModel):
    """Semantic alignment pair between a JD requirement and a resume sentence."""
    jd_requirement: str
    best_matching_resume_sentence: str
    similarity_score: float


class CandidateSemanticMatchItem(BaseModel):
    """Candidate details with domain, semantic, hybrid scores & sentence alignments."""
    student_id: int
    user_id: int
    full_name: str
    email: str
    roll_number: str
    department: str
    cgpa: float
    active_backlogs: int
    skills: List[str]
    predicted_domain: Optional[str] = None
    domain_confidence: float
    semantic_score: float
    hybrid_score: float
    sentence_alignments: List[SentenceAlignmentItem] = []

    model_config = ConfigDict(from_attributes=True)


class SemanticMatchResults(BaseModel):
    """Response model for GET /api/v1/matching/semantic/{job_id}."""
    job_id: int
    job_title: str
    target_domain: str
    weight_domain: float = 0.6
    weight_semantic: float = 0.4
    total_candidates_evaluated: int
    candidates: List[CandidateSemanticMatchItem]


class AblationComparisonItem(BaseModel):
    """Candidate ranking across TF-IDF-only, SBERT-only, and Hybrid models."""
    student_id: int
    full_name: str
    roll_number: str
    department: str
    cgpa: float
    tfidf_score: float       # domain_confidence (from TF-IDF+LogReg)
    sbert_score: float       # SBERT document cosine similarity
    hybrid_score: float      # 0.6 * tfidf_score + 0.4 * sbert_score
    tfidf_rank: int
    sbert_rank: int
    hybrid_rank: int
    rank_delta_hybrid_vs_tfidf: int  # tfidf_rank - hybrid_rank (positive = promoted in hybrid)


class AblationResults(BaseModel):
    """Response model for GET /api/v1/matching/ablation/{job_id}."""
    job_id: int
    job_title: str
    target_domain: str
    total_candidates: int
    comparisons: List[AblationComparisonItem]
