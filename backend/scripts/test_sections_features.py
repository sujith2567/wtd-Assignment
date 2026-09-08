import os
import sys
from fastapi.testclient import TestClient

# Ensure backend path is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.core.security import get_password_hash, create_access_token
from backend.app.models import User, UserRole, Student, Section, AuditLog


client = TestClient(app)

def run_tests():
    db = SessionLocal()
    print("=== Starting Feature Verification Tests ===")

    # Setup Test Users
    admin = db.query(User).filter(User.email == "test_admin@placematch.edu").first()
    if not admin:
        admin = User(
            email="test_admin@placematch.edu",
            hashed_password=get_password_hash("password123"),
            full_name="Test Admin",
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

    recruiter = db.query(User).filter(User.email == "test_recruiter@company.com").first()
    if not recruiter:
        recruiter = User(
            email="test_recruiter@company.com",
            hashed_password=get_password_hash("password123"),
            full_name="Test Recruiter",
            role=UserRole.RECRUITER,
            is_active=True
        )
        db.add(recruiter)
        db.commit()
        db.refresh(recruiter)

    student_user = db.query(User).filter(User.email == "test_student@placematch.edu").first()
    if not student_user:
        student_user = User(
            email="test_student@placematch.edu",
            hashed_password=get_password_hash("password123"),
            full_name="Test Student",
            role=UserRole.STUDENT,
            is_active=True
        )
        db.add(student_user)
        db.commit()
        db.refresh(student_user)

    admin_token = create_access_token({"sub": admin.email, "role": admin.role.value})
    recruiter_token = create_access_token({"sub": recruiter.email, "role": recruiter.role.value})
    student_token = create_access_token({"sub": student_user.email, "role": student_user.role.value})

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    recruiter_headers = {"Authorization": f"Bearer {recruiter_token}"}
    student_headers = {"Authorization": f"Bearer {student_token}"}

    # Clean up pre-existing test section/students if present
    old_section = db.query(Section).filter(Section.name == "Section-AI-BulkTest").first()
    if old_section:
        db.query(Student).filter(Student.section_id == old_section.id).delete()
        db.query(Section).filter(Section.id == old_section.id).delete()
        db.commit()

    for email_to_clean in ["bulk_student1@placematch.edu", "bulk_student2@placematch.edu", "bulk_student3@placematch.edu"]:
        u = db.query(User).filter(User.email == email_to_clean).first()
        if u:
            st = db.query(Student).filter(Student.user_id == u.id).first()
            if st:
                db.query(AuditLog).filter(AuditLog.student_id == st.id).delete()
                db.query(Student).filter(Student.id == st.id).delete()
            db.query(User).filter(User.id == u.id).delete()
    db.commit()

    # =========================================================================
    # TEST 1: Automatic AI Analysis on Bulk Upload (Feature 1)
    # =========================================================================

    print("\n--- TEST 1: Automatic AI Analysis on Bulk Upload ---")
    res = client.post("/api/v1/sections/", json={"name": "Section-AI-BulkTest"}, headers=admin_headers)
    if res.status_code == 201:
        section_id = res.json()["id"]
    else:
        res_list = client.get("/api/v1/sections/", headers=admin_headers)
        section_id = [s["id"] for s in res_list.json() if s["name"] == "Section-AI-BulkTest"][0]

    csv_content = """email,full_name,roll_number,department,batch_year,cgpa,active_backlogs,skills,resume_text
bulk_student1@placematch.edu,Bulk Student 1,ROLL_BULK_01,Computer Science,2025,8.8,0,"Python;FastAPI;ML","Experienced ML engineer building PyTorch models."
bulk_student2@placematch.edu,Bulk Student 2,ROLL_BULK_02,Computer Science,2025,6.9,1,"Java;SQL","Backend developer focusing on enterprise Java microservices."
bulk_student3@placematch.edu,Bulk Student 3,ROLL_BULK_03,Information Tech,2025,9.2,0,"React;TypeScript;Node.js","Full stack web developer proficient in React and Web APIs."
"""
    files = {"file": ("students.csv", csv_content, "text/csv")}
    bulk_res = client.post(f"/api/v1/sections/{section_id}/bulk-upload", files=files, headers=admin_headers)
    print(f"Bulk upload response code: {bulk_res.status_code}")
    print(f"Bulk upload result: {bulk_res.json()}")
    assert bulk_res.status_code == 200

    # Fresh session query
    db_fresh = SessionLocal()
    st1 = db_fresh.query(Student).filter(Student.roll_number == "ROLL_BULK_01").first()
    assert st1 is not None, "Student ROLL_BULK_01 should exist in DB"
    audit_log = db_fresh.query(AuditLog).filter(AuditLog.student_id == st1.id, AuditLog.section_id == section_id).first()
    assert audit_log is not None, "AuditLog entry should exist for bulk uploaded student"
    assert audit_log.anomaly_result is not None, "anomaly_result should be stored"
    assert audit_log.shap_result is not None, "shap_result should be stored"
    print("[SUCCESS] Pre-computed AuditLog entry found in DB with anomaly_result & shap_result!")


    anom_res = client.get(f"/api/v1/audit/anomaly-score/{st1.id}?section_id={section_id}", headers=admin_headers)
    assert anom_res.status_code == 200
    print(f"GET /audit/anomaly-score/{st1.id} returned scope: {anom_res.json().get('scope')}")

    # =========================================================================
    # TEST 2: Individual-vs-Database Consistency Check (Feature 2)
    # =========================================================================
    print("\n--- TEST 2: Individual-vs-Database Consistency Check ---")
    conflict_res = client.post(
        f"/api/v1/sections/{section_id}/upload-resume",
        params={
            "email": "bulk_student1@placematch.edu",
            "full_name": "Bulk Student 1 Conflict",
            "roll_number": "ROLL_BULK_01",
            "department": "Cybersecurity",
            "cgpa": 9.9,
            "active_backlogs": 0,
            "skills_csv": "Python, Docker, Cybersecurity",
            "raw_text": "Conflicting resume text with cybersecurity focus."
        },
        headers=admin_headers
    )

    print(f"Conflict test HTTP Status: {conflict_res.status_code}")
    conflict_json = conflict_res.json()
    print("Sample Conflict Response JSON Detail:")
    import json
    print(json.dumps(conflict_json, indent=2))
    assert conflict_res.status_code == 409
    assert conflict_json["detail"]["status"] == "conflict"
    assert len(conflict_json["detail"]["conflicting_fields"]) > 0

    resolve_res = client.post(
        f"/api/v1/sections/{section_id}/upload-resume",
        params={
            "email": "bulk_student1@placematch.edu",
            "full_name": "Bulk Student 1 Conflict",
            "roll_number": "ROLL_BULK_01",
            "department": "Cybersecurity",
            "cgpa": 9.9,
            "active_backlogs": 0,
            "skills_csv": "Python, Docker, Cybersecurity",
            "raw_text": "Conflicting resume text with cybersecurity focus.",
            "confirm_overwrite": True
        },
        headers=admin_headers
    )
    print(f"Resolve conflict HTTP Status: {resolve_res.status_code}")
    assert resolve_res.status_code == 200
    assert resolve_res.json()["department"] == "Cybersecurity"
    print("[SUCCESS] Conflict resolved successfully with explicit confirmation!")

    # =========================================================================
    # TEST 3: Recruiter Read-Only Permission Split (Feature 3)
    # =========================================================================
    print("\n--- TEST 3: Recruiter Read-Only vs Blocked Write Permissions ---")
    r_list = client.get("/api/v1/sections/", headers=recruiter_headers)
    print(f"Recruiter GET /sections/: {r_list.status_code} (Expected 200)")
    assert r_list.status_code == 200

    r_detail = client.get(f"/api/v1/sections/{section_id}", headers=recruiter_headers)
    print(f"Recruiter GET /sections/{section_id}: {r_detail.status_code} (Expected 200)")
    assert r_detail.status_code == 200

    r_studs = client.get(f"/api/v1/sections/{section_id}/students", headers=recruiter_headers)
    print(f"Recruiter GET /sections/{section_id}/students: {r_studs.status_code} (Expected 200)")
    assert r_studs.status_code == 200

    r_anom = client.get(f"/api/v1/audit/anomaly-score/{st1.id}?section_id={section_id}", headers=recruiter_headers)
    print(f"Recruiter GET /audit/anomaly-score/{st1.id}: {r_anom.status_code} (Expected 200)")
    assert r_anom.status_code == 200

    r_shap = client.get(f"/api/v1/explain/shap-compare/{st1.id}?section_id={section_id}", headers=recruiter_headers)
    print(f"Recruiter GET /explain/shap-compare/{st1.id}: {r_shap.status_code} (Expected 200)")
    assert r_shap.status_code == 200

    r_write1 = client.post("/api/v1/sections/", json={"name": "ForbiddenSection"}, headers=recruiter_headers)
    print(f"Recruiter POST /sections/: {r_write1.status_code} (Expected 403)")
    assert r_write1.status_code == 403

    r_write2 = client.put(f"/api/v1/sections/{section_id}/students/{st1.id}", json={"cgpa": 10.0}, headers=recruiter_headers)
    print(f"Recruiter PUT /sections/{section_id}/students/{st1.id}: {r_write2.status_code} (Expected 403)")
    assert r_write2.status_code == 403

    r_write3 = client.delete(f"/api/v1/sections/{section_id}", headers=recruiter_headers)
    print(f"Recruiter DELETE /sections/{section_id}: {r_write3.status_code} (Expected 403)")
    assert r_write3.status_code == 403

    r_write4 = client.post(f"/api/v1/sections/{section_id}/bulk-upload", files=files, headers=recruiter_headers)
    print(f"Recruiter POST /sections/{section_id}/bulk-upload: {r_write4.status_code} (Expected 403)")
    assert r_write4.status_code == 403

    s_get1 = client.get("/api/v1/sections/", headers=student_headers)
    print(f"Student GET /sections/: {s_get1.status_code} (Expected 403)")
    assert s_get1.status_code == 403

    s_get2 = client.get(f"/api/v1/sections/{section_id}/students", headers=student_headers)
    print(f"Student GET /sections/{section_id}/students: {s_get2.status_code} (Expected 403)")
    assert s_get2.status_code == 403

    print("\n[SUCCESS] ALL TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run_tests()
