from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from backend.app.core.database import get_db
from backend.app.core.security import get_current_user
from backend.app.models.user import User, UserRole
from backend.app.models.student import Student
from backend.app.models.section import Section
from backend.app.models.audit_log import AuditLog
from backend.app.services.shap_service import get_shap_comparison_service
from backend.app.services.anomaly_service import get_anomaly_detection_service, AnomalyDetectionService

router = APIRouter(tags=["ML Novelty Audit & SHAP"])


def _get_section_peers(section_id: int, exclude_student_id: int, db: Session):
    """Return all students in the section except the target student (used as peer group)."""
    return (
        db.query(Student)
        .filter(Student.section_id == section_id, Student.id != exclude_student_id)
        .all()
    )


@router.get("/explain/shap-compare/{student_id}")
def get_student_shap_comparison(
    student_id: int,
    section_id: Optional[int] = Query(None, description="Scope SHAP calibration to a specific section's peer group"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    # Permissions: Student can view their own profile; Admin & Recruiters can view any profile
    if current_user.role == UserRole.STUDENT and student.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    # Check cached AuditLog if section_id is provided
    target_section_id = section_id or student.section_id
    if target_section_id:
        audit_log = db.query(AuditLog).filter(
            AuditLog.student_id == student_id,
            AuditLog.section_id == target_section_id
        ).first()
        if audit_log and audit_log.shap_result:
            return audit_log.shap_result

    # Resolve peer group if section_id provided
    peer_students = None
    scope_meta = {"scope": "global"}
    if section_id is not None:
        section = db.query(Section).filter(Section.id == section_id).first()
        if not section:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found.")
        peer_students = _get_section_peers(section_id, student_id, db)
        scope_meta = {
            "scope": f"section:{section_id}",
            "section_name": section.name,
            "peer_count": len(peer_students),
        }

    shap_svc = get_shap_comparison_service()
    analysis = shap_svc.compute_shap_comparison(
        resume_text=student.raw_resume_text or "",
        skills=student.skills or [],
        projects=student.projects or [],
        target_domain=student.predicted_domain,
        peer_students=peer_students,
    )

    response_data = {
        "student_id": student.id,
        "roll_number": student.roll_number,
        "student_name": student.full_name,
        **scope_meta,
        "shap_analysis": analysis,
    }

    if target_section_id:
        audit_log = db.query(AuditLog).filter(
            AuditLog.student_id == student_id,
            AuditLog.section_id == target_section_id
        ).first()
        if not audit_log:
            audit_log = AuditLog(student_id=student_id, section_id=target_section_id)
            db.add(audit_log)
        audit_log.shap_result = response_data
        db.commit()

    return response_data


@router.get("/audit/anomaly-score/{student_id}")
def get_student_anomaly_score(
    student_id: int,
    section_id: Optional[int] = Query(None, description="Scope Isolation Forest to section peer distribution"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    if current_user.role == UserRole.STUDENT and student.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    target_section_id = section_id or student.section_id
    if target_section_id:
        audit_log = db.query(AuditLog).filter(
            AuditLog.student_id == student_id,
            AuditLog.section_id == target_section_id
        ).first()
        if audit_log and audit_log.anomaly_result:
            return audit_log.anomaly_result

    anomaly_svc = get_anomaly_detection_service()

    # Always compute global score first (backward-compatible)
    global_result = anomaly_svc.evaluate_student_anomaly_global(
        resume_text=student.raw_resume_text or "",
        skills=student.skills or [],
        projects=student.projects or [],
    )

    if section_id is None:
        # Pure global mode
        return {
            "student_id": student.id,
            "roll_number": student.roll_number,
            "student_name": student.full_name,
            "scope": "global",
            "anomaly_audit": global_result,
        }

    # Scoped mode: also run against section peer distribution
    section = db.query(Section).filter(Section.id == section_id).first()
    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found.")

    peer_students = _get_section_peers(section_id, student_id, db)

    scoped_result = anomaly_svc.evaluate_student_anomaly(
        resume_text=student.raw_resume_text or "",
        skills=student.skills or [],
        projects=student.projects or [],
        peer_students=peer_students,
    )

    # Delta shows how much the scoped score diverges from global
    delta = round(scoped_result["anomaly_score"] - global_result["anomaly_score"], 3)

    response_data = {
        "student_id": student.id,
        "roll_number": student.roll_number,
        "student_name": student.full_name,
        "scope": f"section:{section_id}",
        "section_name": section.name,
        "peer_count": len(peer_students),
        # Side-by-side comparison as required
        "global_anomaly_score": global_result["anomaly_score"],
        "scoped_anomaly_score": scoped_result["anomaly_score"],
        "score_delta": delta,
        "delta_direction": "more_anomalous_in_section" if delta > 0 else ("less_anomalous_in_section" if delta < 0 else "identical"),
        # Full scoped audit (primary result when section_id provided)
        "anomaly_audit": scoped_result,
        # Global audit included for full transparency
        "global_audit": global_result,
    }

    if target_section_id:
        audit_log = db.query(AuditLog).filter(
            AuditLog.student_id == student_id,
            AuditLog.section_id == target_section_id
        ).first()
        if not audit_log:
            audit_log = AuditLog(student_id=student_id, section_id=target_section_id)
            db.add(audit_log)
        audit_log.anomaly_result = response_data
        db.commit()

    return response_data



@router.get("/explain/improve/{student_id}")
def get_student_match_improvement_suggestions(
    student_id: int,
    section_id: Optional[int] = Query(None, description="Scope recommendations against section peer SHAP distribution"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    if current_user.role == UserRole.STUDENT and student.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    peer_students = None
    scope_meta = {"scope": "global"}
    if section_id is not None:
        section = db.query(Section).filter(Section.id == section_id).first()
        if not section:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found.")
        peer_students = _get_section_peers(section_id, student_id, db)
        scope_meta = {
            "scope": f"section:{section_id}",
            "section_name": section.name,
            "peer_count": len(peer_students),
        }

    shap_svc = get_shap_comparison_service()
    suggestions = shap_svc.generate_recommendations(
        resume_text=student.raw_resume_text or "",
        skills=student.skills or [],
        projects=student.projects or [],
        target_domain=student.predicted_domain,
        peer_students=peer_students,
    )

    return {
        "student_id": student.id,
        "roll_number": student.roll_number,
        "student_name": student.full_name,
        **scope_meta,
        "improvement_analysis": suggestions,
    }
