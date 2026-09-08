from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from backend.app.core.database import get_db
from backend.app.core.security import get_current_user
from backend.app.models.user import User, UserRole
from backend.app.models.student import Student
from backend.app.models.company import Company
from backend.app.models.job import JobPosting
from backend.app.models.application import Application, ApplicationStatus
from backend.app.schemas.application import (
    ApplicationCreate,
    ApplicationStatusUpdate,
    ApplicationResponse
)

router = APIRouter(prefix="/applications", tags=["Application Status Tracking"])

@router.get("/{student_id}", response_model=List[ApplicationResponse])
def get_student_applications(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    if current_user.role == UserRole.STUDENT and student.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    apps = db.query(Application).filter(Application.student_id == student_id).order_by(Application.updated_at.desc()).all()
    return apps

@router.post("/", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
def create_application(
    payload: ApplicationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can apply to jobs.")

    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found.")

    # Check if application for same job already exists
    if payload.job_id:
        existing = db.query(Application).filter(
            Application.student_id == student.id,
            Application.job_id == payload.job_id
        ).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You have already applied to this job posting.")

    app = Application(
        student_id=student.id,
        job_id=payload.job_id,
        company_name=payload.company_name,
        status=payload.status or ApplicationStatus.APPLIED
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return app

@router.put("/{application_id}/status", response_model=ApplicationResponse)
def update_application_status(
    application_id: int,
    payload: ApplicationStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    app_record = db.query(Application).filter(Application.id == application_id).first()
    if not app_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application record not found.")

    # Admin can update any application
    if current_user.role == UserRole.ADMIN:
        pass
    elif current_user.role == UserRole.RECRUITER:
        company = db.query(Company).filter(Company.user_id == current_user.id).first()
        if not company:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recruiter company record not found.")
        
        # Verify company matches either job company or application company_name
        is_company_match = False
        if app_record.job_id:
            job = db.query(JobPosting).filter(JobPosting.id == app_record.job_id).first()
            if job and job.company_id == company.id:
                is_company_match = True

        if not is_company_match and app_record.company_name.lower().strip() == company.name.lower().strip():
            is_company_match = True

        if not is_company_match:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Recruiters can only update application statuses for their own company's postings."
            )
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. Only recruiters or admins can update application statuses.")

    app_record.status = payload.status
    db.commit()
    db.refresh(app_record)
    return app_record
