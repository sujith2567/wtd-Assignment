"""
Fairness-Aware Matching endpoints for PlaceMatch AI.

Routes
------
GET /fairness/audit/{job_id}
    Returns demographic parity difference and disparate impact ratio for
    gender and category, for the current (unmitigated) matching results.

GET /fairness/mitigate/{job_id}
    Returns a before/after comparison of fairness metrics after threshold
    equalization, plus the list of candidates whose selection changed.

Both endpoints are additive post-processing layers. They DO NOT modify the
existing classifier, the stored match_shortlists table, or the default
0.70 buffer threshold for any other endpoint.
"""

from __future__ import annotations

from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from decimal import Decimal

from backend.app.core.database import get_db
from backend.app.core.security import require_role
from backend.app.models.user import User, UserRole
from backend.app.models.student import Student
from backend.app.models.job import JobPosting

from backend.app.services.fairness_metrics import (
    demographic_parity_difference,
    disparate_impact_ratio,
    equalize_thresholds,
)
from backend.app.schemas.fairness import (
    AdjustedCandidate,
    FairnessAuditResponse,
    FairnessMetrics,
    GroupRate,
    GroupThreshold,
    MitigationResponse,
    UnprivilegedGroupDir,
)

router = APIRouter(prefix="/fairness", tags=["Fairness Audit"])

# --------------------------------------------------------------------------- #
# Weights — kept in sync with matching.py (DO NOT change here without also    #
# updating matching.py).                                                       #
# --------------------------------------------------------------------------- #
_W_ACADEMIC = 0.35
_W_SKILL = 0.40
_W_DOMAIN = 0.25
_GLOBAL_THRESHOLD = 0.70


# --------------------------------------------------------------------------- #
# Internal helpers                                                              #
# --------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------
# Explanation helper functions
# ---------------------------------------------------------------------------

def fairness_reason_to_plain(reason: str) -> str:
    """Convert internal audit strings to user‑friendly sentences.
    Example: "[gender] boosted threshold to meet DIR target" ->
    "Adjusted for gender representation to meet the disparate impact ratio target."
    """
    r = reason.lower()
    if "[gender]" in r:
        return "Adjusted for gender representation to meet the disparate impact ratio target."
    if "[category]" in r:
        return "Adjusted for category representation to meet the disparate impact ratio target."
    return reason.replace("[", "").replace("]", "").strip()

def build_apt_explanation(candidate: dict, job) -> str:
    """Generate a natural‑language paragraph explaining why a candidate fits a job.
    Uses fields: `score`, `matching_skills`, `domain_fit_score`, `domain_confidence`.
    """
    name = candidate.get('full_name', 'The candidate')
    roll = candidate.get('roll_number', '')
    score_pct = candidate.get('score', 0) * 100
    # Determine top signal
    top_signal = "overall suitability"
    if candidate.get('domain_fit_score', 0) > 0:
        conf = candidate.get('domain_confidence', 0)
        top_signal = f"domain fit (confidence {conf:.0%})"
    elif candidate.get('matching_skills'):
        skills = candidate['matching_skills']
        if isinstance(skills, list) and skills:
            top_signal = f"skill match on {skills[0]}"
    # Choose a template (deterministic based on hash)
    templates = [
        f"{name} (Roll {roll}) is a strong fit for '{job.title}' with a {score_pct:.1f}% role‑fit score, driven by",
        f"{name} (Roll {roll}) closely aligns with '{job.title}' achieving a {score_pct:.1f}% fit, thanks to",
        f"{name} (Roll {roll}) shows notable overlap with '{job.title}' at {score_pct:.1f}% confidence, due to",
    ]
    template = templates[hash(name) % len(templates)]
    return f"{template} {top_signal}."

def _score_student(
    student: Student,
    job: JobPosting,
    req_skills_set: set[str],
    target_domain: str,
) -> dict[str, Any]:
    """
    Replicate the composite overall_score formula from matching.py.
    Returns a plain dict ready for the fairness layer.
    """
    s_cgpa = float(student.cgpa)
    s_backlogs = student.active_backlogs
    student_skills = student.skills or []
    s_skills_set = {s.lower().strip() for s in student_skills}

    skill_score = (
        len({s for s in (job.required_skills or []) if s.lower().strip() in s_skills_set})
        / len(req_skills_set)
    ) if req_skills_set else 1.0

    academic_score = min(1.0, s_cgpa / 10.0)

    s_pred = (student.predicted_domain or "").strip()
    s_conf = float(student.domain_confidence or 0.0)
    domain_fit = bool(s_pred) and bool(target_domain) and (s_pred == target_domain)
    domain_fit_score = s_conf if domain_fit else 0.0

    overall_score = round(
        _W_ACADEMIC * academic_score
        + _W_SKILL * skill_score
        + _W_DOMAIN * domain_fit_score,
        4,
    )

    return {
        "student_id": student.id,
        "full_name": student.user.full_name,
        "roll_number": student.roll_number,
        "gender": student.gender or "Unknown",
        "category": student.category or "Unknown",
        "score": overall_score,
        "cgpa": s_cgpa,
        "active_backlogs": s_backlogs,
        "domain_confidence": s_conf,
        "domain_fit": domain_fit,
    }


def _apply_selection_gate(
    scored: list[dict[str, Any]],
    job: JobPosting,
    include_buffer: bool,
    buffer_min_confidence: float,
) -> list[dict[str, Any]]:
    """
    Apply strict + (optional) buffer eligibility gates identical to matching.py.
    Adds a `selected` bool to each candidate dict.
    """
    min_cgpa = float(job.min_cgpa)
    max_backlogs = job.max_backlogs_allowed
    buffer_pct = float(job.buffer_threshold_percent or 0.0)
    buffer_cgpa_floor = min_cgpa * (1.0 - buffer_pct / 100.0) if buffer_pct > 0 else min_cgpa

    result = []
    for c in scored:
        s_cgpa = c["cgpa"]
        s_backlogs = c["active_backlogs"]
        s_conf = c["domain_confidence"]
        domain_fit = c["domain_fit"]

        meets_strict = (s_cgpa >= min_cgpa) and (s_backlogs <= max_backlogs)
        meets_buffer = (
            include_buffer
            and (s_cgpa >= buffer_cgpa_floor)
            and (s_backlogs <= max_backlogs + 1)
            and domain_fit
            and (s_conf >= buffer_min_confidence)
        )

        entry = {**c, "selected": meets_strict or meets_buffer}
        result.append(entry)

    return result


def _build_fairness_metrics(
    candidates: list[dict[str, Any]],
    attr_key: str,
) -> FairnessMetrics:
    """Convert raw metric dicts to FairnessMetrics schema objects."""
    dpd_result = demographic_parity_difference(candidates, attr_key)
    dir_result = disparate_impact_ratio(candidates, attr_key)

    group_rates = [
        GroupRate(
            group=group,
            total=stats["total"],
            selected=stats["selected"],
            selection_rate=round(stats["rate"], 6),
        )
        for group, stats in dir_result["groups"].items()
    ]
    group_rates.sort(key=lambda g: g.group)

    unprivileged = [
        UnprivilegedGroupDir(
            group=group,
            selection_rate=round(info["rate"], 6),
            dir=info["dir"],
            passes_four_fifths=info["passes_four_fifths"],
        )
        for group, info in dir_result["unprivileged_groups"].items()
    ]

    return FairnessMetrics(
        attribute=attr_key,
        group_rates=group_rates,
        demographic_parity_difference=round(dpd_result["dpd"], 6),
        disparate_impact_ratio=dir_result["dir"],
        privileged_group=dir_result["privileged_group"],
        unprivileged_groups=unprivileged,
        passes_four_fifths=dir_result["passes_four_fifths"],
    )


def _fetch_job_and_students(
    job_id: int, db: Session
) -> tuple[JobPosting, list[Student]]:
    """Shared fetch; raises 404 if job not found."""
    job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job posting not found.",
        )
    students = db.query(Student).join(
        Student.user
    ).all()
    return job, students


# --------------------------------------------------------------------------- #
# Endpoints                                                                    #
# --------------------------------------------------------------------------- #

@router.get("/audit/{job_id}", response_model=FairnessAuditResponse)
def fairness_audit(
    job_id: int,
    include_buffer: bool = Query(
        False,
        description="Mirror the matching endpoint's include_buffer flag.",
    ),
    buffer_min_confidence: float = Query(
        _GLOBAL_THRESHOLD,
        ge=0.0,
        le=1.0,
        description="Minimum domain_confidence for buffer promotion.",
    ),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER])),
    db: Session = Depends(get_db),
):
    """
    Audit the fairness of current (unmitigated) matching results for a job.

    Returns demographic parity difference and disparate impact ratio for both
    `gender` and `category`. Flags any group that fails the 4/5ths rule
    (DIR < 0.80).

    The `selected` flag mirrors the existing adaptive buffer-matching logic:
    strict eligibility is always checked; buffer promotion is only applied
    when `include_buffer=true`.
    """
    job, students = _fetch_job_and_students(job_id, db)

    req_skills_set = {s.lower().strip() for s in (job.required_skills or [])}
    target_domain = (job.target_domain or "").strip()

    scored = [
        _score_student(s, job, req_skills_set, target_domain)
        for s in students
    ]
    candidates = _apply_selection_gate(
        scored, job, include_buffer, buffer_min_confidence
    )

    total_selected = sum(1 for c in candidates if c["selected"])

    gender_metrics = _build_fairness_metrics(candidates, "gender")
    category_metrics = _build_fairness_metrics(candidates, "category")

    return FairnessAuditResponse(
        job_id=job.id,
        job_title=job.title,
        total_candidates_evaluated=len(candidates),
        total_selected=total_selected,
        buffer_matching_enabled=include_buffer,
        buffer_min_confidence=buffer_min_confidence,
        gender_metrics=gender_metrics,
        category_metrics=category_metrics,
    )


@router.get("/mitigate/{job_id}", response_model=MitigationResponse)
def fairness_mitigate(
    job_id: int,
    include_buffer: bool = Query(False),
    buffer_min_confidence: float = Query(
        _GLOBAL_THRESHOLD, ge=0.0, le=1.0,
    ),
    target_dir_min: float = Query(
        0.80, ge=0.0, le=1.0,
        description="Lower bound of acceptable disparate impact ratio (default = 4/5ths rule).",
    ),
    target_dir_max: float = Query(
        1.25, ge=1.0, le=2.0,
        description="Upper bound of acceptable disparate impact ratio.",
    ),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER])),
    db: Session = Depends(get_db),
):
    """
    Apply threshold equalization mitigation and return a before/after comparison.

    For each protected attribute (gender, category), computes per-group
    confidence thresholds so that disparate impact ratios land in
    [target_dir_min, target_dir_max].

    Returns:
    - Original + mitigated fairness metrics per attribute.
    - Per-group adjusted thresholds.
    - List of candidates whose inclusion/exclusion changed, with a
      `fairness_adjusted: true` flag and a human-readable reason string.

    This endpoint is purely read-only and does NOT persist any changes.
    The existing global 0.70 threshold default is unchanged for all other
    matching endpoints.
    """
    job, students = _fetch_job_and_students(job_id, db)

    req_skills_set = {s.lower().strip() for s in (job.required_skills or [])}
    target_domain = (job.target_domain or "").strip()

    scored = [
        _score_student(s, job, req_skills_set, target_domain)
        for s in students
    ]
    candidates = _apply_selection_gate(
        scored, job, include_buffer, buffer_min_confidence
    )

    # ------------------------------------------------------------------ #
    # Gender dimension                                                     #
    # ------------------------------------------------------------------ #
    gender_result = equalize_thresholds(
        candidates=candidates,
        attr_key="gender",
        target_dir_min=target_dir_min,
        target_dir_max=target_dir_max,
        global_threshold=buffer_min_confidence,
    )

    # ------------------------------------------------------------------ #
    # Category dimension                                                   #
    # ------------------------------------------------------------------ #
    category_result = equalize_thresholds(
        candidates=candidates,
        attr_key="category",
        target_dir_min=target_dir_min,
        target_dir_max=target_dir_max,
        global_threshold=buffer_min_confidence,
    )

    # ------------------------------------------------------------------ #
    # Build before/after FairnessMetrics from stored equalize outputs     #
    # ------------------------------------------------------------------ #
    def _metrics_from_equalize(result: dict, attr_key: str, use_after: bool) -> FairnessMetrics:
        """Convert equalize_thresholds output metrics to FairnessMetrics schema."""
        raw = result["metrics_after"] if use_after else result["metrics_before"]
        # raw is a dict from disparate_impact_ratio()

        dpd_result = demographic_parity_difference(
            [{**c, "selected": c["mitigated_selected"] if use_after else c["selected"]}
             for c in result["adjusted_candidates"]],
            attr_key,
        )

        group_rates = [
            GroupRate(
                group=group,
                total=stats["total"],
                selected=stats["selected"],
                selection_rate=round(stats["rate"], 6),
            )
            for group, stats in raw["groups"].items()
        ]
        group_rates.sort(key=lambda g: g.group)

        unprivileged = [
            UnprivilegedGroupDir(
                group=group,
                selection_rate=round(info["rate"], 6),
                dir=info["dir"],
                passes_four_fifths=info["passes_four_fifths"],
            )
            for group, info in raw["unprivileged_groups"].items()
        ]

        return FairnessMetrics(
            attribute=attr_key,
            group_rates=group_rates,
            demographic_parity_difference=round(dpd_result["dpd"], 6),
            disparate_impact_ratio=raw["dir"],
            privileged_group=raw["privileged_group"],
            unprivileged_groups=unprivileged,
            passes_four_fifths=raw["passes_four_fifths"],
        )

    gender_before = _metrics_from_equalize(gender_result, "gender", use_after=False)
    gender_after = _metrics_from_equalize(gender_result, "gender", use_after=True)
    category_before = _metrics_from_equalize(category_result, "category", use_after=False)
    category_after = _metrics_from_equalize(category_result, "category", use_after=True)

    # ------------------------------------------------------------------ #
    # Build per-group threshold lists                                      #
    # ------------------------------------------------------------------ #
    gender_thresholds = [
        GroupThreshold(group=g, threshold=t)
        for g, t in sorted(gender_result["group_thresholds"].items())
    ]
    category_thresholds = [
        GroupThreshold(group=g, threshold=t)
        for g, t in sorted(category_result["group_thresholds"].items())
    ]

    # ------------------------------------------------------------------ #
    # Merge changed candidates from both dimensions                        #
    # ------------------------------------------------------------------ #
    # Index gender and category adjusted candidate lists by student_id
    gender_by_id = {c["student_id"]: c for c in gender_result["adjusted_candidates"]}
    category_by_id = {c["student_id"]: c for c in category_result["adjusted_candidates"]}

    changed_candidates: list[AdjustedCandidate] = []

    for sid, gc in gender_by_id.items():
        cc = category_by_id.get(sid, {})

        gender_changed = gc.get("fairness_adjusted", False)
        category_changed = cc.get("fairness_adjusted", False)

        if not gender_changed and not category_changed:
            continue

        # Combine: a candidate is mitigated_selected if EITHER dimension
        # includes them (inclusive OR for fairness).
        combined_mitigated = gc.get("mitigated_selected", gc["selected"]) or \
                             cc.get("mitigated_selected", gc["selected"])

        # Compose reason string
        reasons = []
        if gc.get("fairness_reason"):
            reasons.append(f"[gender] {gc['fairness_reason']}")
        if cc.get("fairness_reason"):
            reasons.append(f"[category] {cc['fairness_reason']}")

        changed_candidates.append(
            AdjustedCandidate(
                student_id=sid,
                full_name=gc["full_name"],
                roll_number=gc["roll_number"],
                gender=gc.get("gender"),
                category=gc.get("category"),
                score=gc["score"],
                original_selected=gc["selected"],
                mitigated_selected=combined_mitigated,
                changed=True,
                fairness_adjusted=True,
                fairness_reason=" | ".join(reasons) if reasons else None,
                fit_explanation=build_apt_explanation(gc, job),
                fairness_note=fairness_reason_to_plain(reasons[0]) if reasons else None,
            )
        )

    changed_candidates.sort(key=lambda c: c.roll_number)

    return MitigationResponse(
        job_id=job.id,
        job_title=job.title,
        total_candidates_evaluated=len(candidates),
        buffer_matching_enabled=include_buffer,
        buffer_min_confidence=buffer_min_confidence,
        global_threshold=buffer_min_confidence,
        target_dir_min=target_dir_min,
        target_dir_max=target_dir_max,
        gender_thresholds=gender_thresholds,
        gender_metrics_before=gender_before,
        gender_metrics_after=gender_after,
        category_thresholds=category_thresholds,
        category_metrics_before=category_before,
        category_metrics_after=category_after,
        changed_candidates=changed_candidates,
    )
