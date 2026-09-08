import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.core.database import SessionLocal
from backend.app.models.user import User, UserRole
from backend.app.models.student import Student
from backend.app.models.job import JobPosting, JobStatus
from backend.app.models.company import Company
from backend.app.core.security import get_password_hash
from backend.app.schemas.student import StudentResponse
from backend.app.schemas.job import JobPostingResponse
from backend.app.services.classifier_service import get_classifier_service
from backend.app.api.v1.students import get_own_student_profile, list_students, get_student_by_id
from backend.app.api.v1.jobs import list_active_jobs, get_recruiter_jobs
from backend.app.api.v1.matching import evaluate_baseline_candidates, get_student_domain_explanation
from backend.app.api.v1.interviews import get_own_student_interviews, list_interview_records

def run_regression_and_edge_cases():
    print("==================================================================")
    print("STABILIZATION & REGRESSION PASS (ALL 3 ROLES + EDGE CASES)")
    print("==================================================================")

    db = SessionLocal()

    # Fetch role users
    admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
    recruiter = db.query(User).filter(User.role == UserRole.RECRUITER).first()
    student_user = db.query(User).filter(User.role == UserRole.STUDENT).first()
    student = db.query(Student).filter(Student.user_id == student_user.id).first()

    # 1. Edge Case: Empty / Minimal Student Profile Classification
    print("\n[EDGE CASE 1] Classifier handling for blank resume & empty skills...")
    clf = get_classifier_service()
    res_empty = clf.predict_and_explain(resume_text="", skills=[], projects=[])
    assert "predicted_domain" in res_empty
    assert "confidence" in res_empty
    summary_empty = clf.build_human_readable_summary(
        res_empty["predicted_domain"], res_empty["confidence"], res_empty["explainability"]
    )
    print(f"  --> Empty Profile Classified: Domain='{res_empty['predicted_domain']}', Confidence={res_empty['confidence']*100:.0f}%")
    print(f"      Fallback Summary: '{summary_empty}'")

    # 2. Edge Case: Job with Impossible Criteria (0 Candidates)
    print("\n[EDGE CASE 2] Candidate shortlist evaluation for job with CGPA=10.0 & Backlogs=0...")
    # Create temporary impossible job
    imp_job = JobPosting(
        company_id=1,
        title="Unreachable Benchmark Role",
        target_domain="Software Development",
        description="Testing 0 candidate match edge case",
        min_cgpa=9.99,
        max_backlogs_allowed=0,
        required_skills=["QuantumComputing", "NonExistentSkill123"],
        status=JobStatus.ACTIVE
    )
    db.add(imp_job)
    db.commit()
    db.refresh(imp_job)

    shortlist_imp = evaluate_baseline_candidates(
        job_id=imp_job.id, limit=50, include_buffer=True, buffer_min_confidence=0.99, current_user=recruiter, db=db
    )
    print(f"  --> Shortlist for Impossible Job #{imp_job.id}: Total Matches={len(shortlist_imp.matches)}, Strict={shortlist_imp.strict_matches_count}, Buffer={shortlist_imp.buffer_matches_count}")
    assert shortlist_imp.strict_matches_count == 0 or len(shortlist_imp.matches) == 0

    # Cleanup temporary job
    db.delete(imp_job)
    db.commit()

    # 3. Role 1 (Admin) Regression Pass
    print("\n[ROLE 1: ADMIN REGRESSION]")
    studs = list_students(skip=0, limit=10, current_user=admin, db=db)
    print(f"  - Admin Students List: Retrieved {len(studs)} students with full_name='{studs[0].full_name}'")
    
    jobs = list_active_jobs(skip=0, limit=10, current_user=admin, db=db)
    print(f"  - Admin Jobs List: Retrieved {len(jobs)} jobs with company_name='{jobs[0].company_name}'")

    ints = list_interview_records(job_id=None, student_id=None, current_user=admin, db=db)
    print(f"  - Admin Interviews List: Retrieved {len(ints)} campus interview records")

    # 4. Role 2 (Recruiter) Regression Pass
    print("\n[ROLE 2: RECRUITER REGRESSION]")
    my_j = get_recruiter_jobs(current_user=recruiter, db=db)
    print(f"  - Recruiter My Jobs: Retrieved {len(my_j)} job postings")
    
    recruiter_job_id = my_j[0].id
    shortlist_r = evaluate_baseline_candidates(job_id=recruiter_job_id, limit=200, include_buffer=True, current_user=recruiter, db=db)
    print(f"  - Recruiter Shortlist (Job #{recruiter_job_id}): {shortlist_r.strict_matches_count} Strict, {shortlist_r.buffer_matches_count} Buffer")

    # 5. Role 3 (Student) Regression Pass
    print("\n[ROLE 3: STUDENT REGRESSION]")
    prof = get_own_student_profile(current_user=student_user, db=db)
    print(f"  - Student Profile: Name='{prof.full_name}', CGPA={prof.cgpa}")
    
    expl = get_student_domain_explanation(student_id=prof.id, current_user=student_user, db=db)
    print(f"  - Student AI Explanation: Domain='{expl.predicted_domain}', Confidence={expl.confidence_score*100:.1f}%")
    
    my_ints = get_own_student_interviews(current_user=student_user, db=db)
    print(f"  - Student Interviews: Retrieved {len(my_ints)} personal interview outcomes")

    print("\n==================================================================")
    print("ALL EDGE CASES & REGRESSION CHECKS PASSED WITH CODE 0!")
    print("==================================================================")

if __name__ == "__main__":
    run_regression_and_edge_cases()
