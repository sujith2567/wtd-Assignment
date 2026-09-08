"""
Manual smoke test for the new GET /api/v1/matching/student/{id}/explanation
endpoint.

Picks 3 representative students (demo + clean + noisy) from the v2 dataset,
authenticates as admin via the existing /api/v1/auth/login endpoint using
only the Python standard library (urllib), and prints the JSON response
formatted for human review.

Usage:
    1. Start the API:   uvicorn backend.app.main:app --reload
    2. Run the test:    python backend\\scripts\\test_explanation_endpoint.py
"""

import sys
import os
import json
from urllib import request, error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.core.database import SessionLocal
from backend.app.models import Student

BASE_URL = "http://127.0.0.1:8000"
ADMIN_EMAIL = "admin@placematch.edu"
ADMIN_PASSWORD = "password123"


def _post_json(path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_json(path: str, token: str) -> dict:
    req = request.Request(
        f"{BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    with request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def login() -> str:
    body = _post_json(
        "/api/v1/auth/login",
        {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    return body["access_token"]


def find_representative_students():
    """Pick 3 student_ids that span demo / clean / noisy cases."""
    db = SessionLocal()
    try:
        demo = db.query(Student).filter_by(roll_number="CS2025001").first()
        # First-fill predicted_domain for any student that has None so the
        # noisy check (predicted != label) is meaningful.
        all_labelled = (
            db.query(Student)
            .filter(Student.domain_label.isnot(None))
            .all()
        )
        for s in all_labelled:
            if s.predicted_domain is None:
                # Quick local inference: do not hit the live API for this.
                from backend.app.services.classifier_service import get_classifier_service
                res = get_classifier_service().predict_and_explain(
                    resume_text=s.raw_resume_text or "",
                    skills=s.skills or [],
                    projects=s.projects or [],
                )
                s.predicted_domain = res["predicted_domain"]
                s.domain_confidence = res["confidence"]
        db.commit()

        clean = (
            db.query(Student)
            .filter(Student.domain_label.isnot(None),
                    Student.predicted_domain.isnot(None),
                    Student.domain_label == Student.predicted_domain)
            .first()
        )
        noisy = (
            db.query(Student)
            .filter(Student.domain_label.isnot(None),
                    Student.predicted_domain.isnot(None),
                    Student.domain_label != Student.predicted_domain)
            .first()
        )
        picked = []
        if demo:
            picked.append(("DEMO (CS2025001)", demo.id))
        if clean:
            picked.append(("CLEAN (label == predicted)", clean.id))
        if noisy:
            picked.append(("NOISY (label != predicted)", noisy.id))
        return picked
    finally:
        db.close()


def call_explanation(student_id: int, token: str) -> dict:
    return _get_json(f"/api/v1/matching/student/{student_id}/explanation", token)


def pretty_print(label: str, payload: dict) -> None:
    print("\n" + "=" * 78)
    print(f"  {label}  (student_id={payload['student_id']})")
    print("=" * 78)
    print(f"  Name:        {payload['student_name']}")
    print(f"  Roll:        {payload['roll_number']}")
    print(f"  Predicted:   {payload['predicted_domain']}   "
          f"(confidence {payload['confidence_score']:.2%})")
    print(f"  GroundTruth: {payload['ground_truth_domain']}   "
          f"is_correct={payload['is_correct']}   "
          f"is_noisy_case={payload['is_noisy_case']}")

    print("\n  Class probabilities (sorted):")
    for cp in payload["class_probabilities"]:
        bar = "#" * int(cp["probability"] * 40)
        print(f"    {cp['domain']:<38} {cp['probability']:.4f}  {bar}")

    print("\n  Top contributing factors:")
    for f in payload["top_contributing_factors"]:
        marker = {"supports": "++", "weakly_supports": "+", "against": "-"}[f["direction"]]
        print(f"    {marker}  {f['keyword']:<28}  weight={f['weight']:+.4f}")
        print(f"        {f['description']}")

    print("\n  Human-readable summary:")
    print(f"    \"{payload['human_readable_summary']}\"")
    print()


def main() -> int:
    print(f"[*] Connecting to {BASE_URL} ...")
    try:
        token = login()
    except error.URLError as e:
        print(f"[!] Could not reach {BASE_URL}/api/v1/auth/login: {e}")
        print("    Is uvicorn running? Start it with:")
        print("    uvicorn backend.app.main:app --reload")
        return 1

    print("[*] Selecting representative students from DB...")
    picks = find_representative_students()
    if not picks:
        print("[!] No students found. Run generate_synthetic_data.py first.")
        return 1
    for label, sid in picks:
        print(f"    - {label}: id={sid}")

    for label, sid in picks:
        try:
            payload = call_explanation(sid, token)
            pretty_print(label, payload)
        except error.HTTPError as e:
            print(f"[!] HTTP {e.code} for student {sid}: {e.read().decode()}")
        except Exception as e:
            print(f"[!] Error for student {sid}: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
