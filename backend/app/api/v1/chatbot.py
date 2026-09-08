from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import get_current_user
from backend.app.models.user import User, UserRole
from backend.app.models.student import Student
from backend.app.services.classifier_service import get_classifier_service
from backend.app.services.shap_service import get_shap_comparison_service
from backend.app.services.anomaly_service import get_anomaly_detection_service

router = APIRouter(prefix="/students/chatbot", tags=["Student AI Chatbot"])

class ChatQuery(BaseModel):
    query: str

class ChatResponse(BaseModel):
    query: str
    answer: str
    context_summary: str

@router.post("/query", response_model=ChatResponse)
def answer_student_explainability_query(
    payload: ChatQuery,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Explainability Chatbot is accessible to logged-in students."
        )

    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found.")

    # Fetch context for this student ONLY
    clf = get_classifier_service()
    explanation = clf.predict_and_explain(
        resume_text=student.raw_resume_text or "",
        skills=student.skills or [],
        projects=student.projects or []
    )

    shap_svc = get_shap_comparison_service()
    shap_analysis = shap_svc.compute_shap_comparison(
        resume_text=student.raw_resume_text or "",
        skills=student.skills or [],
        projects=student.projects or [],
        target_domain=explanation["predicted_domain"]
    )

    anomaly_svc = get_anomaly_detection_service()
    anomaly_audit = anomaly_svc.evaluate_student_anomaly(
        resume_text=student.raw_resume_text or "",
        skills=student.skills or [],
        projects=student.projects or []
    )

    q = payload.query.lower().strip()

    # Contextual synthesis based strictly on this student's data
    predicted_domain = explanation["predicted_domain"]
    confidence_pct = f"{explanation['confidence'] * 100:.1f}%"
    top_skills = [f["feature"] for f in explanation["explainability"][:3]]
    top_skills_str = ", ".join(top_skills) if top_skills else "skills & project descriptions"

    if "shap" in q or "feature" in q or "contribution" in q:
        answer = (
            f"Your SHAP (SHapley Additive exPlanations) analysis measures how much each claimed skill pushes "
            f"the AI model toward '{predicted_domain}'. For your profile, your highest SHAP-supported skills are: "
            f"{', '.join(shap_analysis['well_supported_skills'][:5]) if shap_analysis['well_supported_skills'] else top_skills_str}. "
            f"Your database coverage score is {shap_analysis['database_coverage_score'] * 100:.0f}%."
        )
        if shap_analysis['outlier_or_exaggerated_skills']:
            answer += f" Note: Outlier terms detected in your profile include: {', '.join(shap_analysis['outlier_or_exaggerated_skills'])}."

    elif "why" in q or "domain" in q or "classified" in q or "matched" in q or "label" in q:
        answer = (
            f"You were classified into **{predicted_domain}** with a confidence score of **{confidence_pct}**. "
            f"The primary positive evidence driving this classification consists of: {top_skills_str}. "
            f"The classifier concatenated your resume text, skills inventory ({len(student.skills or [])} listed), and projects."
        )

    elif "anomaly" in q or "flag" in q or "audit" in q or "fake" in q or "score" in q or "integrity" in q:
        status_text = "NORMAL (Approved for pipeline)" if not anomaly_audit["is_anomalous"] else "FLAGGED FOR ADMIN AUDIT"
        answer = (
            f"Your profile's Isolation Forest anomaly score is **{anomaly_audit['anomaly_score']} / 1.0** (Status: **{status_text}**). "
            f"{anomaly_audit['recommendation']}. "
            f"Reasons: {'; '.join(anomaly_audit['anomaly_reasons'])}."
        )

    elif "improve" in q or "cgpa" in q or "recommend" in q or "better" in q or "help" in q:
        answer = (
            f"To boost your match strength for {predicted_domain}: "
            f"1. Add more domain-specific projects highlighting technologies like {top_skills_str}. "
            f"2. Ensure your resume text clearly details technical implementations rather than general statements. "
            f"3. Maintain your CGPA (currently {float(student.cgpa):.2f}) and keep active backlogs at {student.active_backlogs}."
        )

    else:
        answer = (
            f"Here is your AI classification summary for {student.full_name}: "
            f"Domain: **{predicted_domain}** ({confidence_pct} confidence). "
            f"Top attribution factors: {top_skills_str}. "
            f"Anomaly Status: {anomaly_audit['audit_status']}. "
            f"Feel free to ask 'Why was I matched to this domain?', 'What does my SHAP score mean?', or 'Is my profile flagged?'."
        )

    context_summary = f"Student: {student.full_name} | Domain: {predicted_domain} ({confidence_pct}) | Anomaly Score: {anomaly_audit['anomaly_score']}"

    return {
        "query": payload.query,
        "answer": answer,
        "context_summary": context_summary
    }
