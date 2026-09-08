from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from decimal import Decimal
from typing import List, Optional

from backend.app.core.database import get_db
from backend.app.core.security import require_role
from backend.app.models.user import User, UserRole
from backend.app.models.student import Student
from backend.app.models.job import JobPosting
from backend.app.models.match import MatchTier
from backend.app.schemas.match import JobMatchResults, CandidateMatchItem

router = APIRouter(prefix="/matching", tags=["Matching & Shortlisting"])

@router.get("/jobs/{job_id}/baseline-candidates", response_model=JobMatchResults)
def evaluate_baseline_candidates(
    job_id: int,
    limit: int = Query(200, ge=1, le=500),
    include_buffer: bool = Query(False, description="If true, also surface buffer-match candidates: students who fall within the job's buffer_threshold_percent of min_cgpa (with at most one extra backlog) AND whose predicted_domain == job.target_domain with confidence >= buffer_min_confidence."),
    buffer_min_confidence: float = Query(0.70, ge=0.0, le=1.0, description="Minimum domain_confidence required for buffer promotion."),
    current_user: User = Depends(require_role([UserRole.RECRUITER, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """Rank candidates for a job by combined academic + skill + domain-fit score.

    Composite overall_score formula (weights documented for the report):
        overall_score = 0.35 * academic_score
                      + 0.40 * skill_match_score
                      + 0.25 * domain_fit_score
    where:
        academic_score    = min(1.0, cgpa / 10.0)
        skill_match_score = |student_skills ∩ job.required_skills| / |job.required_skills|
        domain_fit_score  = domain_confidence  if predicted_domain == job.target_domain
                            else 0.0
        semantic_similarity is left at 0.0 as a placeholder for the
        sentence-transformers layer (next milestone).

    Tier logic:
        strict_match  — CGPA >= min_cgpa AND active_backlogs <= max_backlogs
        buffer_match  — only emitted when include_buffer=true AND:
                          * CGPA >= min_cgpa * (1 - buffer_threshold_percent/100)
                          * active_backlogs <= max_backlogs + 1
                          * predicted_domain == job.target_domain
                          * domain_confidence >= buffer_min_confidence
        (Students who fail strict and have no buffer pass are dropped.)

    `strict_matches_count` and `buffer_matches_count` are returned
    independently so the strict count stays a clean pre-AI benchmark even
    when buffer promotion is enabled.
    """
    # Fetch job posting
    job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job posting not found.")

    if hasattr(limit, 'default'):
        limit = limit.default if limit.default is not None else 200
    if hasattr(include_buffer, 'default'):
        include_buffer = include_buffer.default if include_buffer.default is not None else False
    if hasattr(buffer_min_confidence, 'default'):
        buffer_min_confidence = buffer_min_confidence.default if buffer_min_confidence.default is not None else 0.70

    min_cgpa = float(job.min_cgpa)
    max_backlogs = job.max_backlogs_allowed
    buffer_pct = float(job.buffer_threshold_percent or 0.0)
    req_skills_set = {s.lower().strip() for s in (job.required_skills or [])}
    target_domain = (job.target_domain or "").strip()

    # Fetch all students and join user info
    students = db.query(Student).join(User, Student.user_id == User.id).all()

    matches: List[CandidateMatchItem] = []
    strict_count = 0
    buffer_count = 0

    # Weights exposed for the score_breakdown dict (kept in sync with formula above).
    W_ACADEMIC = 0.35
    W_SKILL = 0.40
    W_DOMAIN = 0.25

    # CGPA floor for buffer promotion (e.g. min_cgpa=7.0, buffer_pct=10 -> floor=6.3)
    buffer_cgpa_floor = min_cgpa * (1.0 - buffer_pct / 100.0) if buffer_pct > 0 else min_cgpa

    for student in students:
        s_cgpa = float(student.cgpa)
        s_backlogs = student.active_backlogs
        student_skills = student.skills or []
        s_skills_set = {s.lower().strip() for s in student_skills}

        # Skill overlap
        matching_skills = [s for s in (job.required_skills or []) if s.lower().strip() in s_skills_set]
        missing_skills = [s for s in (job.required_skills or []) if s.lower().strip() not in s_skills_set]
        skill_score = (len(matching_skills) / len(req_skills_set)) if req_skills_set else 1.0
        academic_score = min(1.0, s_cgpa / 10.0)

        # Domain-fit component
        s_pred = (student.predicted_domain or "").strip()
        s_conf = float(student.domain_confidence or 0.0)
        domain_fit = bool(s_pred) and bool(target_domain) and (s_pred == target_domain)
        domain_fit_score = s_conf if domain_fit else 0.0

        overall_score = round(
            W_ACADEMIC * academic_score + W_SKILL * skill_score + W_DOMAIN * domain_fit_score,
            3,
        )
        breakdown = {
            "academic_weight": round(W_ACADEMIC * academic_score, 4),
            "skill_weight":    round(W_SKILL    * skill_score,    4),
            "domain_weight":   round(W_DOMAIN   * domain_fit_score, 4),
        }

        meets_strict = (s_cgpa >= min_cgpa) and (s_backlogs <= max_backlogs)
        # Buffer gate (only meaningful when include_buffer is on)
        meets_buffer = (
            include_buffer
            and (s_cgpa >= buffer_cgpa_floor)
            and (s_backlogs <= max_backlogs + 1)
            and domain_fit
            and (s_conf >= buffer_min_confidence)
        )

        if meets_strict:
            tier = MatchTier.STRICT_MATCH.value
            strict_count += 1
            reason = (
                f"Strict match: CGPA {s_cgpa:.2f} >= {min_cgpa:.2f}, "
                f"Backlogs {s_backlogs} <= {max_backlogs}. "
                f"{len(matching_skills)}/{len(req_skills_set)} skills matched. "
                f"Domain-fit: predicted={s_pred or 'N/A'} ({s_conf:.0%}) "
                f"vs target={target_domain or 'N/A'}."
            )
            matches.append(CandidateMatchItem(
                student_id=student.id,
                user_id=student.user.id,
                full_name=student.user.full_name,
                email=student.user.email,
                roll_number=student.roll_number,
                department=student.department,
                cgpa=s_cgpa,
                active_backlogs=s_backlogs,
                skills=student_skills,
                match_tier=tier,
                overall_score=overall_score,
                academic_score=round(academic_score, 3),
                skill_match_score=round(skill_score, 3),
                semantic_similarity=0.0,  # Placeholder for upcoming embeddings layer
                domain_fit_score=round(domain_fit_score, 4),
                score_breakdown=breakdown,
                matching_skills=matching_skills,
                missing_skills=missing_skills,
                reason=reason,
            ))
        elif meets_buffer:
            tier = MatchTier.BUFFER_MATCH.value
            buffer_count += 1
            # For buffer candidates, missing skills / backlogs are explicitly called out
            gap_note = []
            if s_cgpa < min_cgpa:
                gap_note.append(f"CGPA {s_cgpa:.2f} below {min_cgpa:.2f} (within buffer)")
            if s_backlogs > max_backlogs:
                gap_note.append(f"{s_backlogs} active backlogs (within buffer)")
            reason = (
                f"Buffer match via domain-fit: {s_pred} ({s_conf:.0%}) "
                f"matches target {target_domain}. "
                + (" ".join(gap_note) + " " if gap_note else "")
                + f"{len(matching_skills)}/{len(req_skills_set)} skills matched."
            )
            matches.append(CandidateMatchItem(
                student_id=student.id,
                user_id=student.user.id,
                full_name=student.user.full_name,
                email=student.user.email,
                roll_number=student.roll_number,
                department=student.department,
                cgpa=s_cgpa,
                active_backlogs=s_backlogs,
                skills=student_skills,
                match_tier=tier,
                overall_score=overall_score,
                academic_score=round(academic_score, 3),
                skill_match_score=round(skill_score, 3),
                semantic_similarity=0.0,  # Placeholder for upcoming embeddings layer
                domain_fit_score=round(domain_fit_score, 4),
                score_breakdown=breakdown,
                matching_skills=matching_skills,
                missing_skills=missing_skills,
                reason=reason,
            ))
        # else: drop student (fails strict and either include_buffer is off
        #       or the domain-fit/confidence gate didn't pass)

    # Sort results by highest overall score
    matches.sort(key=lambda x: x.overall_score, reverse=True)
    matches = matches[:limit]

    return JobMatchResults(
        job_id=job.id,
        job_title=job.title,
        min_cgpa=min_cgpa,
        max_backlogs=max_backlogs,
        required_skills=job.required_skills or [],
        total_candidates_evaluated=len(students),
        strict_matches_count=strict_count,
        buffer_matches_count=buffer_count,
        matches=matches,
    )

from backend.app.schemas.student import (
    DomainPredictionResponse,
    StudentExplanationResponse,
    StudentExplanationTopClass,
    StudentExplanationExplanationFactor,
)
from backend.app.services.classifier_service import get_classifier_service

@router.post("/predict-domain/{student_id}", response_model=DomainPredictionResponse)
def predict_student_domain(
    student_id: int,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER, UserRole.STUDENT])),
    db: Session = Depends(get_db)
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    
    # Check permissions if student
    if current_user.role == UserRole.STUDENT and student.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    service = get_classifier_service()
    result = service.predict_and_explain(
        resume_text=student.raw_resume_text or "",
        skills=student.skills or [],
        projects=student.projects or []
    )

    # Persist AI prediction in student profile
    student.predicted_domain = result["predicted_domain"]
    student.domain_confidence = result["confidence"]
    db.commit()
    db.refresh(student)

    is_correct = (
        (student.domain_label == result["predicted_domain"])
        if student.domain_label else None
    )

    return DomainPredictionResponse(
        student_id=student.id,
        roll_number=student.roll_number,
        student_name=student.user.full_name,
        predicted_domain=result["predicted_domain"],
        confidence_score=result["confidence"],
        ground_truth_domain=student.domain_label,
        is_correct=is_correct,
        class_probabilities=result["class_probabilities"],
        explainability=result["explainability"],
        model_version=result["model_version"]
    )

@router.post("/batch-predict-domains")
def batch_predict_all_students(
    section_id: Optional[int] = Query(None, description="Scope batch prediction to a specific section's students only"),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """Run domain classifier over all students, or only students in a specific section."""
    service = get_classifier_service()

    if section_id is not None:
        from backend.app.models.section import Section
        section = db.query(Section).filter(Section.id == section_id).first()
        if not section:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found.")
        students = db.query(Student).filter(Student.section_id == section_id).all()
        scope_label = f"section '{section.name}' (id={section_id})"
    else:
        students = db.query(Student).all()
        scope_label = "global (all students)"

    processed = 0
    correct_count = 0

    for s in students:
        res = service.predict_and_explain(
            resume_text=s.raw_resume_text or "",
            skills=s.skills or [],
            projects=s.projects or []
        )
        s.predicted_domain = res["predicted_domain"]
        s.domain_confidence = res["confidence"]
        if s.domain_label and s.domain_label == res["predicted_domain"]:
            correct_count += 1
        processed += 1

    db.commit()
    return {
        "status": "success",
        "scope": scope_label,
        "total_processed": processed,
        "matching_ground_truth": correct_count,
        "sample_preview": f"Updated AI predicted domain for {processed} students in scope: {scope_label}."
    }


# ----------------------------------------------------------------------------
# Read-only explainability dashboard
# ----------------------------------------------------------------------------

@router.get("/student/{student_id}/explanation", response_model=StudentExplanationResponse)
def get_student_domain_explanation(
    student_id: int,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER, UserRole.STUDENT])),
    db: Session = Depends(get_db)
):
    """Return the classifier's prediction, per-instance feature attribution,
    class probability distribution, and a human-readable summary for a single
    student.

    This endpoint is **read-only** — it does NOT write predicted_domain or
    domain_confidence to the database. It reuses the trained model in
    memory, so it can be called repeatedly without side effects (e.g. by
    the recruiter UI or a student-facing explainability dashboard).
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    # Students can only see their own explanation; Admin/Recruiter can see any.
    if current_user.role == UserRole.STUDENT and student.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    service = get_classifier_service()
    result = service.predict_and_explain(
        resume_text=student.raw_resume_text or "",
        skills=student.skills or [],
        projects=student.projects or [],
        top_k_factors=5,
    )

    predicted_domain = result["predicted_domain"]
    confidence = float(result["confidence"])
    ground_truth = student.domain_label
    is_correct = (ground_truth == predicted_domain) if ground_truth else None
    is_noisy = bool(ground_truth) and (ground_truth != predicted_domain)

    # Sort class probabilities desc for the dashboard
    class_probs_sorted = sorted(
        result["class_probabilities"].items(), key=lambda kv: kv[1], reverse=True
    )
    top_classes = [
        StudentExplanationTopClass(domain=name, probability=float(p))
        for name, p in class_probs_sorted
    ]

    # Direction: positive weight => supports the prediction strongly.
    # We surface weight as a "supports" / "weakly_supports" / "against"
    # hint for the UI; threshold tuned to the v2 model's typical scale.
    factors: List[StudentExplanationExplanationFactor] = []
    for f in result["explainability"]:
        w = float(f["weight"])
        if w >= 0.5:
            direction = "supports"
        elif w >= 0.1:
            direction = "weakly_supports"
        else:
            direction = "against"
        factors.append(StudentExplanationExplanationFactor(
            keyword=f["feature"],
            weight=round(w, 4),
            direction=direction,
            description=f["description"],
        ))

    summary = service.build_human_readable_summary(
        predicted_domain=predicted_domain,
        confidence=confidence,
        top_factors=result["explainability"],
        ground_truth_domain=ground_truth,
    )

    return StudentExplanationResponse(
        student_id=student.id,
        roll_number=student.roll_number,
        student_name=student.user.full_name,
        predicted_domain=predicted_domain,
        confidence_score=round(confidence, 4),
        ground_truth_domain=ground_truth,
        is_correct=is_correct,
        is_noisy_case=is_noisy,
        class_probabilities=top_classes,
        top_contributing_factors=factors,
        human_readable_summary=summary,
        model_version=result["model_version"],
    )
