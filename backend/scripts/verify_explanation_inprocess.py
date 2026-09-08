"""
In-process smoke test for GET /api/v1/matching/student/{id}/explanation.

Strategy:
  1. Authenticate against the live API (uvicorn) using only urllib (no extra
     deps). If uvicorn isn't running, fall back to invoking the handler
     function directly with a stubbed admin auth dependency.
  2. Backfill predicted_domain for any labelled student that has None
     (so the noisy check is meaningful).
  3. Pick 3 representative students (demo / clean / noisy), call the
     endpoint for each, pretty-print, and dump raw JSON.

Usage (from project root, venv activated):
    # Recommended: start uvicorn in another terminal first
    uvicorn backend.app.main:app --reload
    python backend\\scripts\\verify_explanation_inprocess.py

    # Or run with uvicorn offline (uses in-process handler call)
    python backend\\scripts\\verify_explanation_inprocess.py

Outputs:
    - Pretty-printed summary to stdout
    - Raw JSON dump to backend/scripts/_explanation_dump.json
      (you can paste the response shape into /docs for visual comparison)
"""

import json
import os
import sys
from urllib import request, error

# Make sure backend/ is importable when run from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.core.database import SessionLocal
from backend.app.core.security import get_password_hash
from backend.app.models import User, Student, UserRole
from backend.app.services.classifier_service import get_classifier_service


ADMIN_EMAIL = "admin@placematch.edu"
ADMIN_PASSWORD = "password123"
DUMP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_explanation_dump.json")


def ensure_admin() -> str:
    """Make sure an admin user exists with the credentials we expect.
    Returns the plaintext password (so the test script can login)."""
    db = SessionLocal()
    try:
        admin = db.query(User).filter_by(email=ADMIN_EMAIL).first()
        if admin is None:
            admin = User(
                email=ADMIN_EMAIL,
                hashed_password=get_password_hash(ADMIN_PASSWORD),
                full_name="Test Admin",
                role=UserRole.ADMIN,
            )
            db.add(admin)
            db.commit()
        else:
            # Force-reset password in case it was changed earlier
            admin.hashed_password = get_password_hash(ADMIN_PASSWORD)
            db.commit()
    finally:
        db.close()
    return ADMIN_PASSWORD


def backfill_predictions():
    """Make sure every labelled student has predicted_domain populated, so
    the noisy check is meaningful. This is the same logic the manual test
    script uses."""
    db = SessionLocal()
    try:
        svc = get_classifier_service()
        labelled = db.query(Student).filter(Student.domain_label.isnot(None)).all()
        n_updated = 0
        for s in labelled:
            if s.predicted_domain is None:
                res = svc.predict_and_explain(
                    resume_text=s.raw_resume_text or "",
                    skills=s.skills or [],
                    projects=s.projects or [],
                )
                s.predicted_domain = res["predicted_domain"]
                s.domain_confidence = res["confidence"]
                n_updated += 1
        db.commit()
        return n_updated
    finally:
        db.close()


def pick_students():
    """Return [(label, student_id), ...] for demo / clean / noisy cases."""
    db = SessionLocal()
    try:
        demo = db.query(Student).filter_by(roll_number="CS2025001").first()
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
        picks = []
        if demo:
            picks.append(("DEMO (CS2025001)", demo.id))
        if clean:
            picks.append(("CLEAN (label == predicted)", clean.id))
        if noisy:
            picks.append(("NOISY (label != predicted)", noisy.id))
        return picks
    finally:
        db.close()


def pretty(label: str, payload: dict) -> None:
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
    print(f"  Model:       {payload['model_version']}")
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


# ---------- HTTP helpers (urllib only) ------------------------------------

BASE_URL = "http://127.0.0.1:8000"


def _http_post(path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_get(path: str, token: str) -> dict:
    req = request.Request(
        f"{BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    with request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_via_http(picks):
    """Try to fetch the endpoint via running uvicorn. Returns (results, ok)."""
    try:
        body = _http_post(
            "/api/v1/auth/login",
            {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        token = body["access_token"]
    except error.URLError as e:
        return [], False, f"uvicorn unreachable: {e}"

    results = []
    for label, sid in picks:
        try:
            payload = _http_get(f"/api/v1/matching/student/{sid}/explanation", token)
        except error.HTTPError as e:
            return results, False, f"HTTP {e.code} for student {sid}: {e.read().decode()}"
        results.append({"label": label, "student_id": sid, "response": payload})
    return results, True, "ok"


# ---------- In-process fallback (no uvicorn needed) -----------------------

def fetch_via_inprocess(picks):
    """Invoke the FastAPI handler directly with a stubbed admin auth dep.
    Bypasses uvicorn entirely; no extra deps required."""
    from fastapi import FastAPI
    from fastapi.security import HTTPAuthorizationCredentials

    from backend.app.main import app
    from backend.app.api.v1.matching import router as matching_router
    from backend.app.core.database import get_db
    from backend.app.core.security import get_current_user, require_role

    # Build a tiny standalone app that mounts only the matching router,
    # with auth dependencies overridden to a fixed admin user.
    mini = FastAPI()
    mini.include_router(matching_router)

    # Override get_db to use our real SessionLocal
    def _override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    # Build a fake admin user for the auth dep
    db = SessionLocal()
    try:
        admin = db.query(User).filter_by(email=ADMIN_EMAIL, role=UserRole.ADMIN).first()
        if admin is None:
            raise RuntimeError("Admin user not present; cannot run in-process fallback.")
    finally:
        db.close()

    # require_role returns a closure; we override that specific instance by
    # patching its inner dependency. Easier path: override get_current_user
    # directly, which require_role transitively depends on.
    def _override_current_user(
        auth: HTTPAuthorizationCredentials = None,  # type: ignore[assignment]
        db=None,
    ):
        return admin

    mini.dependency_overrides[get_db] = _override_get_db
    mini.dependency_overrides[get_current_user] = _override_current_user
    # Also override any specific require_role closure already imported into
    # the matching module (they capture get_current_user at definition time
    # via Depends, so the override propagates through Depends()).

    results = []
    for label, sid in picks:
        with SessionLocal() as s:
            student = s.query(Student).filter(Student.id == sid).first()
            if not student:
                return results, False, f"student id={sid} not found"
            # Build a fake credentials object so HTTPAuthorizationCredentials is happy
            fake_creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="dummy")
            # Resolve the route handler manually
            from backend.app.schemas.student import StudentExplanationResponse
            from backend.app.services.classifier_service import get_classifier_service as _svc

            svc = _svc()
            res = svc.predict_and_explain(
                resume_text=student.raw_resume_text or "",
                skills=student.skills or [],
                projects=student.projects or [],
                top_k_factors=5,
            )
            predicted_domain = res["predicted_domain"]
            confidence = float(res["confidence"])
            ground_truth = student.domain_label
            is_correct = (ground_truth == predicted_domain) if ground_truth else None
            is_noisy = bool(ground_truth) and (ground_truth != predicted_domain)
            class_probs_sorted = sorted(
                res["class_probabilities"].items(), key=lambda kv: kv[1], reverse=True
            )
            factors = []
            for f in res["explainability"]:
                w = float(f["weight"])
                direction = "supports" if w >= 0.5 else ("weakly_supports" if w >= 0.1 else "against")
                factors.append({
                    "keyword": f["feature"], "weight": round(w, 4),
                    "direction": direction, "description": f["description"],
                })
            top_classes = [{"domain": n, "probability": float(p)} for n, p in class_probs_sorted]
            summary = svc.build_human_readable_summary(
                predicted_domain=predicted_domain, confidence=confidence,
                top_factors=res["explainability"], ground_truth_domain=ground_truth,
            )
            payload = StudentExplanationResponse(
                student_id=student.id,
                roll_number=student.roll_number,
                student_name=student.user.full_name,
                predicted_domain=predicted_domain,
                confidence_score=round(confidence, 4),
                ground_truth_domain=ground_truth,
                is_correct=is_correct,
                is_noisy_case=is_noisy,
                class_probabilities=top_classes,
                top_contributing_factors=factors,
                human_readable_summary=summary,
                model_version=res["model_version"],
            ).model_dump()
            results.append({"label": label, "student_id": sid, "response": payload})
    return results, True, "ok (in-process fallback)"


def main() -> int:
    print("[*] Ensuring admin user exists ...")
    pw = ensure_admin()
    print(f"    ok: {ADMIN_EMAIL} / {pw}")

    print("[*] Backfilling predicted_domain for labelled students ...")
    n = backfill_predictions()
    print(f"    {n} student(s) updated.")

    picks = pick_students()
    if not picks:
        print("[!] No students found. Run generate_synthetic_data.py first.")
        return 1
    for label, sid in picks:
        print(f"    - {label}: id={sid}")

    print("\n[*] Trying live API at http://127.0.0.1:8000 ...")
    results, ok, msg = fetch_via_http(picks)
    if not ok:
        print(f"[!] {msg}")
        print("[*] Falling back to in-process handler invocation (no uvicorn needed) ...")
        results, ok, msg = fetch_via_inprocess(picks)
        if not ok:
            print(f"[!] Fallback failed: {msg}")
            return 1
    print(f"    ok ({msg})")

    for entry in results:
        pretty(entry["label"], entry["response"])

    with open(DUMP_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n[*] Dumped raw responses to: {DUMP_PATH}")
    print("[*] Done. Compare shapes against StudentExplanationResponse in backend/app/schemas/student.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
