import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.core.database import SessionLocal
from backend.app.api.v1.auth import login
from backend.app.schemas.user import UserLogin
from backend.app.models.user import UserRole
from fastapi import HTTPException

def run_tests():
    db = SessionLocal()
    accounts = [
        ("student@placematch.edu", "password123", UserRole.STUDENT),
        ("recruiter@google.com", "password123", UserRole.RECRUITER),
        ("admin@placematch.edu", "password123", UserRole.ADMIN),
    ]

    all_roles = [UserRole.STUDENT, UserRole.RECRUITER, UserRole.ADMIN]

    print("\n--- RUNNING ROLE-MATCH LOGIN VALIDATION SUITE ---")
    passed = 0
    total = 0

    for email, pwd, actual_role in accounts:
        for selected_role in all_roles:
            total += 1
            is_correct_match = (selected_role == actual_role)
            login_req = UserLogin(email=email, password=pwd, role=selected_role)
            try:
                res = login(login_req, db=db)
                if is_correct_match:
                    print(f"[PASS] {email} with selected role '{selected_role.value}' -> 200 OK (Token generated)")
                    passed += 1
                else:
                    print(f"[FAIL] {email} with wrong role '{selected_role.value}' should have failed but returned 200 OK!")
            except HTTPException as exc:
                if not is_correct_match and exc.status_code == 403:
                    print(f"[PASS] {email} (actual: {actual_role.value}) with selected role '{selected_role.value}' -> 403 FORBIDDEN: '{exc.detail}'")
                    passed += 1
                else:
                    print(f"[FAIL] Unexpected error for {email} ({selected_role.value}): {exc.status_code} - {exc.detail}")

    db.close()
    print(f"\nResult: {passed}/{total} tests passed!")
    return passed == total

if __name__ == "__main__":
    success = run_tests()
    if not success:
        sys.exit(1)
