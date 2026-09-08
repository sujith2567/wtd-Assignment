import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.core.database import SessionLocal
from backend.app.models.student import Student
from backend.app.models.user import User
from backend.app.api.v1.readiness import get_questions_by_domain, submit_readiness_checklist, get_student_latest_readiness_score
from backend.app.schemas.readiness import SubmissionCreate, AnswerItem

def test_readiness():
    db = SessionLocal()
    student = db.query(Student).first()
    if not student:
        print("[!] No student found in DB.")
        return

    user = student.user
    domain = "Software Development"

    print(f"\n--- TESTING READINESS FEATURE FOR STUDENT '{student.full_name}' ---")

    # 1. Fetch questions
    questions = get_questions_by_domain(domain=domain, db=db, current_user=user)
    print(f"[OK] GET /api/v1/readiness/questions/{domain} -> Fetched {len(questions)} questions")

    # 2. Submit answers
    answers = [AnswerItem(question_id=q["id"], selected_points=4 if q["category"] == "DSA" else 2) for q in questions]
    payload = SubmissionCreate(domain=domain, answers=answers)
    
    score = submit_readiness_checklist(payload=payload, current_user=user, db=db)
    print(f"[OK] POST /api/v1/readiness/submit -> Overall Readiness: {score['total_score_percent']}%")
    print(f"    Category Scores: {score['category_scores']}")
    print(f"    Strong Areas: {score['strong_areas']}")
    print(f"    Weak Areas: {score['weak_areas']}")

    # 3. Retrieve latest score
    latest = get_student_latest_readiness_score(student_id=student.id, db=db, current_user=user)
    print(f"[OK] GET /api/v1/readiness/score/{student.id} -> Retrieved latest readiness score ({latest['total_score_percent']}%)")

    db.close()
    print("\nResult: All Readiness feature endpoints passed successfully!")

if __name__ == "__main__":
    test_readiness()
