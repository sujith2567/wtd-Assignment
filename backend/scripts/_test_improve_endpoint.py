import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.core.database import SessionLocal
from backend.app.models.student import Student
from backend.app.models.user import User
from backend.app.api.v1.audit import get_student_match_improvement_suggestions

def test_endpoint():
    db = SessionLocal()
    student = db.query(Student).first()
    if not student:
        print("[!] No student found in database.")
        return

    # Dummy admin user for permission check
    dummy_user = student.user
    
    print(f"\n--- TESTING GET /api/v1/explain/improve/{student.id} FOR REAL STUDENT '{student.full_name}' ---")
    response_data = get_student_match_improvement_suggestions(student_id=student.id, current_user=dummy_user, db=db)
    print("\nSAMPLE JSON RESPONSE:")
    print(json.dumps(response_data, indent=2))
    db.close()

if __name__ == "__main__":
    test_endpoint()
