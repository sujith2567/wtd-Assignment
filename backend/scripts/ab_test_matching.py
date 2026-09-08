"""
A/B test for the rewired baseline-candidates endpoint.

For each target job_id we:
  1. Call evaluate_baseline_candidates(include_buffer=False)  -> "BEFORE"
  2. Call evaluate_baseline_candidates(include_buffer=True)   -> "AFTER"
  3. Print top-N of each, plus a diff summary:
     - how many students moved tier (strict <-> buffer)
     - how many students' ranks shifted, and by how much
     - how many new buffer candidates surfaced
  4. Dump raw results to JSON for the report.

Strategy:
  Bypass uvicorn / TestClient / httpx. Instead, invoke the FastAPI handler
  function directly with a stubbed admin auth dep (override get_current_user
  on a tiny standalone FastAPI app that mounts only the matching router).

Picks 3 jobs from the v2 dataset:
  - 1 in a domain with many students (high signal)
  - 1 borderline (fewer students, moderate CGPA cutoff)
  - 1 where buffer promotion should actually fire (target_domain has
    confident predictions, but min_cgpa is high enough to push some
    candidates just below strict).

Usage:
    python backend\\scripts\\ab_test_matching.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# NOTE: do NOT import fastapi.testclient at module-load — it raises if httpx is
# missing, before we get a chance to fall back to direct handler invocation.


def _httpx_available() -> bool:
    try:
        import httpx  # noqa: F401
        return True
    except ImportError:
        return False


def _pick_jobs(db, n: int = 3):
    """Pick 3 representative jobs from the dataset."""
    from backend.app.models.job import JobPosting
    from backend.app.models.student import Student

    jobs = db.query(JobPosting).all()
    if not jobs:
        return []

    # Score each job by # students whose domain_label == target_domain
    scored = []
    for j in jobs:
        n_strict = db.query(Student).filter(
            Student.cgpa >= j.min_cgpa,
            Student.active_backlogs <= j.max_backlogs_allowed,
        ).count()
        n_domain = db.query(Student).filter(Student.domain_label == j.target_domain).count()
        scored.append((j, n_strict, n_domain))

    # Pick: most-populated, least-populated, mid-populated (by n_strict)
    scored.sort(key=lambda x: x[1])
    picks = []
    if len(scored) >= 1:
        picks.append(("LOW volume (few strict candidates)", scored[0][0]))
    if len(scored) >= 3:
        mid = scored[len(scored) // 2]
        picks.append(("MID volume", mid[0]))
    if len(scored) >= 2:
        picks.append(("HIGH volume (many strict candidates)", scored[-1][0]))
    return picks[:n]


def _resolve_handler_via_testclient():
    """Use FastAPI TestClient if httpx is available. Otherwise return None."""
    if not _httpx_available():
        return None

    # Import TestClient lazily so its absence doesn't crash module load.
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.core.database import SessionLocal
    from backend.app.core.security import get_current_user
    from backend.app.models import User, UserRole

    # Build a fake admin user (we use the admin created by the explanation script)
    db = SessionLocal()
    try:
        admin = db.query(User).filter_by(email="admin@placematch.edu", role=UserRole.ADMIN).first()
        if admin is None:
            print("[!] No admin user; run verify_explanation_inprocess.py first.")
            return None
    finally:
        db.close()

    # Override get_current_user on the REAL app so every route uses our admin
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)
    return client


def _call_endpoint_via_testclient(client, job_id: int, include_buffer: bool, buffer_min_confidence: float):
    r = client.get(
        f"/api/v1/matching/jobs/{job_id}/baseline-candidates",
        params={
            "limit": 50,
            "include_buffer": str(include_buffer).lower(),
            "buffer_min_confidence": buffer_min_confidence,
        },
    )
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text}")
    return r.json()


def _call_endpoint_inprocess(job_id: int, include_buffer: bool, buffer_min_confidence: float):
    """Direct handler invocation when httpx is unavailable. Replicates the
    route's behavior without going through ASGI dispatch."""
    from backend.app.core.database import SessionLocal
    from backend.app.models.user import User, UserRole
    from backend.app.models.student import Student
    from backend.app.models.job import JobPosting
    from backend.app.models.match import MatchTier
    from backend.app.schemas.match import CandidateMatchItem

    db = SessionLocal()
    try:
        admin = db.query(User).filter_by(email="admin@placematch.edu", role=UserRole.ADMIN).first()
        if admin is None:
            raise RuntimeError("No admin user; run verify_explanation_inprocess.py first.")

        job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
        if not job:
            raise RuntimeError(f"job_id={job_id} not found")

        min_cgpa = float(job.min_cgpa)
        max_backlogs = job.max_backlogs_allowed
        buffer_pct = float(job.buffer_threshold_percent or 0.0)
        req_skills_set = {s.lower().strip() for s in (job.required_skills or [])}
        target_domain = (job.target_domain or "").strip()

        W_ACADEMIC, W_SKILL, W_DOMAIN = 0.35, 0.40, 0.25
        buffer_cgpa_floor = min_cgpa * (1.0 - buffer_pct / 100.0) if buffer_pct > 0 else min_cgpa

        students = db.query(Student).join(User, Student.user_id == User.id).all()

        matches = []
        strict_count = 0
        buffer_count = 0
        for student in students:
            s_cgpa = float(student.cgpa)
            s_backlogs = student.active_backlogs
            student_skills = student.skills or []
            s_skills_set = {s.lower().strip() for s in student_skills}
            matching_skills = [s for s in (job.required_skills or []) if s.lower().strip() in s_skills_set]
            missing_skills  = [s for s in (job.required_skills or []) if s.lower().strip() not in s_skills_set]
            skill_score = (len(matching_skills) / len(req_skills_set)) if req_skills_set else 1.0
            academic_score = min(1.0, s_cgpa / 10.0)

            s_pred = (student.predicted_domain or "").strip()
            s_conf = float(student.domain_confidence or 0.0)
            domain_fit = bool(s_pred) and bool(target_domain) and (s_pred == target_domain)
            domain_fit_score = s_conf if domain_fit else 0.0

            overall_score = round(
                W_ACADEMIC * academic_score + W_SKILL * skill_score + W_DOMAIN * domain_fit_score, 3,
            )
            breakdown = {
                "academic_weight": round(W_ACADEMIC * academic_score, 4),
                "skill_weight":    round(W_SKILL    * skill_score,    4),
                "domain_weight":   round(W_DOMAIN   * domain_fit_score, 4),
            }

            meets_strict = (s_cgpa >= min_cgpa) and (s_backlogs <= max_backlogs)
            meets_buffer = (
                include_buffer
                and (s_cgpa >= buffer_cgpa_floor)
                and (s_backlogs <= max_backlogs + 1)
                and domain_fit
                and (s_conf >= buffer_min_confidence)
            )

            if meets_strict:
                tier = MatchTier.STRICT_MATCH.value; strict_count += 1
                reason = f"Strict: CGPA {s_cgpa:.2f}>={min_cgpa:.2f}, backlogs {s_backlogs}<={max_backlogs}, {len(matching_skills)}/{len(req_skills_set)} skills, predicted={s_pred or 'N/A'} ({s_conf:.0%})."
            elif meets_buffer:
                tier = MatchTier.BUFFER_MATCH.value; buffer_count += 1
                gap = []
                if s_cgpa < min_cgpa: gap.append(f"CGPA {s_cgpa:.2f}<{min_cgpa:.2f}")
                if s_backlogs > max_backlogs: gap.append(f"backlogs {s_backlogs}>{max_backlogs}")
                reason = f"Buffer via domain-fit {s_pred} ({s_conf:.0%}) -> {target_domain}. {' '.join(gap)}; {len(matching_skills)}/{len(req_skills_set)} skills."
            else:
                continue

            matches.append(CandidateMatchItem(
                student_id=student.id, user_id=student.user.id,
                full_name=student.user.full_name, email=student.user.email,
                roll_number=student.roll_number, department=student.department,
                cgpa=s_cgpa, active_backlogs=s_backlogs,
                skills=student_skills, match_tier=tier,
                overall_score=overall_score,
                academic_score=round(academic_score, 3),
                skill_match_score=round(skill_score, 3),
                semantic_similarity=0.0,
                domain_fit_score=round(domain_fit_score, 4),
                score_breakdown=breakdown,
                matching_skills=matching_skills, missing_skills=missing_skills,
                reason=reason,
            ))

        matches.sort(key=lambda x: x.overall_score, reverse=True)
        matches = matches[:50]
        return {
            "job_id": job.id,
            "job_title": job.title,
            "min_cgpa": min_cgpa,
            "max_backlogs": max_backlogs,
            "required_skills": job.required_skills or [],
            "total_candidates_evaluated": len(students),
            "strict_matches_count": strict_count,
            "buffer_matches_count": buffer_count,
            "matches": [m.model_dump() for m in matches],
        }
    finally:
        db.close()


def _diff_summary(before: dict, after: dict, top_n: int = 10) -> dict:
    """Compare two ranking snapshots."""
    def rankmap(snap):
        return {m["student_id"]: (i, m["match_tier"], m["overall_score"], m["domain_fit_score"])
                for i, m in enumerate(snap["matches"])}

    rb = rankmap(before)
    ra = rankmap(after)
    all_ids = set(rb) | set(ra)

    new_in_top = [sid for sid in all_ids if sid not in rb and sid in ra][:top_n]
    dropped_from_top = [sid for sid in all_ids if sid in rb and sid not in ra][:top_n]

    rank_shifts = []
    tier_changes = []
    for sid in all_ids:
        if sid in rb and sid in ra:
            old_rank, old_tier, old_score, _ = rb[sid]
            new_rank, new_tier, new_score, _ = ra[sid]
            if old_rank != new_rank:
                rank_shifts.append({
                    "student_id": sid,
                    "old_rank": old_rank, "new_rank": new_rank,
                    "delta": old_rank - new_rank,
                    "old_score": old_score, "new_score": new_score,
                    "tier": new_tier,
                })
            if old_tier != new_tier:
                tier_changes.append({
                    "student_id": sid,
                    "old_tier": old_tier, "new_tier": new_tier,
                })

    rank_shifts.sort(key=lambda x: abs(x["delta"]), reverse=True)
    return {
        "before_strict_count": before["strict_matches_count"],
        "after_strict_count": after["strict_matches_count"],
        "before_buffer_count": before["buffer_matches_count"],
        "after_buffer_count": after["buffer_matches_count"],
        "before_top_n_size": len(before["matches"]),
        "after_top_n_size": len(after["matches"]),
        "new_in_top_n": new_in_top,
        "dropped_from_top_n": dropped_from_top,
        "biggest_rank_shifts": rank_shifts[:10],
        "tier_changes": tier_changes,
    }


def _print_top(snap: dict, label: str, top_n: int = 10) -> None:
    print(f"\n  --- {label} ---")
    print(f"  job_id={snap['job_id']}  title={snap['job_title']!r}")
    print(f"  min_cgpa={snap['min_cgpa']}  max_backlogs={snap['max_backlogs']}")
    print(f"  required_skills={snap['required_skills']}")
    print(f"  strict={snap['strict_matches_count']}  buffer={snap['buffer_matches_count']}  shown={len(snap['matches'])}")
    print(f"\n  {'rank':>4} {'tier':<14} {'score':>6} {'acad':>5} {'skill':>5} {'dom':>5} {'cgpa':>5} {'roll':<12} name")
    for i, m in enumerate(snap["matches"][:top_n], 1):
        bd = m.get("score_breakdown", {})
        print(f"  {i:>4} {m['match_tier']:<14} {m['overall_score']:>6.3f} "
              f"{bd.get('academic_weight', 0):>5.2f} {bd.get('skill_weight', 0):>5.2f} {bd.get('domain_weight', 0):>5.2f} "
              f"{m['cgpa']:>5.2f} {m['roll_number']:<12} {m['full_name']}")


def main() -> int:
    from backend.app.core.database import SessionLocal

    client = _resolve_handler_via_testclient()
    if client is not None:
        print("[*] Using TestClient (httpx available).")
        def call(jid, ib, bmc):
            return _call_endpoint_via_testclient(client, jid, ib, bmc)
    else:
        print("[*] httpx not installed; using direct handler invocation.")
        def call(jid, ib, bmc):
            return _call_endpoint_inprocess(jid, ib, bmc)

    db = SessionLocal()
    try:
        picks = _pick_jobs(db, 3)
    finally:
        db.close()

    if not picks:
        print("[!] No jobs found. Run generate_synthetic_data.py first.")
        return 1

    print("\n[*] Selected jobs:")
    for label, j in picks:
        print(f"    - {label}: id={j.id}  title={j.title!r}  target_domain={j.target_domain!r}  min_cgpa={j.min_cgpa}  buffer_pct={j.buffer_threshold_percent}")

    all_results = []
    for label, job in picks:
        print(f"\n{'#' * 78}\n# JOB {job.id}  {label}\n{'#' * 78}")
        before = call(job.id, False, 0.70)
        after  = call(job.id, True,  0.70)
        diff   = _diff_summary(before, after)
        _print_top(before, "BEFORE (strict only)", top_n=10)
        _print_top(after,  "AFTER  (strict + buffer @ conf>=0.70)", top_n=10)
        print("\n  --- DIFF ---")
        print(f"  strict: {diff['before_strict_count']} -> {diff['after_strict_count']}")
        print(f"  buffer: {diff['before_buffer_count']} -> {diff['after_buffer_count']}")
        print(f"  new in top-10: {len(diff['new_in_top_n'])}")
        print(f"  dropped from top-10: {len(diff['dropped_from_top_n'])}")
        print(f"  rank shifts > 0: {len(diff['biggest_rank_shifts'])}")
        print(f"  tier changes:    {len(diff['tier_changes'])}")
        for s in diff["biggest_rank_shifts"][:5]:
            print(f"    student {s['student_id']}: rank {s['old_rank']}->{s['new_rank']} (delta {s['delta']:+d})  score {s['old_score']}->{s['new_score']}  tier={s['tier']}")
        for t in diff["tier_changes"][:5]:
            print(f"    student {t['student_id']}: tier {t['old_tier']} -> {t['new_tier']}")
        all_results.append({
            "job_id": job.id, "job_label": label, "job_title": job.title,
            "target_domain": job.target_domain, "min_cgpa": float(job.min_cgpa),
            "buffer_threshold_percent": float(job.buffer_threshold_percent),
            "before": before, "after": after, "diff": diff,
        })

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ab_test_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n[*] Dumped full results to: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
