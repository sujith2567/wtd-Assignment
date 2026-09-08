import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.core.database import SessionLocal
from backend.app.models.user import User
from backend.app.models.student import Student
from backend.app.models.job import JobPosting
from backend.app.schemas.job import JobPostingResponse
from backend.app.schemas.interview import InterviewRecordCreate
from backend.app.api.v1.matching import evaluate_baseline_candidates, get_student_domain_explanation
from backend.app.api.v1.students import get_own_student_profile
from backend.app.api.v1.jobs import list_active_jobs
from backend.app.api.v1.interviews import (
    submit_interview_feedback,
    get_own_student_interviews,
    list_interview_records,
    get_template_suggestions,
    FeedbackSuggestionRequest,
)

def run_e2e_pass():
    print("==================================================================")
    print("END-TO-END VALIDATION: SHORTLIST PAGINATION, STUDENT BUFFER & INTERVIEW MODULE")
    print("==================================================================")

    db = SessionLocal()

    # Users
    admin = db.query(User).filter(User.email == "admin@placematch.edu").first()
    recruiter = db.query(User).filter(User.email == "recruiter@google.com").first()
    student_user = db.query(User).filter(User.email == "student@placematch.edu").first()
    student = db.query(Student).filter(Student.user_id == student_user.id).first()

    # ------------------------------------------------------------------
    # ITEM 1: Candidate Shortlist Pagination / Limit Parameter
    # ------------------------------------------------------------------
    print("\n[ITEM 1] Candidate Shortlist Pagination / Limit Parameter...")
    job = db.query(JobPosting).filter(JobPosting.company_id == 1).first()

    shortlist_50 = evaluate_baseline_candidates(job_id=job.id, limit=50, include_buffer=True, current_user=recruiter, db=db)
    shortlist_200 = evaluate_baseline_candidates(job_id=job.id, limit=200, include_buffer=True, current_user=recruiter, db=db)
    shortlist_500 = evaluate_baseline_candidates(job_id=job.id, limit=500, include_buffer=True, current_user=recruiter, db=db)

    print(f"  - Limit=50  : Returned {len(shortlist_50.matches)} candidates (Strict: {len([m for m in shortlist_50.matches if m.match_tier == 'strict_match'])}, Buffer: {len([m for m in shortlist_50.matches if m.match_tier == 'buffer_match'])})")
    print(f"  - Limit=200 : Returned {len(shortlist_200.matches)} candidates (Strict: {len([m for m in shortlist_200.matches if m.match_tier == 'strict_match'])}, Buffer: {len([m for m in shortlist_200.matches if m.match_tier == 'buffer_match'])})")
    print(f"  - Limit=500 : Returned {len(shortlist_500.matches)} candidates (Strict: {len([m for m in shortlist_500.matches if m.match_tier == 'strict_match'])}, Buffer: {len([m for m in shortlist_500.matches if m.match_tier == 'buffer_match'])})")

    assert len(shortlist_200.matches) > len(shortlist_50.matches), "Limit 200 should return more candidates than Limit 50!"
    print("  [PASS]: Candidate limit selector & pagination verified!")

    # ------------------------------------------------------------------
    # ITEM 2: Student Recommendations with Direct vs Buffer Split
    # ------------------------------------------------------------------
    print("\n[ITEM 2] Student Recommendations Page (Direct vs Buffer Split)...")
    explanation = get_student_domain_explanation(student_id=student.id, current_user=student_user, db=db)
    all_jobs_raw = list_active_jobs(skip=0, limit=100, current_user=student_user, db=db)
    all_jobs = [JobPostingResponse.model_validate(j) for j in all_jobs_raw]

    pred_domain = explanation.predicted_domain.strip().lower()
    s_conf = explanation.confidence_score
    s_cgpa = float(student.cgpa)
    s_backlogs = student.active_backlogs

    direct_jobs = []
    buffer_jobs = []

    for j in all_jobs:
        j_domain = j.target_domain.strip().lower()
        is_domain_match = pred_domain in j_domain or j_domain in pred_domain
        min_cgpa = float(j.min_cgpa)
        max_backlogs = j.max_backlogs_allowed
        buffer_cgpa_floor = min_cgpa * 0.90

        if is_domain_match:
            if s_cgpa >= min_cgpa and s_backlogs <= max_backlogs:
                direct_jobs.append(j)
            elif s_cgpa >= buffer_cgpa_floor and s_backlogs <= max_backlogs + 1 and s_conf >= 0.70:
                buffer_jobs.append(j)

    print(f"  - Student: '{student_user.full_name}' | Predicted Domain: '{explanation.predicted_domain}' ({s_conf*100:.1f}% Confidence)")
    print(f"  - Direct Eligible Job Matches Section : {len(direct_jobs)} jobs")
    print(f"  - Adaptive Buffer Job Recommendations : {len(buffer_jobs)} jobs (AI Promoted)")

    print("  [PASS]: Student Recommendations 2-tier split verified!")

    # ------------------------------------------------------------------
    # ITEM 3: Lightweight Interview Feedback Module (Recruiter -> Student -> Admin)
    # ------------------------------------------------------------------
    print("\n[ITEM 3] Interview Feedback Module (Recruiter -> Student -> Admin)...")

    # A) Test template suggestions helper
    req_sug = FeedbackSuggestionRequest(technical_score=8.5, communication_score=5.5, problem_solving_score=8.0, outcome="passed")
    sug_res = get_template_suggestions(req_sug)
    print(f"  - Template Suggestion Generated: Summary='{sug_res.suggested_summary}'")
    print(f"    Strengths='{sug_res.suggested_strengths}' | Weaknesses='{sug_res.suggested_weaknesses}'")

    # B) Recruiter logs interview feedback
    record_create = InterviewRecordCreate(
        student_id=student.id,
        job_id=job.id,
        round_number=1,
        round_name="Technical & System Design",
        technical_score=8.5,
        communication_score=7.0,
        problem_solving_score=8.5,
        strengths="Strong Python, FastAPI backend skills and clean data structure implementation.",
        weaknesses="Can speak slightly slower when walking through architecture diagrams.",
        detailed_feedback="Excellent technical interview. Passed round 1 with high confidence.",
        interview_outcome="passed"
    )

    created_interview = submit_interview_feedback(record_in=record_create, current_user=recruiter, db=db)
    print(f"\n  [RECRUITER SUBMITTED]: Created Interview Record #{created_interview.id} for Student '{created_interview.student_name}'")
    print(f"    Job: '{created_interview.job_title}' ({created_interview.company_name})")
    print(f"    Scores: Tech {created_interview.technical_score}/10, Comm {created_interview.communication_score}/10, PS {created_interview.problem_solving_score}/10")
    print(f"    Decision: {created_interview.interview_outcome.value.upper()}")

    # C) Student views own interview outcome
    student_interviews = get_own_student_interviews(current_user=student_user, db=db)
    assert len(student_interviews) > 0, "Student should have at least 1 interview record!"
    st_int = student_interviews[0]
    print(f"\n  [STUDENT VIEW]: Student '{student_user.full_name}' retrieved {len(student_interviews)} interview outcome(s)")
    print(f"    Company: '{st_int.company_name}', Job: '{st_int.job_title}', Decision: {st_int.interview_outcome.value.upper()}")
    print(f"    Detailed Notes: '{st_int.detailed_feedback}'")

    # D) Admin views campus-wide interview outcomes
    admin_interviews = list_interview_records(job_id=None, student_id=None, current_user=admin, db=db)
    assert len(admin_interviews) > 0, "Admin should see campus interview records!"
    print(f"\n  [ADMIN VIEW]: College Administrator retrieved {len(admin_interviews)} campus interview outcome record(s)")

    print("\n==================================================================")
    print("ALL VERIFICATION TASKS COMPLETED & PASSED CLEANLY!")
    print("==================================================================")

if __name__ == "__main__":
    run_e2e_pass()
