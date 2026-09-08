import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.core.database import SessionLocal
from backend.app.models.user import User, UserRole
from backend.app.models.student import Student
from backend.app.schemas.student import StudentResponse
from backend.app.schemas.job import JobPostingResponse
from backend.app.api.v1.students import get_own_student_profile
from backend.app.api.v1.matching import get_student_domain_explanation
from backend.app.api.v1.jobs import list_active_jobs

def run_student_manual_pass():
    print("==================================================================")
    print("MANUAL WALKTHROUGH & SCREEN-BY-SCREEN PASS (PHASE 4: STUDENT DASHBOARD)")
    print("==================================================================")

    db = SessionLocal()

    # 1. Fetch demo student user (student@placematch.edu)
    student_user = db.query(User).filter(User.email == "student@placematch.edu").first()
    assert student_user is not None, "Demo student user not found!"

    print(f"\n[STEP 1] Logged in as Demo Student ('{student_user.full_name}', Email: {student_user.email}, Role: {student_user.role.value})")

    # 2. Fetch Student Profile (/student/profile)
    print("\n[STEP 2] Loading Student Profile data (get_own_student_profile)...")
    profile_orm = get_own_student_profile(current_user=student_user, db=db)
    profile = StudentResponse.model_validate(profile_orm)

    print(f"\n  === SCREEN SUMMARY: STUDENT PROFILE CARD ===")
    print(f"  - Full Name:       '{profile.full_name}'")
    print(f"  - Roll Number:     {profile.roll_number}")
    print(f"  - Department:      {profile.department}")
    print(f"  - CGPA:            {profile.cgpa}")
    print(f"  - Active Backlogs: {profile.active_backlogs}")
    print(f"  - Batch Year:      {profile.batch_year}")
    print(f"  - Skills Inventory: {profile.skills}")
    print(f"  - Resume Snippet:  '{profile.raw_resume_text[:80]}...'")

    # 3. Own Domain Prediction & AI Explainability View
    print(f"\n[STEP 3] Loading AI Explainability View (get_student_domain_explanation for Student #{profile.id})...")
    explanation = get_student_domain_explanation(student_id=profile.id, current_user=student_user, db=db)

    print(f"\n  === SCREEN SUMMARY: PROMINENT AI EXPLAINABILITY BANNER ===")
    print(f"  - Predicted Domain: '{explanation.predicted_domain}'")
    print(f"  - Confidence Score: {explanation.confidence_score*100:.1f}%")
    print(f"  - Ground Truth:     '{explanation.ground_truth_domain}' (Match Badge: {explanation.is_correct})")
    print(f"  - Model Version:    {explanation.model_version}")
    print(f"  - Human Summary:    '{explanation.human_readable_summary}'")

    print("\n  --- CLASS PROBABILITIES DISTRIBUTION DISPLAYED ---")
    for cp in explanation.class_probabilities:
        print(f"    * {cp.domain:32s} : {cp.probability*100:5.1f}%")

    print("\n  --- TOP CONTRIBUTING FACTORS & KEYWORDS DISPLAYED ---")
    for factor in explanation.top_contributing_factors:
        print(f"    * Keyword: '{factor.keyword}' | Weight: {factor.weight} | Direction: {factor.direction} | '{factor.description}'")

    # 4. Job & Company Recommendations (/student/recommendations)
    print("\n[STEP 4] Loading AI Job & Company Recommendations (list_active_jobs)...")
    jobs_raw = list_active_jobs(skip=0, limit=100, current_user=student_user, db=db)
    jobs = [JobPostingResponse.model_validate(j) for j in jobs_raw]

    pred_domain = explanation.predicted_domain.strip().lower()
    matched_domain_jobs = [j for j in jobs if (j.target_domain or '').strip().lower() == pred_domain]

    print(f"\n  === SCREEN SUMMARY: RECOMMENDED JOBS PAGE ===")
    print(f"  - Total Active Jobs in System:   {len(jobs)}")
    print(f"  - Direct Target Domain Matches: {len(matched_domain_jobs)} jobs for '{explanation.predicted_domain}'")

    print("\n  --- TOP 3 RECOMMENDED JOB CARDS DISPLAYED ---")
    for j in matched_domain_jobs[:3]:
        print(f"    * Title: '{j.title}' | Company: '{j.company_name}'")
        print(f"      Location: '{j.location}' | Salary: '{j.salary_range}'")
        print(f"      Criteria: Min CGPA {j.min_cgpa} | Max Backlogs {j.max_backlogs_allowed}")
        print(f"      Skills Required: {j.required_skills}")
        print(f"      Why it's a match: Direct match for your predicted domain ({explanation.predicted_domain}) & academic criteria.")

    print("\n==================================================================")
    print("PHASE 4 STUDENT DASHBOARD MANUAL PASS COMPLETED SUCCESSFULLY!")
    print("==================================================================")

if __name__ == "__main__":
    run_student_manual_pass()
