"""
test_semantic_matching.py
=========================
Pytest test suite for Sentence-BERT Semantic Matching module in PlaceMatch AI.

Tests cover:
1. compute_semantic_score (paraphrased vs unrelated pairs, empty text edge cases).
2. compute_hybrid_score (weighted score formulas, custom weights, bounds).
3. explain_sentence_alignment (sentence splitting, top K matching, structure).
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.services.semantic_matching import (
    compute_semantic_score,
    compute_hybrid_score,
    explain_sentence_alignment,
    cosine_similarity,
    embed_text,
)


class TestSemanticMatching:

    def test_compute_semantic_score_paraphrased_vs_unrelated(self):
        """
        Verify that paraphrased resume/JD pairs score significantly higher
        than completely unrelated pairs.
        """
        jd_tech = (
            "Looking for a Backend Developer skilled in Python, FastAPI, and Docker "
            "to build microservices and REST APIs."
        )
        resume_tech = (
            "Software engineer with experience building web applications using Python, "
            "FastAPI framework, and Docker containerization."
        )
        resume_unrelated = (
            "Senior Accountant with 5+ years experience in tax auditing, ledger management, "
            "and financial risk compliance."
        )

        score_tech = compute_semantic_score(resume_tech, jd_tech)
        score_unrelated = compute_semantic_score(resume_unrelated, jd_tech)

        assert score_tech > 0.60, f"Expected high similarity for tech pair, got {score_tech}"
        assert score_unrelated < 0.35, f"Expected low similarity for unrelated pair, got {score_unrelated}"
        assert score_tech > score_unrelated + 0.30, "Tech match score must be much higher than unrelated score"

    def test_compute_semantic_score_empty_input(self):
        """Empty or blank inputs should return 0.0 similarity."""
        assert compute_semantic_score("", "Job description text") == 0.0
        assert compute_semantic_score("Resume text", "") == 0.0
        assert compute_semantic_score("", "") == 0.0

    def test_compute_hybrid_score(self):
        """
        Test hybrid score calculation under various domain confidence and semantic scores.
        Formula: 0.6 * domain_conf + 0.4 * semantic_score
        """
        # Case 1: domain=0.80, semantic=0.70 => 0.6*0.8 + 0.4*0.7 = 0.48 + 0.28 = 0.76
        score1 = compute_hybrid_score(0.80, 0.70, weight_domain=0.6, weight_semantic=0.4)
        assert abs(score1 - 0.76) < 1e-4

        # Case 2: Custom equal weights 0.5 / 0.5
        score2 = compute_hybrid_score(0.90, 0.50, weight_domain=0.5, weight_semantic=0.5)
        assert abs(score2 - 0.70) < 1e-4

        # Case 3: Bounds test (0.0 to 1.0)
        assert compute_hybrid_score(0.0, 0.0) == 0.0
        assert compute_hybrid_score(1.0, 1.0) == 1.0

    def test_explain_sentence_alignment(self):
        """
        Test sentence-level semantic alignment explainability function.
        """
        jd_text = (
            "Requirement 1: Develop backend REST APIs with FastAPI. "
            "Requirement 2: Manage relational database design using MySQL. "
            "Requirement 3: Implement automated CI/CD deployment pipelines."
        )
        resume_text = (
            "Built 20+ REST API endpoints using Python and FastAPI framework. "
            "Designed complex MySQL database schemas with indexing and query tuning. "
            "Configured GitHub Actions for continuous integration and automated deployment."
        )

        alignments = explain_sentence_alignment(resume_text, jd_text, top_k=3)

        assert len(alignments) > 0
        assert len(alignments) <= 3

        for item in alignments:
            assert "jd_requirement" in item
            assert "best_matching_resume_sentence" in item
            assert "similarity_score" in item
            assert 0.0 <= item["similarity_score"] <= 1.0
            assert len(item["jd_requirement"]) > 0
            assert len(item["best_matching_resume_sentence"]) > 0

        # Verify that FastAPI requirement aligns with FastAPI resume sentence
        fastapi_item = next((item for item in alignments if "FastAPI" in item["jd_requirement"]), None)
        assert fastapi_item is not None
        assert "FastAPI" in fastapi_item["best_matching_resume_sentence"]
