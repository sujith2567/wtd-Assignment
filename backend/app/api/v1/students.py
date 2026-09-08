from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from decimal import Decimal
import csv
import io

from backend.app.core.database import get_db
from backend.app.core.security import get_current_user, require_role, get_password_hash
from backend.app.models.user import User, UserRole
from backend.app.models.student import Student, StudentProject
from backend.app.schemas.student import (
    StudentResponse, StudentBulkUploadResult, StudentUpdate
)

router = APIRouter(prefix="/students", tags=["Students"])

@router.get("/profile", response_model=StudentResponse)
def get_own_student_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current user is not registered as a student."
        )
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found.")
    return student

@router.get("/", response_model=List[StudentResponse])
def list_students(
    min_cgpa: Optional[float] = Query(None, description="Minimum CGPA filter"),
    max_cgpa: Optional[float] = Query(None, description="Maximum CGPA filter"),
    max_backlogs: Optional[int] = Query(None, description="Maximum active backlogs allowed"),
    department: Optional[str] = Query(None, description="Filter by department"),
    domain: Optional[str] = Query(None, description="Filter by predicted domain"),
    search: Optional[str] = Query(None, description="Search by roll number or student name"),
    section_id: Optional[int] = Query(None, description="[Admin only] Filter by section ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER])),
    db: Session = Depends(get_db)
):
    query = db.query(Student).join(User, Student.user_id == User.id)

    if min_cgpa is not None and not hasattr(min_cgpa, 'default'):
        query = query.filter(Student.cgpa >= Decimal(str(min_cgpa)))
    if max_cgpa is not None and not hasattr(max_cgpa, 'default'):
        query = query.filter(Student.cgpa <= Decimal(str(max_cgpa)))
    if max_backlogs is not None and not hasattr(max_backlogs, 'default'):
        query = query.filter(Student.active_backlogs <= max_backlogs)
    if department and not hasattr(department, 'default'):
        query = query.filter(Student.department.ilike(f"%{department}%"))
    if domain and not hasattr(domain, 'default'):
        query = query.filter(Student.predicted_domain.ilike(f"%{domain}%"))
    if search and not hasattr(search, 'default'):
        query = query.filter(
            or_(
                Student.roll_number.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%")
            )
        )
    # section_id filter is admin-only; ignored for recruiters
    if section_id is not None and not hasattr(section_id, 'default') and current_user.role == UserRole.ADMIN:
        query = query.filter(Student.section_id == section_id)

    skip_val = skip.default if hasattr(skip, 'default') else skip
    limit_val = limit.default if hasattr(limit, 'default') else limit
    students = query.offset(skip_val).limit(limit_val).all()
    return students

@router.get("/{student_id}", response_model=StudentResponse)
def get_student_by_id(
    student_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    
    # Students can only view their own profile; Admin/Recruiters can view any profile
    if current_user.role == UserRole.STUDENT and student.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
        
    return student

@router.post("/bulk-upload", response_model=StudentBulkUploadResult)
async def bulk_upload_students_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    from backend.app.api.v1.sections import parse_bulk_student_file

    contents = await file.read()
    parsed_rows = parse_bulk_student_file(file.filename, contents)

    total_parsed = 0
    successful_inserts = 0
    failed_rows = []
    default_hash = get_password_hash("password123")

    for row_idx, row in enumerate(parsed_rows, start=2):
        total_parsed += 1
        try:
            email = str(row.get("email", "")).strip()
            full_name = str(row.get("full_name", "")).strip()
            roll_number = str(row.get("roll_number", "")).strip()
            department = str(row.get("department", "Computer Science")).strip() or "Computer Science"
            batch_year = int(float(row.get("batch_year", 2025) or 2025))
            cgpa_val = row.get("cgpa", 7.00)
            cgpa = Decimal(str(cgpa_val if cgpa_val != "" else 7.00))
            active_backlogs = int(float(row.get("active_backlogs", 0) or 0))

            skills_raw = str(row.get("skills", ""))
            if ";" in skills_raw:
                skills = [s.strip() for s in skills_raw.split(";") if s.strip()]
            elif "," in skills_raw:
                skills = [s.strip() for s in skills_raw.split(",") if s.strip()]
            else:
                skills = [skills_raw.strip()] if skills_raw.strip() else []

            resume_text = str(row.get("resume_text", f"Resume summary for {full_name}"))

            if not email or not roll_number or not full_name:
                failed_rows.append({"row": row_idx, "reason": "Missing required fields (email, full_name, or roll_number)"})
                continue

            # Check if user already exists
            existing_user = db.query(User).filter(User.email == email).first()
            if existing_user:
                failed_rows.append({"row": row_idx, "email": email, "reason": "Email already exists"})
                continue

            # Check if roll number exists
            existing_roll = db.query(Student).filter(Student.roll_number == roll_number).first()
            if existing_roll:
                failed_rows.append({"row": row_idx, "roll_number": roll_number, "reason": "Roll number already exists"})
                continue

            new_user = User(
                email=email,
                hashed_password=default_hash,
                role=UserRole.STUDENT,
                full_name=full_name,
                is_active=True
            )
            db.add(new_user)
            db.flush()

            new_student = Student(
                user_id=new_user.id,
                roll_number=roll_number,
                department=department,
                batch_year=batch_year,
                cgpa=cgpa,
                active_backlogs=active_backlogs,
                history_backlogs=active_backlogs,
                skills=skills,
                raw_resume_text=resume_text,
                predicted_domain=row.get("predicted_domain", "Software Development"),
                domain_confidence=0.85
            )
            db.add(new_student)
            successful_inserts += 1

        except Exception as err:
            failed_rows.append({"row": row_idx, "reason": str(err)})

    db.commit()
    return {
        "total_parsed": total_parsed,
        "successful_inserts": successful_inserts,
        "failed_rows": failed_rows
    }


@router.put("/{student_id}", response_model=StudentResponse)
def update_student(
    student_id: int,
    student_in: StudentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    
    # Permission check: Student can only edit own profile; Admin can edit any student profile
    if current_user.role == UserRole.STUDENT and student.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    if current_user.role not in [UserRole.ADMIN, UserRole.STUDENT]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    # Update User full_name if provided
    if student_in.full_name is not None and student.user:
        student.user.full_name = student_in.full_name

    # Update Student fields
    if student_in.roll_number is not None:
        student.roll_number = student_in.roll_number
    if student_in.department is not None:
        student.department = student_in.department
    if student_in.batch_year is not None:
        student.batch_year = student_in.batch_year
    if student_in.cgpa is not None:
        student.cgpa = student_in.cgpa
    if student_in.active_backlogs is not None:
        student.active_backlogs = student_in.active_backlogs
    if student_in.history_backlogs is not None:
        student.history_backlogs = student_in.history_backlogs
    if student_in.phone is not None:
        student.phone = student_in.phone
    if student_in.skills is not None:
        student.skills = student_in.skills
    if student_in.raw_resume_text is not None:
        student.raw_resume_text = student_in.raw_resume_text
    if student_in.predicted_domain is not None:
        student.predicted_domain = student_in.predicted_domain

    # Re-run ML domain classifier if resume text or skills updated
    if student_in.raw_resume_text is not None or student_in.skills is not None:
        try:
            from backend.app.services.classifier_service import get_classifier_service
            clf = get_classifier_service()
            result = clf.predict_and_explain(
                resume_text=student.raw_resume_text or "",
                skills=student.skills or [],
                projects=student.projects or []
            )
            student.predicted_domain = result["predicted_domain"]
            student.domain_confidence = result["confidence"]
        except Exception:
            pass

    # Invalidate cached AuditLog on student edit
    try:
        from backend.app.models.audit_log import AuditLog
        db.query(AuditLog).filter(AuditLog.student_id == student.id).delete()
    except Exception:
        pass

    db.commit()
    db.refresh(student)
    return student


@router.post("/upload-resume", response_model=StudentResponse)
async def upload_student_resume(
    email: str = Query(...),
    full_name: str = Query(...),
    roll_number: str = Query(...),
    department: str = Query("Computer Science"),
    cgpa: float = Query(7.5),
    active_backlogs: int = Query(0),
    skills_csv: Optional[str] = Query(None, description="Comma-separated skills"),
    file: Optional[UploadFile] = File(None),
    raw_text: Optional[str] = Query(None, description="Raw text if file not uploaded"),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    from backend.app.api.v1.sections import _extract_text_from_file

    extracted_text = ""
    if file:
        content = await file.read()
        extracted_text = _extract_text_from_file(file.filename, content)
    elif raw_text:
        extracted_text = raw_text
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either a resume file or raw_text must be provided."
        )


    skills_list = [s.strip() for s in skills_csv.split(",") if s.strip()] if skills_csv else []

    # Check if student exists by email or roll
    user = db.query(User).filter(User.email == email).first()
    default_hash = get_password_hash("password123")

    if not user:
        user = User(
            email=email,
            hashed_password=default_hash,
            role=UserRole.STUDENT,
            full_name=full_name,
            is_active=True
        )
        db.add(user)
        db.flush()

    student = db.query(Student).filter(Student.user_id == user.id).first()
    if not student:
        student = db.query(Student).filter(Student.roll_number == roll_number).first()

    if not student:
        student = Student(
            user_id=user.id,
            roll_number=roll_number,
            department=department,
            batch_year=2025,
            cgpa=Decimal(str(cgpa)),
            active_backlogs=active_backlogs,
            skills=skills_list,
            raw_resume_text=extracted_text
        )
        db.add(student)
        db.flush()
    else:
        student.department = department
        student.cgpa = Decimal(str(cgpa))
        student.active_backlogs = active_backlogs
        if skills_list:
            student.skills = skills_list
        student.raw_resume_text = extracted_text
        user.full_name = full_name

    # Predict domain
    try:
        from backend.app.services.classifier_service import get_classifier_service
        clf = get_classifier_service()
        result = clf.predict_and_explain(
            resume_text=student.raw_resume_text or "",
            skills=student.skills or [],
            projects=student.projects or []
        )
        student.predicted_domain = result["predicted_domain"]
        student.domain_confidence = result["confidence"]
    except Exception:
        student.predicted_domain = "Software Development"
        student.domain_confidence = 0.85

    db.commit()
    db.refresh(student)
    return student

