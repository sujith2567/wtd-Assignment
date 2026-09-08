from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from backend.app.core.database import get_db
from backend.app.core.security import get_current_user
from backend.app.models.user import User, UserRole
from backend.app.models.student import Student
from backend.app.models.readiness import ReadinessQuestion, ReadinessSubmission
from backend.app.schemas.readiness import (
    ReadinessQuestionOut,
    SubmissionCreate,
    ReadinessScoreOut
)

router = APIRouter(prefix="/readiness", tags=["Placement Readiness Score"])

@router.get("/questions/{domain}", response_model=List[ReadinessQuestionOut])
def get_questions_by_domain(
    domain: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    questions = db.query(ReadinessQuestion).filter(ReadinessQuestion.domain == domain).all()
    if not questions:
        # Fallback to general Software Development if specific domain questions aren't pre-seeded
        questions = db.query(ReadinessQuestion).filter(ReadinessQuestion.domain == "Software Development").all()

    result = []
    for q in questions:
        opts = q.options_json if isinstance(q.options_json, list) else []
        result.append({
            "id": q.id,
            "domain": q.domain,
            "question_text": q.question_text,
            "category": q.category,
            "weight": q.weight,
            "options": opts
        })
    return result

@router.post("/submit", response_model=ReadinessScoreOut)
def submit_readiness_checklist(
    payload: SubmissionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found.")

    if not payload.answers:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No answers provided.")

    # Calculate weighted score per category
    category_totals = {}
    category_maxes = {}

    for ans in payload.answers:
        q = db.query(ReadinessQuestion).filter(ReadinessQuestion.id == ans.question_id).first()
        if not q:
            continue
        cat = q.category
        w = q.weight or 1
        pts = max(0, min(5, ans.selected_points))

        category_totals[cat] = category_totals.get(cat, 0) + (pts * w)
        category_maxes[cat] = category_maxes.get(cat, 0) + (5 * w)

    if not category_maxes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid question answers.")

    category_scores = {}
    strong_areas = []
    weak_areas = []
    grand_total_earned = 0
    grand_total_max = 0

    for cat, max_pts in category_maxes.items():
        earned = category_totals.get(cat, 0)
        pct = round((earned / max_pts) * 100, 1)
        category_scores[cat] = pct
        grand_total_earned += earned
        grand_total_max += max_pts

        if pct >= 75.0:
            strong_areas.append(cat)
        elif pct < 60.0:
            weak_areas.append(cat)

    total_score_percent = round((grand_total_earned / grand_total_max) * 100, 1) if grand_total_max > 0 else 0.0

    submission = ReadinessSubmission(
        student_id=student.id,
        domain=payload.domain,
        total_score_percent=total_score_percent,
        strong_areas=strong_areas,
        weak_areas=weak_areas,
        category_scores_json=category_scores
    )

    db.add(submission)
    db.commit()
    db.refresh(submission)

    return {
        "id": submission.id,
        "student_id": submission.student_id,
        "domain": submission.domain,
        "total_score_percent": submission.total_score_percent,
        "strong_areas": submission.strong_areas or [],
        "weak_areas": submission.weak_areas or [],
        "category_scores": submission.category_scores_json or {},
        "created_at": submission.created_at
    }

@router.get("/score/{student_id}", response_model=ReadinessScoreOut)
def get_student_latest_readiness_score(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    if current_user.role == UserRole.STUDENT and student.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    latest = (
        db.query(ReadinessSubmission)
        .filter(ReadinessSubmission.student_id == student_id)
        .order_by(ReadinessSubmission.created_at.desc())
        .first()
    )

    if not latest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No readiness check submissions found for this student.")

    return {
        "id": latest.id,
        "student_id": latest.student_id,
        "domain": latest.domain,
        "total_score_percent": latest.total_score_percent,
        "strong_areas": latest.strong_areas or [],
        "weak_areas": latest.weak_areas or [],
        "category_scores": latest.category_scores_json or {},
        "created_at": latest.created_at
    }
