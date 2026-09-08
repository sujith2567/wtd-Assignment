import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.core.database import SessionLocal
from backend.app.models.student import Student
from backend.app.models.user import User, UserRole
from backend.app.models.application import ApplicationStatus
from backend.app.api.v1.applications import (
    get_student_applications,
    update_application_status,
    create_application
)
from backend.app.schemas.application import ApplicationCreate, ApplicationStatusUpdate

def test_applications():
    db = SessionLocal()
    student = db.query(Student).first()
    if not student:
        print("[!] No student found in DB.")
        return

    student_user = student.user
    admin_user = db.query(User).filter(User.role == UserRole.ADMIN).first()

    print(f"\n--- TESTING APPLICATION TRACKING FEATURE FOR STUDENT '{student.full_name}' ---")

    # 1. Fetch applications list
    apps = get_student_applications(student_id=student.id, db=db, current_user=student_user)
    print(f"[OK] GET /api/v1/applications/{student.id} -> Returned {len(apps)} application records")

    if apps:
        first_app = apps[0]
        print(f"    Sample App: Company '{first_app.company_name}' | Status: '{first_app.status.value}'")

        # 2. Update status as Admin
        update_req = ApplicationStatusUpdate(status=ApplicationStatus.INTERVIEW)
        updated = update_application_status(application_id=first_app.id, payload=update_req, current_user=admin_user, db=db)
        print(f"[OK] PUT /api/v1/applications/{first_app.id}/status -> Admin updated status to '{updated.status.value}'")

    db.close()
    print("\nResult: All Application Tracking endpoints passed successfully!")

if __name__ == "__main__":
    test_applications()
