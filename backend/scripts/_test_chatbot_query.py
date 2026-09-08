import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.core.database import SessionLocal
from backend.app.models.student import Student
from backend.app.models.user import User
from backend.app.api.v1.chatbot import answer_student_explainability_query, ChatQuery

def test_chatbot():
    db = SessionLocal()
    student = db.query(Student).first()
    if not student:
        print("[!] No student found.")
        return

    user = student.user
    print(f"\n--- TESTING CHATBOT ENDPOINT FOR STUDENT '{student.full_name}' (user_id: {user.id}) ---")

    queries = [
        "Why was I matched to this domain?",
        "What does my SHAP score mean?",
        "Is my profile flagged for anomaly audit?",
        "How can I improve my placement match?"
    ]

    for q in queries:
        try:
            payload = ChatQuery(query=q)
            res = answer_student_explainability_query(payload=payload, current_user=user, db=db)
            print(f"\n[OK] Query: '{q}'")
            print(f"     Answer: {res['answer'][:120]}...")
        except Exception as e:
            print(f"\n[ERROR] Query: '{q}' failed with Exception:")
            import traceback
            traceback.print_exc()

    db.close()

if __name__ == "__main__":
    test_chatbot()
