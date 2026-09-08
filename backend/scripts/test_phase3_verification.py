import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.core.database import SessionLocal
from backend.app.models.user import User, UserRole
from backend.app.models.company import Company
from backend.app.models.student import Student
from backend.app.models.job import JobPosting
from backend.app.core.security import get_password_hash
from backend.app.schemas.student import StudentResponse
from backend.app.schemas.job import JobPostingResponse, JobPostingCreate
from backend.app.api.v1.students import list_students
from backend.app.api.v1.jobs import list_active_jobs, create_job_posting, get_recruiter_jobs
from backend.app.api.v1.matching import evaluate_baseline_candidates

def run_verification():
    print("==================================================================")
    print("PHASE 3 VERIFICATION & END-TO-END SUITE (DIRECT API VALIDATION)")
    print("==================================================================")

    db = SessionLocal()

    # 1. Setup Test Recruiter & Admin users in DB if needed
    admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
    if not admin:
        admin = User(
            email="admin_test@placematch.edu",
            hashed_password=get_password_hash("password123"),
            full_name="Dr. Placement Director",
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

    recruiter = db.query(User).filter(User.role == UserRole.RECRUITER).first()
    if not recruiter:
        recruiter = User(
            email="recruiter_test@techcorp.com",
            hashed_password=get_password_hash("password123"),
            full_name="Sarah Jenkins",
            role=UserRole.RECRUITER,
            is_active=True
        )
        db.add(recruiter)
        db.commit()
        db.refresh(recruiter)

    # Ensure recruiter company exists
    company = db.query(Company).filter(Company.user_id == recruiter.id).first()
    if not company:
        company = Company(
            user_id=recruiter.id,
            company_name="Acme Tech Innovations",
            contact_email=recruiter.email,
            industry="Software & AI"
        )
        db.add(company)
        db.commit()
        db.refresh(company)

    # ------------------------------------------------------------------
    # TEST 1: Students Endpoint Schema Fix (full_name)
    # ------------------------------------------------------------------
    print("\n[TEST 1] Testing list_students endpoint for full_name inclusion...")
    students_raw = list_students(skip=0, limit=5, current_user=admin, db=db)
    students_serialized = [StudentResponse.model_validate(s) for s in students_raw]
    assert len(students_serialized) > 0, "No students found in DB!"
    s0 = students_serialized[0]
    assert hasattr(s0, "full_name") and s0.full_name is not None, "full_name missing from StudentResponse!"
    print(f"  [PASS]: StudentResponse contains full_name ('{s0.full_name}')")

    # ------------------------------------------------------------------
    # TEST 2: Jobs Endpoint Schema Fix (company_name)
    # ------------------------------------------------------------------
    print("\n[TEST 2] Testing list_active_jobs endpoint for company_name inclusion...")
    jobs_raw = list_active_jobs(skip=0, limit=5, current_user=admin, db=db)
    jobs_serialized = [JobPostingResponse.model_validate(j) for j in jobs_raw]
    assert len(jobs_serialized) > 0, "No active jobs found in DB!"
    j0 = jobs_serialized[0]
    assert hasattr(j0, "company_name"), "company_name missing from JobPostingResponse!"
    print(f"  [PASS]: JobPostingResponse contains company_name ('{j0.company_name}')")

    # ------------------------------------------------------------------
    # TEST 3: Post Job Endpoint (Recruiter)
    # ------------------------------------------------------------------
    print("\n[TEST 3] Creating a new job posting via create_job_posting endpoint...")
    new_job_create = JobPostingCreate(
        title="AI Systems Architect",
        target_domain="Software Development",
        description="Designing scalable cloud infrastructure and ML pipelines.",
        min_cgpa=7.00,
        max_backlogs_allowed=0,
        required_skills=["Python", "FastAPI", "Docker"],
        preferred_skills=["Kubernetes", "AWS"],
        salary_range="12 - 18 LPA",
        location="Bengaluru, KA",
        buffer_threshold_percent=10.0
    )
    created_job_orm = create_job_posting(job_in=new_job_create, current_user=recruiter, db=db)
    created_job = JobPostingResponse.model_validate(created_job_orm)
    assert created_job.title == "AI Systems Architect"
    assert created_job.company_name == company.company_name, f"Expected {company.company_name}, got {created_job.company_name}"
    print(f"  [PASS]: Job #{created_job.id} posted successfully with company_name='{created_job.company_name}'")

    # ------------------------------------------------------------------
    # TEST 4: My Jobs Endpoint (Recruiter)
    # ------------------------------------------------------------------
    print("\n[TEST 4] Fetching recruiter jobs via get_recruiter_jobs endpoint...")
    my_jobs_raw = get_recruiter_jobs(current_user=recruiter, db=db)
    my_jobs = [JobPostingResponse.model_validate(j) for j in my_jobs_raw]
    assert any(j.id == created_job.id for j in my_jobs), f"Created job #{created_job.id} not found in my_jobs!"
    print(f"  [PASS]: Recruiter has {len(my_jobs)} job(s) listed under '{company.company_name}'")

    # ------------------------------------------------------------------
    # TEST 5: Candidate Shortlist with Adaptive Buffer Match
    # ------------------------------------------------------------------
    print(f"\n[TEST 5] Evaluating candidate shortlist for Job #{created_job.id} with include_buffer=True...")
    shortlist = evaluate_baseline_candidates(
        job_id=created_job.id,
        limit=50,
        include_buffer=True,
        buffer_min_confidence=0.70,
        current_user=recruiter,
        db=db
    )

    tot_eval = shortlist.total_candidates_evaluated
    strict_cnt = shortlist.strict_matches_count
    buffer_cnt = shortlist.buffer_matches_count
    matches = shortlist.matches

    print(f"  - Total Candidates Evaluated: {tot_eval}")
    print(f"  - Strict Matches Count:      {strict_cnt}")
    print(f"  - Buffer Matches Count:      {buffer_cnt}")
    print(f"  - Total Shortlist Returned:  {len(matches)}")

    strict_tier = [m for m in matches if m.match_tier == "strict_match"]
    buffer_tier = [m for m in matches if m.match_tier == "buffer_match"]

    print(f"  - Strict Tier Candidates: {len(strict_tier)}")
    print(f"  - Buffer Tier Candidates: {len(buffer_tier)}")

    if strict_tier:
        s_sample = strict_tier[0]
        assert s_sample.full_name, "Candidate full_name is missing!"
        print(f"  [PASS]: Sample Strict Candidate: '{s_sample.full_name}' (CGPA={s_sample.cgpa}, Score={s_sample.overall_score})")

    if buffer_tier:
        b_sample = buffer_tier[0]
        assert b_sample.full_name, "Buffer candidate full_name is missing!"
        assert b_sample.domain_fit_score > 0, "Buffer candidate must have positive domain_fit_score!"
        assert b_sample.score_breakdown, "Buffer candidate must have score_breakdown!"
        print(f"  [PASS]: Sample Buffer Candidate (AI Promoted): '{b_sample.full_name}' (CGPA={b_sample.cgpa}, Domain Fit={b_sample.domain_fit_score*100:.0f}%, Reason='{b_sample.reason}')")

    print("\n==================================================================")
    print("ALL PHASE 3 VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("==================================================================")

if __name__ == "__main__":
    run_verification()
