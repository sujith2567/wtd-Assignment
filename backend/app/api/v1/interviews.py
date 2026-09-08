from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.app.core.database import get_db
from backend.app.core.security import get_current_user, require_role
from backend.app.models.user import User, UserRole
from backend.app.models.student import Student
from backend.app.models.job import JobPosting
from backend.app.models.interview import InterviewRecord, InterviewOutcome
from backend.app.schemas.interview import (
    InterviewRecordCreate,
    InterviewRecordResponse,
    FeedbackSuggestionRequest,
    FeedbackSuggestionResponse,
)

router = APIRouter(prefix="/interviews", tags=["Interview Feedback"])

def build_feedback_suggestions(tech: float, comm: float, ps: float, outcome: str) -> dict:
    strengths = []
    weaknesses = []
    recs = []

    if tech >= 8.0:
        strengths.append("Strong technical competence and domain knowledge.")
    elif tech < 6.0:
        weaknesses.append("Core technical skills require further practice.")
        recs.append("Review fundamental data structures and algorithms.")

    if ps >= 8.0:
        strengths.append("Methodical problem-solving and logical analytical thinking.")
    elif ps < 6.0:
        weaknesses.append("Struggled with complex edge cases and optimization.")
        recs.append("Practice system design and multi-step algorithmic problems.")

    if comm >= 8.0:
        strengths.append("Articulate communicator with clear presentation of solutions.")
    elif comm < 6.0:
        weaknesses.append("Verbal explanation and clarity could be improved.")
        recs.append("Practice mock technical interviews and verbal solution walkthroughs.")

    if outcome.lower() == "passed":
        summary = "Candidate demonstrated solid competence across evaluation criteria and is recommended to proceed."
    elif outcome.lower() == "on_hold":
        summary = "Candidate showed promise but requires further evaluation or comparative review."
    else:
        summary = "Candidate did not meet the required threshold for technical or communication standards."

    if not recs:
        recs.append("Continue developing advanced domain projects and system architecture skills.")

    return {
        "suggested_strengths": " ".join(strengths) if strengths else "Good baseline performance across rounds.",
        "suggested_weaknesses": " ".join(weaknesses) if weaknesses else "No major deficiencies observed.",
        "suggested_summary": summary,
        "recommendations": recs,
    }

@router.post("/template-suggestions", response_model=FeedbackSuggestionResponse)
def get_template_suggestions(req: FeedbackSuggestionRequest):
    data = build_feedback_suggestions(
        req.technical_score, req.communication_score, req.problem_solving_score, req.outcome
    )
    return FeedbackSuggestionResponse(**data)

@router.post("/", response_model=InterviewRecordResponse, status_code=status.HTTP_201_CREATED)
def submit_interview_feedback(
    record_in: InterviewRecordCreate,
    current_user: User = Depends(require_role([UserRole.RECRUITER, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    student = db.query(Student).filter(Student.id == record_in.student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    job = db.query(JobPosting).filter(JobPosting.id == record_in.job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job posting not found.")

    # If match_id is not explicitly passed, check if a MatchShortlist entry exists for this job & student
    match_id = record_in.match_id
    if not match_id:
        from backend.app.models.match import MatchShortlist
        existing_match = db.query(MatchShortlist).filter(
            MatchShortlist.job_id == record_in.job_id,
            MatchShortlist.student_id == record_in.student_id
        ).first()
        if existing_match:
            match_id = existing_match.id

    # Auto-generate suggestions if detailed_feedback or recommendations are empty
    if not record_in.detailed_feedback or not record_in.improvement_recommendations:
        sug = build_feedback_suggestions(
            record_in.technical_score,
            record_in.communication_score,
            record_in.problem_solving_score,
            record_in.interview_outcome.value,
        )
        if not record_in.detailed_feedback:
            record_in.detailed_feedback = sug["suggested_summary"]
        if not record_in.strengths:
            record_in.strengths = sug["suggested_strengths"]
        if not record_in.weaknesses:
            record_in.weaknesses = sug["suggested_weaknesses"]
        if not record_in.improvement_recommendations:
            record_in.improvement_recommendations = sug["recommendations"]

    record = InterviewRecord(
        match_id=match_id,
        student_id=record_in.student_id,
        job_id=record_in.job_id,
        round_number=record_in.round_number,
        round_name=record_in.round_name,
        technical_score=record_in.technical_score,
        communication_score=record_in.communication_score,
        problem_solving_score=record_in.problem_solving_score,
        strengths=record_in.strengths,
        weaknesses=record_in.weaknesses,
        detailed_feedback=record_in.detailed_feedback,
        interview_outcome=record_in.interview_outcome,
        improvement_recommendations=record_in.improvement_recommendations,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return InterviewRecordResponse(
        id=record.id,
        match_id=record.match_id,
        student_id=record.student_id,
        job_id=record.job_id,
        round_number=record.round_number,
        round_name=record.round_name,
        technical_score=record.technical_score,
        communication_score=record.communication_score,
        problem_solving_score=record.problem_solving_score,
        strengths=record.strengths,
        weaknesses=record.weaknesses,
        detailed_feedback=record.detailed_feedback,
        interview_outcome=record.interview_outcome,
        improvement_recommendations=record.improvement_recommendations or [],
        created_at=record.created_at,
        student_name=student.user.full_name if student.user else "",
        student_roll=student.roll_number,
        job_title=job.title,
        company_name=job.company.company_name if job.company else "",
    )

@router.get("/my-interviews", response_model=List[InterviewRecordResponse])
def get_own_student_interviews(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only student users can access my-interviews.")

    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        return []

    records = db.query(InterviewRecord).filter(InterviewRecord.student_id == student.id).all()
    results = []
    for r in records:
        results.append(InterviewRecordResponse(
            id=r.id,
            match_id=r.match_id,
            student_id=r.student_id,
            job_id=r.job_id,
            round_number=r.round_number,
            round_name=r.round_name,
            technical_score=r.technical_score,
            communication_score=r.communication_score,
            problem_solving_score=r.problem_solving_score,
            strengths=r.strengths,
            weaknesses=r.weaknesses,
            detailed_feedback=r.detailed_feedback,
            interview_outcome=r.interview_outcome,
            improvement_recommendations=r.improvement_recommendations or [],
            created_at=r.created_at,
            student_name=student.user.full_name if student.user else "",
            student_roll=student.roll_number,
            job_title=r.job.title if r.job else "",
            company_name=r.job.company.company_name if (r.job and r.job.company) else "",
        ))
    return results

@router.get("/", response_model=List[InterviewRecordResponse])
def list_interview_records(
    job_id: Optional[int] = Query(None),
    student_id: Optional[int] = Query(None),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER])),
    db: Session = Depends(get_db)
):
    query = db.query(InterviewRecord)
    if job_id and not hasattr(job_id, 'default'):
        query = query.filter(InterviewRecord.job_id == job_id)
    if student_id and not hasattr(student_id, 'default'):
        query = query.filter(InterviewRecord.student_id == student_id)

    records = query.all()
    results = []
    for r in records:
        results.append(InterviewRecordResponse(
            id=r.id,
            match_id=r.match_id,
            student_id=r.student_id,
            job_id=r.job_id,
            round_number=r.round_number,
            round_name=r.round_name,
            technical_score=r.technical_score,
            communication_score=r.communication_score,
            problem_solving_score=r.problem_solving_score,
            strengths=r.strengths,
            weaknesses=r.weaknesses,
            detailed_feedback=r.detailed_feedback,
            interview_outcome=r.interview_outcome,
            improvement_recommendations=r.improvement_recommendations or [],
            created_at=r.created_at,
            student_name=r.student.user.full_name if (r.student and r.student.user) else "",
            student_roll=r.student.roll_number if r.student else "",
            job_title=r.job.title if r.job else "",
            company_name=r.job.company.company_name if (r.job and r.job.company) else "",
        ))
    return results
