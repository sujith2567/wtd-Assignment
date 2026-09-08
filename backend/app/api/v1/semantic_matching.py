"""
semantic_matching.py
====================
API Router for Hybrid Semantic Matching (Sentence-BERT) & Ablation Study.

Endpoints:
- GET /matching/semantic/{job_id}
- GET /matching/ablation/{job_id}
"""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import require_role
from backend.app.models.user import User, UserRole
from backend.app.models.student import Student
from backend.app.models.job import JobPosting
from backend.app.services.classifier_service import get_classifier_service
from backend.app.services.semantic_matching import (
    compute_semantic_score,
    compute_hybrid_score,
    explain_sentence_alignment,
)
from backend.app.schemas.semantic_match import (
    AblationComparisonItem,
    AblationResults,
    CandidateSemanticMatchItem,
    SemanticMatchResults,
    SentenceAlignmentItem,
)

router = APIRouter(prefix="/matching", tags=["Semantic Matching & Ablation"])


def _get_student_resume_text(student: Student) -> str:
    """Helper to retrieve or assemble student resume text for embedding."""
    if student.raw_resume_text and len(student.raw_resume_text.strip()) > 20:
        return student.raw_resume_text.strip()
    
    # Fallback assembly if raw_resume_text is sparse
    skills_str = ", ".join(student.skills or [])
    projects_str = " ".join([
        f"{p.title}: {p.description}"
        for p in (student.projects or [])
    ])
    return f"Student: {student.full_name}. Department: {student.department}. Skills: {skills_str}. Projects: {projects_str}"


def _get_student_domain_confidence(student: Student, target_domain: str) -> float:
    """
    Get existing TF-IDF+LogReg domain classifier confidence for the target domain.
    If student predicted_domain matches target_domain, return domain_confidence;
    otherwise use the domain classifier service to get exact target class probability.
    """
    if student.predicted_domain == target_domain and student.domain_confidence is not None:
        return float(student.domain_confidence)
    
    # Query classifier service for exact class probability
    try:
        classifier_service = get_classifier_service()
        res = classifier_service.predict_and_explain(
            resume_text=student.raw_resume_text or "",
            skills=student.skills or [],
            projects=student.projects or [],
        )
        probas = res.get("class_probabilities", {})
        return float(probas.get(target_domain, 0.0))
    except Exception:
        return 0.0


@router.get("/semantic/{job_id}", response_model=SemanticMatchResults)
def evaluate_semantic_matches(
    job_id: int,
    limit: int = Query(200, ge=1, le=500),
    weight_domain: float = Query(0.6, ge=0.0, le=1.0, description="Weight for TF-IDF domain confidence"),
    weight_semantic: float = Query(0.4, ge=0.0, le=1.0, description="Weight for SBERT semantic match score"),
    top_k_alignments: int = Query(3, ge=1, le=10, description="Number of sentence alignment pairs to return"),
    current_user: User = Depends(require_role([UserRole.RECRUITER, UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """
    Evaluate candidates for a job posting using Sentence-BERT (SBERT) Hybrid Semantic Matching.

    Returns for each candidate:
    - domain_confidence: Existing TF-IDF+LogReg domain classifier confidence
    - semantic_score: SBERT cosine similarity score (resume text vs job description)
    - hybrid_score: Weighted combination (0.6 * domain_confidence + 0.4 * semantic_score)
    - sentence_alignments: Sentence-level semantic alignment breakdown (top K requirement vs resume pairs)
    """
    job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job posting not found.")

    students = db.query(Student).join(Student.user).all()
    job_desc = job.description or f"{job.title} in {job.target_domain}. Skills: {', '.join(job.required_skills or [])}"
    target_domain = job.target_domain

    evaluated_candidates: List[CandidateSemanticMatchItem] = []

    for student in students:
        resume_text = _get_student_resume_text(student)
        domain_conf = _get_student_domain_confidence(student, target_domain)
        sem_score = compute_semantic_score(resume_text, job_desc)
        hyb_score = compute_hybrid_score(domain_conf, sem_score, weight_domain, weight_semantic)

        alignments_raw = explain_sentence_alignment(resume_text, job_desc, top_k=top_k_alignments)
        sentence_alignments = [
            SentenceAlignmentItem(
                jd_requirement=item["jd_requirement"],
                best_matching_resume_sentence=item["best_matching_resume_sentence"],
                similarity_score=item["similarity_score"],
            )
            for item in alignments_raw
        ]

        evaluated_candidates.append(CandidateSemanticMatchItem(
            student_id=student.id,
            user_id=student.user_id,
            full_name=student.full_name,
            email=student.user.email if student.user else "",
            roll_number=student.roll_number,
            department=student.department,
            cgpa=float(student.cgpa),
            active_backlogs=student.active_backlogs,
            skills=student.skills or [],
            predicted_domain=student.predicted_domain,
            domain_confidence=round(domain_conf, 4),
            semantic_score=round(sem_score, 4),
            hybrid_score=round(hyb_score, 4),
            sentence_alignments=sentence_alignments,
        ))

    # Sort candidates by hybrid_score descending
    evaluated_candidates.sort(key=lambda c: c.hybrid_score, reverse=True)
    sliced_candidates = evaluated_candidates[:limit]

    return SemanticMatchResults(
        job_id=job.id,
        job_title=job.title,
        target_domain=job.target_domain,
        weight_domain=weight_domain,
        weight_semantic=weight_semantic,
        total_candidates_evaluated=len(evaluated_candidates),
        candidates=sliced_candidates,
    )


@router.get("/ablation/{job_id}", response_model=AblationResults)
def generate_ablation_study(
    job_id: int,
    current_user: User = Depends(require_role([UserRole.RECRUITER, UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """
    Generate side-by-side ranking comparison across TF-IDF-only, SBERT-only, and Hybrid models
    for ablation study reporting in the IEEE paper.
    """
    job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job posting not found.")

    students = db.query(Student).join(Student.user).all()
    job_desc = job.description or f"{job.title} in {job.target_domain}. Skills: {', '.join(job.required_skills or [])}"
    target_domain = job.target_domain

    records = []
    for student in students:
        resume_text = _get_student_resume_text(student)
        tfidf_score = _get_student_domain_confidence(student, target_domain)
        sbert_score = compute_semantic_score(resume_text, job_desc)
        hybrid_score = compute_hybrid_score(tfidf_score, sbert_score, 0.6, 0.4)

        records.append({
            "student_id": student.id,
            "full_name": student.full_name,
            "roll_number": student.roll_number,
            "department": student.department,
            "cgpa": float(student.cgpa),
            "tfidf_score": round(tfidf_score, 4),
            "sbert_score": round(sbert_score, 4),
            "hybrid_score": round(hybrid_score, 4),
        })

    # Sort by TF-IDF to assign tfidf_rank
    records.sort(key=lambda r: (r["tfidf_score"], r["cgpa"]), reverse=True)
    for rank, r in enumerate(records, start=1):
        r["tfidf_rank"] = rank

    # Sort by SBERT to assign sbert_rank
    records.sort(key=lambda r: (r["sbert_score"], r["cgpa"]), reverse=True)
    for rank, r in enumerate(records, start=1):
        r["sbert_rank"] = rank

    # Sort by Hybrid to assign hybrid_rank
    records.sort(key=lambda r: (r["hybrid_score"], r["cgpa"]), reverse=True)
    for rank, r in enumerate(records, start=1):
        r["hybrid_rank"] = rank

    comparisons: List[AblationComparisonItem] = []
    for r in records:
        comparisons.append(AblationComparisonItem(
            student_id=r["student_id"],
            full_name=r["full_name"],
            roll_number=r["roll_number"],
            department=r["department"],
            cgpa=r["cgpa"],
            tfidf_score=r["tfidf_score"],
            sbert_score=r["sbert_score"],
            hybrid_score=r["hybrid_score"],
            tfidf_rank=r["tfidf_rank"],
            sbert_rank=r["sbert_rank"],
            hybrid_rank=r["hybrid_rank"],
            rank_delta_hybrid_vs_tfidf=r["tfidf_rank"] - r["hybrid_rank"],
        ))

    # Keep default return sorted by hybrid rank
    comparisons.sort(key=lambda c: c.hybrid_rank)

    return AblationResults(
        job_id=job.id,
        job_title=job.title,
        target_domain=job.target_domain,
        total_candidates=len(comparisons),
        comparisons=comparisons,
    )
