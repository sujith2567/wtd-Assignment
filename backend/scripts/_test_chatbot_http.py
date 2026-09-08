import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.models.student import Student
from backend.app.core.security import create_access_token

def test_chatbot_http():
    client = TestClient(app)
    db = SessionLocal()
    student = db.query(Student).first()
    if not student:
        print("[!] No student found.")
        return

    user = student.user
    token = create_access_token(data={"sub": user.email, "role": user.role.value, "user_id": user.id})

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Origin": "http://localhost:5173"
    }

    print(f"\n--- TESTING HTTP POST /api/v1/students/chatbot/query FOR '{student.full_name}' ---")
    response = client.post(
        "/api/v1/students/chatbot/query",
        headers=headers,
        json={"query": "Why was I matched to this domain?"}
    )

    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"Response Body: {response.text}")

    db.close()

if __name__ == "__main__":
    test_chatbot_http()
