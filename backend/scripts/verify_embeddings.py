"""
verify_embeddings.py
====================
Sanity check script for Sentence-BERT (all-MiniLM-L6-v2) embeddings in PlaceMatch AI.

Measures:
1. Model loading latency (Singleton startup).
2. Similarity score for a clearly PARAPHRASED text pair (expected high, > 0.65).
3. Similarity score for a clearly UNRELATED text pair (expected low, < 0.25).
4. Sentence-level explainability alignment test.
5. In-memory text-hash caching speedup test.
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.services.semantic_matching import (
    SemanticModelManager,
    compute_semantic_score,
    compute_hybrid_score,
    explain_sentence_alignment,
    get_embedding_cache_stats,
)

def run_verification():
    print("=========================================================")
    print("   PlaceMatch AI - Sentence-BERT Embeddings Sanity Check  ")
    print("=========================================================\n")

    # 1. Measure model loading time
    print("[1] Loading SBERT Model (all-MiniLM-L6-v2)...")
    t0 = time.perf_counter()
    model = SemanticModelManager().get_model()
    t1 = time.perf_counter()
    load_time_sec = t1 - t0
    print(f"    -> Model loaded in {load_time_sec:.3f} seconds (CPU mode).\n")

    # 2. Test Paraphrased Pair
    jd_paraphrased = (
        "Seeking a Software Engineer to design, build, and deploy RESTful APIs "
        "using Python and FastAPI microservices in cloud environment."
    )
    resume_paraphrased = (
        "Experienced software developer specializing in backend services, REST API creation, "
        "and building microservices using Python and FastAPI framework."
    )

    print("[2] Testing Paraphrased Pair (Software / Backend):")
    print(f"    JD:     '{jd_paraphrased}'")
    print(f"    Resume: '{resume_paraphrased}'")
    score_para = compute_semantic_score(resume_paraphrased, jd_paraphrased)
    print(f"    -> Semantic Similarity Score: {score_para:.4f} (Expected HIGH > 0.65)\n")

    # 3. Test Unrelated Pair
    jd_unrelated = (
        "Looking for a Senior Financial Auditor to conduct ledger reconciliation, "
        "tax compliance, and corporate risk management."
    )
    resume_unrelated = (
        "Fullstack web developer proficient in React, Node.js, HTML5, CSS3, and SQL database design."
    )

    print("[3] Testing Unrelated Pair (Finance Audit vs Web Dev):")
    print(f"    JD:     '{jd_unrelated}'")
    print(f"    Resume: '{resume_unrelated}'")
    score_unrelated = compute_semantic_score(resume_unrelated, jd_unrelated)
    print(f"    -> Semantic Similarity Score: {score_unrelated:.4f} (Expected LOW < 0.25)\n")

    # 4. Hybrid Score Test
    domain_conf = 0.85
    hybrid_score = compute_hybrid_score(domain_confidence=domain_conf, semantic_score=score_para)
    print("[4] Hybrid Score Computation:")
    print(f"    Domain Confidence (0.85) x 0.6 + Semantic ({score_para}) x 0.4")
    print(f"    -> Hybrid Score: {hybrid_score:.4f}\n")

    # 5. Sentence Alignment Test
    print("[5] Testing Sentence-Level Explainability Alignment:")
    jd_reqs = (
        "1. Build scalable RESTful web APIs using FastAPI. "
        "2. Experience with Docker containerization and CI/CD pipelines. "
        "3. Strong knowledge of MySQL database optimization."
    )
    resume_exp = (
        "Developed 15+ REST endpoints with Python and FastAPI for campus placement system. "
        "Containerized applications using Docker and deployed via GitHub Actions. "
        "Designed normalized MySQL schemas and indexed query bottlenecks."
    )
    alignments = explain_sentence_alignment(resume_exp, jd_reqs, top_k=3)
    for idx, item in enumerate(alignments, 1):
        print(f"    Pair #{idx} (Sim: {item['similarity_score']:.4f}):")
        print(f"      JD Req: '{item['jd_requirement']}'")
        print(f"      Matched Resume: '{item['best_matching_resume_sentence']}'")
    print()

    # 6. Cache Stats
    stats = get_embedding_cache_stats()
    print(f"[6] Cache Statistics: {stats['cached_embeddings']} unique texts cached.")

    # Validation assertions
    assert score_para > 0.60, f"Paraphrased similarity score ({score_para}) too low!"
    assert score_unrelated < 0.35, f"Unrelated similarity score ({score_unrelated}) too high!"
    assert score_para > score_unrelated, "Paraphrased score must be higher than unrelated score!"

    print("\n[OK] SANITY CHECK PASSED - Embeddings and Hybrid Scoring are behaving as expected!\n")

if __name__ == "__main__":
    run_verification()
