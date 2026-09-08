"""
ablation_study.py
=================
Ablation study script for PlaceMatch AI IEEE paper report.

Evaluates candidates for a specified job using three ranking paradigms side-by-side:
1. TF-IDF + Logistic Regression Domain Classifier (Baseline)
2. Sentence-BERT (SBERT) Cosine Similarity (Semantic Only)
3. Hybrid Model (0.6 TF-IDF + 0.4 SBERT)

Outputs a formatted ASCII comparison table and optional JSON / CSV report.
"""

import sys
import os
import argparse
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.core.database import SessionLocal
from backend.app.models.job import JobPosting
from backend.app.models.student import Student
from backend.app.services.semantic_matching import (
    compute_semantic_score,
    compute_hybrid_score,
)
from backend.app.services.classifier_service import get_classifier_service


def run_ablation(job_id: int, top_n: int = 15):
    db = SessionLocal()
    try:
        job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
        if not job:
            print(f"[ERROR] Job ID {job_id} not found in database.")
            return

        students = db.query(Student).join(Student.user).all()
        if not students:
            print("[ERROR] No students found in database.")
            return

        target_domain = job.target_domain
        job_desc = job.description or f"{job.title} in {job.target_domain}. Skills: {', '.join(job.required_skills or [])}"

        print(f"\n==========================================================================")
        print(f"  PlaceMatch AI - Ablation Study Report for Job #{job.id}: {job.title}")
        print(f"  Target Domain: {target_domain} | Total Candidates: {len(students)}")
        print(f"==========================================================================\n")

        records = []
        classifier_service = get_classifier_service()

        for s in students:
            resume_text = s.raw_resume_text or ""
            skills = s.skills or []
            projects = s.projects or []

            # TF-IDF Domain Classifier Score
            if s.predicted_domain == target_domain and s.domain_confidence is not None:
                tfidf_score = float(s.domain_confidence)
            else:
                try:
                    res = classifier_service.predict_and_explain(resume_text, skills, projects)
                    tfidf_score = float(res["class_probabilities"].get(target_domain, 0.0))
                except Exception:
                    tfidf_score = 0.0

            # SBERT Semantic Score
            sbert_score = compute_semantic_score(resume_text, job_desc)

            # Hybrid Score
            hybrid_score = compute_hybrid_score(tfidf_score, sbert_score, 0.6, 0.4)

            records.append({
                "student_id": s.id,
                "full_name": s.full_name,
                "roll_number": s.roll_number,
                "cgpa": float(s.cgpa),
                "tfidf_score": round(tfidf_score, 4),
                "sbert_score": round(sbert_score, 4),
                "hybrid_score": round(hybrid_score, 4),
            })

        # Rank candidates under each strategy
        records.sort(key=lambda r: (r["tfidf_score"], r["cgpa"]), reverse=True)
        for rank, r in enumerate(records, start=1):
            r["tfidf_rank"] = rank

        records.sort(key=lambda r: (r["sbert_score"], r["cgpa"]), reverse=True)
        for rank, r in enumerate(records, start=1):
            r["sbert_rank"] = rank

        records.sort(key=lambda r: (r["hybrid_score"], r["cgpa"]), reverse=True)
        for rank, r in enumerate(records, start=1):
            r["hybrid_rank"] = rank

        # Display Top N Hybrid candidates side-by-side
        print(f"{'Hybrid Rank':<12} | {'Roll No':<10} | {'Name':<22} | {'TF-IDF (Rank)':<16} | {'SBERT (Rank)':<16} | {'Hybrid Score':<12} | {'Rank Delta'}")
        print("-" * 110)

        for r in records[:top_n]:
            delta = r["tfidf_rank"] - r["hybrid_rank"]
            delta_str = f"+{delta} (promoted)" if delta > 0 else f"{delta}" if delta < 0 else "0 (unchanged)"
            print(
                f"#{r['hybrid_rank']:<11} | "
                f"{r['roll_number']:<10} | "
                f"{r['full_name'][:22]:<22} | "
                f"{r['tfidf_score']:.4f} (#{r['tfidf_rank']:<2}) | "
                f"{r['sbert_score']:.4f} (#{r['sbert_rank']:<2}) | "
                f"{r['hybrid_score']:.4f}       | "
                f"{delta_str}"
            )

        print("-" * 110)
        print(f"\n[SUMMARY] Evaluated {len(students)} candidates.")
        print(f"Top candidate under Hybrid model: {records[0]['full_name']} ({records[0]['roll_number']})")
        print("Ablation study evaluation completed successfully.\n")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run PlaceMatch AI Ablation Study")
    parser.add_argument("--job-id", type=int, default=1, help="Job posting ID to analyze (default: 1)")
    parser.add_argument("--top-n", type=int, default=15, help="Number of top candidates to display (default: 15)")
    args = parser.parse_args()

    run_ablation(job_id=args.job_id, top_n=args.top_n)
