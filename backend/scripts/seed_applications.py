import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.core.database import SessionLocal
from backend.app.models.student import Student
from backend.app.models.job import JobPosting
from backend.app.models.application import Application, ApplicationStatus

def seed_applications():
    db = SessionLocal()
    
    existing_count = db.query(Application).count()
    if existing_count > 0:
        print(f"[*] Applications already seeded ({existing_count} records). Skipping.")
        db.close()
        return

    student = db.query(Student).first()
    if not student:
        print("[!] No student found to seed applications.")
        db.close()
        return

    jobs = db.query(JobPosting).limit(4).all()

    sample_apps = [
        {
            "student_id": student.id,
            "job_id": jobs[0].id if len(jobs) > 0 else None,
            "company_name": "Google",
            "status": ApplicationStatus.INTERVIEW
        },
        {
            "student_id": student.id,
            "job_id": jobs[1].id if len(jobs) > 1 else None,
            "company_name": "Microsoft",
            "status": ApplicationStatus.OFFER
        },
        {
            "student_id": student.id,
            "job_id": jobs[2].id if len(jobs) > 2 else None,
            "company_name": "Amazon",
            "status": ApplicationStatus.SHORTLISTED
        },
        {
            "student_id": student.id,
            "job_id": jobs[3].id if len(jobs) > 3 else None,
            "company_name": "Deloitte",
            "status": ApplicationStatus.APPLIED
        },
    ]

    print(f"[*] Seeding {len(sample_apps)} application tracking records for student '{student.full_name}'...")
    for app_dict in sample_apps:
        app_rec = Application(**app_dict)
        db.add(app_rec)
    
    db.commit()
    db.close()
    print(" -> Application tracking records successfully seeded!")

if __name__ == "__main__":
    seed_applications()
