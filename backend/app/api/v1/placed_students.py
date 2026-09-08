from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from decimal import Decimal
import csv
import io

from backend.app.core.database import get_db
from backend.app.core.security import get_current_user, require_role
from backend.app.models.user import User, UserRole
from backend.app.models.placed_student import PlacedStudent
from backend.app.schemas.placed_student import PlacedStudentResponse, PlacedStudentCreate
from backend.app.services.classifier_service import get_classifier_service

router = APIRouter(prefix="/placed-students", tags=["Placed Students"])

@router.get("/", response_model=List[PlacedStudentResponse])
def list_placed_students(
    search: Optional[str] = Query(None, description="Search by name, company, or role"),
    domain: Optional[str] = Query(None, description="Filter by domain"),
    company: Optional[str] = Query(None, description="Filter by company name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(PlacedStudent)

    if domain:
        query = query.filter(PlacedStudent.domain.ilike(f"%{domain}%"))
    if company:
        query = query.filter(PlacedStudent.company_name.ilike(f"%{company}%"))
    if search:
        query = query.filter(
            or_(
                PlacedStudent.student_name.ilike(f"%{search}%"),
                PlacedStudent.company_name.ilike(f"%{search}%"),
                PlacedStudent.role_title.ilike(f"%{search}%"),
                PlacedStudent.domain.ilike(f"%{search}%")
            )
        )

    records = query.order_by(PlacedStudent.created_at.desc()).offset(skip).limit(limit).all()
    return records

@router.get("/{id}", response_model=PlacedStudentResponse)
def get_placed_student_by_id(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    record = db.query(PlacedStudent).filter(PlacedStudent.id == id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Placed student record not found.")
    return record

@router.get("/{id}/explainability")
def get_placed_student_explainability(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    record = db.query(PlacedStudent).filter(PlacedStudent.id == id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Placed student record not found.")

    clf = get_classifier_service()
    explanation = clf.predict_and_explain(
        resume_text=record.raw_resume_text or f"{record.student_name} - {record.role_title} at {record.company_name}",
        skills=record.talents or [],
        projects=[]
    )

    human_summary = clf.build_human_readable_summary(
        predicted_domain=explanation["predicted_domain"],
        confidence=explanation["confidence"],
        top_factors=explanation["explainability"],
        ground_truth_domain=record.domain
    )

    return {
        "placed_student_id": record.id,
        "student_name": record.student_name,
        "company_name": record.company_name,
        "role_title": record.role_title,
        "actual_domain": record.domain,
        "predicted_domain": explanation["predicted_domain"],
        "confidence_score": explanation["confidence"],
        "is_correct": explanation["predicted_domain"].lower() in record.domain.lower() or record.domain.lower() in explanation["predicted_domain"].lower(),
        "class_probabilities": explanation["class_probabilities"],
        "explainability_factors": explanation["explainability"],
        "human_readable_summary": human_summary
    }

@router.post("/", response_model=PlacedStudentResponse, status_code=status.HTTP_201_CREATED)
def create_placed_student(
    payload: PlacedStudentCreate,
    current_user: User = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    record = PlacedStudent(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record

@router.post("/upload")
async def bulk_upload_placed_students_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    contents = await file.read()
    try:
        decoded = contents.decode("utf-8")
    except UnicodeDecodeError:
        decoded = contents.decode("latin-1", errors="ignore")

    reader = csv.DictReader(io.StringIO(decoded))
    count = 0
    for row in reader:
        student_name = row.get("student_name", "").strip()
        company_name = row.get("company_name", "").strip()
        role_title = row.get("role_title", "").strip()
        if not student_name or not company_name or not role_title:
            continue

        cgpa = Decimal(str(row.get("cgpa", 8.0)))
        domain = row.get("domain", "Software Development").strip()
        talents_raw = row.get("talents", row.get("skills", ""))
        talents = [t.strip() for t in talents_raw.split(";") if t.strip()] if talents_raw else []
        year = int(row.get("placement_year", 2024))
        resume_text = row.get("raw_resume_text", f"Resume text for {student_name}, placed as {role_title} at {company_name}")

        record = PlacedStudent(
            student_name=student_name,
            company_name=company_name,
            role_title=role_title,
            cgpa=cgpa,
            domain=domain,
            talents=talents,
            placement_year=year,
            raw_resume_text=resume_text
        )
        db.add(record)
        count += 1

    db.commit()
    return {"message": f"Successfully uploaded {count} placed student records."}
