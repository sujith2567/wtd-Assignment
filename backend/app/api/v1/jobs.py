from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.app.core.database import get_db
from backend.app.core.security import get_current_user, require_role
from backend.app.models.user import User, UserRole
from backend.app.models.company import Company
from backend.app.models.job import JobPosting, JobStatus
from backend.app.models.match import MatchShortlist
from backend.app.schemas.job import (
    JobPostingCreate, JobPostingUpdate, JobPostingResponse
)
from backend.app.schemas.match import MatchShortlistResponse

router = APIRouter(prefix="/jobs", tags=["Jobs & Recruiters"])

@router.post("/", response_model=JobPostingResponse, status_code=status.HTTP_201_CREATED)
def create_job_posting(
    job_in: JobPostingCreate,
    current_user: User = Depends(require_role([UserRole.RECRUITER, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    # Find or link company
    company = db.query(Company).filter(Company.user_id == current_user.id).first()
    if not company:
        # Fallback to first company or create one
        company = db.query(Company).first()
        if not company:
            company = Company(
                user_id=current_user.id,
                company_name=f"{current_user.full_name}'s Company",
                contact_email=current_user.email
            )
            db.add(company)
            db.commit()
            db.refresh(company)

    job = JobPosting(
        company_id=company.id,
        title=job_in.title,
        target_domain=job_in.target_domain,
        description=job_in.description,
        min_cgpa=job_in.min_cgpa,
        max_backlogs_allowed=job_in.max_backlogs_allowed,
        required_skills=job_in.required_skills,
        preferred_skills=job_in.preferred_skills,
        salary_range=job_in.salary_range,
        location=job_in.location,
        status=job_in.status,
        buffer_threshold_percent=job_in.buffer_threshold_percent
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job

@router.get("/my-jobs", response_model=List[JobPostingResponse])
def get_recruiter_jobs(
    current_user: User = Depends(require_role([UserRole.RECRUITER, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    company = db.query(Company).filter(Company.user_id == current_user.id).first()
    if not company:
        return []
    return db.query(JobPosting).filter(JobPosting.company_id == company.id).all()

@router.get("/", response_model=List[JobPostingResponse])
def list_active_jobs(
    domain: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(JobPosting).filter(JobPosting.status == JobStatus.ACTIVE)
    if domain:
        query = query.filter(JobPosting.target_domain.ilike(f"%{domain}%"))
    return query.offset(skip).limit(limit).all()

@router.get("/{job_id}", response_model=JobPostingResponse)
def get_job_by_id(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job posting not found.")
    return job

@router.put("/{job_id}", response_model=JobPostingResponse)
def update_job_posting(
    job_id: int,
    job_update: JobPostingUpdate,
    current_user: User = Depends(require_role([UserRole.RECRUITER, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job posting not found.")

    update_data = job_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(job, field, value)

    db.commit()
    db.refresh(job)
    return job

@router.get("/{job_id}/shortlists", response_model=List[MatchShortlistResponse])
def get_job_shortlists(
    job_id: int,
    current_user: User = Depends(require_role([UserRole.RECRUITER, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    shortlists = db.query(MatchShortlist).filter(MatchShortlist.job_id == job_id).all()
    return shortlists
