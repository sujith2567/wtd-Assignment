"""
fairness_metrics.py
===================
Post-processing fairness metrics and threshold equalization for PlaceMatch AI.

This module is a pure-Python, zero-ML-dependency layer that sits *after*
the existing adaptive buffer-matching pipeline and computes:

  1. demographic_parity_difference  — max – min group selection rate.
  2. disparate_impact_ratio         — unprivileged / privileged selection rate.
  3. equalize_thresholds            — per-group confidence threshold adjustment
                                      so DIRs land in a caller-specified range,
                                      with the existing global 0.70 gate as
                                      a hard floor (never penalise below it).

All three functions are generic over any protected attribute key, so the
same code handles both `gender` and `category` without duplication.

Candidate dict contract (minimum required keys)
-----------------------------------------------
Each candidate dict passed in must have at least:
  - the protected attribute key (e.g. "gender" or "category")  → str | None
  - "selected"  → bool   (whether the student passed the current threshold)
  - "score"     → float  (overall_score from the matching engine, 0-1)
  - "student_id" → int
  - "full_name"  → str
  - "roll_number" → str
"""

from __future__ import annotations

from typing import Any


# --------------------------------------------------------------------------- #
# Internal helpers                                                             #
# --------------------------------------------------------------------------- #

def _group_stats(
    candidates: list[dict[str, Any]],
    attr_key: str,
) -> dict[str, dict[str, int | float]]:
    """
    Compute per-group selection counts from a list of candidate dicts.

    Returns a mapping:
        { group_value: {"total": int, "selected": int, "rate": float} }

    Candidates whose attr_key value is None / empty string are placed in an
    "Unknown" group so they are not silently dropped from the audit.
    """
    stats: dict[str, dict[str, int | float]] = {}

    for c in candidates:
        group = c.get(attr_key) or "Unknown"
        if group not in stats:
            stats[group] = {"total": 0, "selected": 0, "rate": 0.0}
        stats[group]["total"] += 1
        if c.get("selected", False):
            stats[group]["selected"] += 1

    # Compute selection rates
    for group, s in stats.items():
        s["rate"] = s["selected"] / s["total"] if s["total"] > 0 else 0.0

    return stats


def _identify_privileged(
    stats: dict[str, dict[str, int | float]],
    privileged_group: str | None,
) -> str:
    """
    Return the privileged group label.

    If privileged_group is explicitly provided, use it (raises KeyError if
    not found in stats — callers should validate input).
    Otherwise, auto-detect as the group with the highest selection rate.
    On a tie, pick the lexicographically first group name for determinism.
    """
    if privileged_group is not None:
        if privileged_group not in stats:
            raise ValueError(
                f"privileged_group '{privileged_group}' not found in candidates. "
                f"Available groups: {list(stats.keys())}"
            )
        return privileged_group

    # Auto-detect: highest selection rate, then alphabetical tie-break
    return max(stats.keys(), key=lambda g: (stats[g]["rate"], -ord(g[0])))


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #

def demographic_parity_difference(
    candidates: list[dict[str, Any]],
    attr_key: str,
) -> dict[str, Any]:
    """
    Compute the Demographic Parity Difference (DPD) for a protected attribute.

    DPD = max(group selection rate) − min(group selection rate)

    A DPD of 0 means all groups are selected at the same rate.
    A DPD of 1 means one group has 100 % selection and another has 0 %.

    Parameters
    ----------
    candidates : list of dicts
        Each dict must contain `attr_key` and `"selected"` (bool).
    attr_key : str
        Name of the protected attribute column, e.g. "gender" or "category".

    Returns
    -------
    dict with keys:
        groups          : dict mapping group → {"total", "selected", "rate"}
        dpd             : float  — demographic parity difference
        max_rate_group  : str    — group with highest selection rate
        min_rate_group  : str    — group with lowest selection rate
    """
    if not candidates:
        return {
            "groups": {},
            "dpd": 0.0,
            "max_rate_group": None,
            "min_rate_group": None,
        }

    stats = _group_stats(candidates, attr_key)

    max_group = max(stats.keys(), key=lambda g: (stats[g]["rate"], g))
    min_group = min(stats.keys(), key=lambda g: (stats[g]["rate"], g))

    dpd = stats[max_group]["rate"] - stats[min_group]["rate"]

    return {
        "groups": stats,
        "dpd": round(dpd, 6),
        "max_rate_group": max_group,
        "min_rate_group": min_group,
    }


def disparate_impact_ratio(
    candidates: list[dict[str, Any]],
    attr_key: str,
    privileged_group: str | None = None,
) -> dict[str, Any]:
    """
    Compute the Disparate Impact Ratio (DIR) for a protected attribute.

    DIR = (unprivileged group selection rate) / (privileged group selection rate)

    The 4/5ths (80 %) rule flags DIR < 0.80 as indicating adverse impact.
    DIR > 1.25 indicates reverse disparate impact.

    Parameters
    ----------
    candidates : list of dicts
        Each dict must contain `attr_key` and `"selected"` (bool).
    attr_key : str
        Protected attribute column name.
    privileged_group : str | None
        Explicitly specify the privileged group, or None to auto-detect
        (group with the highest selection rate is treated as privileged).

    Returns
    -------
    dict with keys:
        groups              : dict mapping group → {"total", "selected", "rate"}
        dir                 : float | None  (None if privileged rate == 0)
        privileged_group    : str
        unprivileged_groups : dict  mapping group → {"rate", "dir", "passes_four_fifths"}
        passes_four_fifths  : bool  — True if ALL unprivileged DIRs >= 0.80
    """
    if not candidates:
        return {
            "groups": {},
            "dir": None,
            "privileged_group": None,
            "unprivileged_groups": {},
            "passes_four_fifths": True,
        }

    stats = _group_stats(candidates, attr_key)
    priv = _identify_privileged(stats, privileged_group)
    priv_rate = stats[priv]["rate"]

    unprivileged: dict[str, Any] = {}
    all_pass = True

    for group, s in stats.items():
        if group == priv:
            continue
        if priv_rate == 0:
            group_dir = None
            passes = True  # both groups at 0 — no adverse impact
        else:
            group_dir = round(s["rate"] / priv_rate, 6)
            passes = group_dir >= 0.80
            if not passes:
                all_pass = False

        unprivileged[group] = {
            "rate": s["rate"],
            "dir": group_dir,
            "passes_four_fifths": passes,
        }

    # Overall DIR: minimum across all unprivileged groups (most adverse)
    dir_values = [v["dir"] for v in unprivileged.values() if v["dir"] is not None]
    overall_dir = round(min(dir_values), 6) if dir_values else None

    return {
        "groups": stats,
        "dir": overall_dir,
        "privileged_group": priv,
        "unprivileged_groups": unprivileged,
        "passes_four_fifths": all_pass,
    }


def equalize_thresholds(
    candidates: list[dict[str, Any]],
    attr_key: str,
    target_dir_min: float = 0.80,
    target_dir_max: float = 1.25,
    global_threshold: float = 0.70,
) -> dict[str, Any]:
    """
    Compute per-group confidence thresholds so that disparate impact ratios
    across all groups land in [target_dir_min, target_dir_max].

    Strategy (Threshold Equalization):
    - The privileged group (highest current selection rate) keeps the global
      threshold as its starting point.
    - For under-represented groups (DIR < target_dir_min), their per-group
      threshold is *lowered* until their rate rises enough to reach target_dir_min.
    - For over-represented groups (DIR > target_dir_max), their threshold is
      *raised* until their rate falls to target_dir_max.
    - No group's threshold is lowered below `global_threshold * 0.5` (safety
      floor so the adjustment remains defensible).
    - No group's threshold is raised above 1.0.

    The binary search per group converges in O(log₂ 200) ≈ 8 iterations.

    Parameters
    ----------
    candidates : list of dicts
        Must contain: attr_key, "selected" (bool), "score" (float),
        "student_id" (int), "full_name" (str), "roll_number" (str).
    attr_key : str
        Protected attribute column name.
    target_dir_min : float
        Lower bound of acceptable DIR range (default 0.80 = 4/5ths rule).
    target_dir_max : float
        Upper bound (default 1.25 = inverse 4/5ths).
    global_threshold : float
        The existing default confidence gate (default 0.70). Used as a
        reference; also enforced as a lower-bound floor for privileged group.

    Returns
    -------
    dict with keys:
        group_thresholds   : dict mapping group → float threshold
        adjusted_candidates: list of dicts — each candidate dict with an
                             added "mitigated_selected" (bool),
                             "fairness_adjusted" (bool), and
                             "fairness_reason" (str | None).
        metrics_before     : result of disparate_impact_ratio before mitigation
        metrics_after      : result of disparate_impact_ratio after mitigation
    """
    if not candidates:
        return {
            "group_thresholds": {},
            "adjusted_candidates": [],
            "metrics_before": disparate_impact_ratio([], attr_key),
            "metrics_after": disparate_impact_ratio([], attr_key),
        }

    # Identify privileged group from current selections
    before_metrics = disparate_impact_ratio(candidates, attr_key)
    priv_group = before_metrics["privileged_group"]

    # Collect all unique groups
    all_groups = {(c.get(attr_key) or "Unknown") for c in candidates}

    # ------------------------------------------------------------------ #
    # Binary search per group                                             #
    # ------------------------------------------------------------------ #
    SAFETY_FLOOR = global_threshold * 0.5  # never drop below this

    def _selection_rate_at_threshold(group: str, threshold: float) -> float:
        """Selection rate for a group given a per-group threshold on 'score'."""
        group_candidates = [
            c for c in candidates
            if (c.get(attr_key) or "Unknown") == group
        ]
        if not group_candidates:
            return 0.0
        selected = sum(1 for c in group_candidates if c.get("score", 0.0) >= threshold)
        return selected / len(group_candidates)

    # Privileged group keeps global_threshold as its threshold
    priv_rate = _selection_rate_at_threshold(priv_group, global_threshold)

    group_thresholds: dict[str, float] = {priv_group: global_threshold}

    for group in all_groups:
        if group == priv_group:
            continue

        current_rate = _selection_rate_at_threshold(group, global_threshold)

        if priv_rate == 0:
            # Both at 0 — no adjustment needed
            group_thresholds[group] = global_threshold
            continue

        current_dir = current_rate / priv_rate

        if target_dir_min <= current_dir <= target_dir_max:
            # Already in range
            group_thresholds[group] = global_threshold
            continue

        if current_dir < target_dir_min:
            # Need to LOWER threshold to include more from this group
            lo, hi = SAFETY_FLOOR, global_threshold
            for _ in range(40):  # converge in ≤40 bisection steps
                mid = (lo + hi) / 2.0
                rate = _selection_rate_at_threshold(group, mid)
                d = rate / priv_rate if priv_rate > 0 else 0.0
                if d < target_dir_min:
                    hi = mid
                else:
                    lo = mid
                if hi - lo < 1e-5:
                    break
            group_thresholds[group] = round(lo, 5)

        else:
            # current_dir > target_dir_max: RAISE threshold
            lo, hi = global_threshold, 1.0
            for _ in range(40):
                mid = (lo + hi) / 2.0
                rate = _selection_rate_at_threshold(group, mid)
                d = rate / priv_rate if priv_rate > 0 else 0.0
                if d > target_dir_max:
                    lo = mid
                else:
                    hi = mid
                if hi - lo < 1e-5:
                    break
            group_thresholds[group] = round(hi, 5)

    # ------------------------------------------------------------------ #
    # Apply adjusted thresholds to candidates                             #
    # ------------------------------------------------------------------ #
    adjusted: list[dict[str, Any]] = []

    for c in candidates:
        group = c.get(attr_key) or "Unknown"
        threshold = group_thresholds.get(group, global_threshold)
        score = c.get("score", 0.0)

        original_selected = c.get("selected", False)
        mitigated_selected = score >= threshold

        fairness_adjusted = mitigated_selected != original_selected
        fairness_reason: str | None = None

        if fairness_adjusted:
            if mitigated_selected and not original_selected:
                fairness_reason = (
                    f"Included via fairness-adjusted threshold "
                    f"({threshold:.3f}) for {attr_key} group '{group}' "
                    f"(original gate: {global_threshold:.2f})."
                )
            elif not mitigated_selected and original_selected:
                fairness_reason = (
                    f"Excluded via fairness-adjusted threshold "
                    f"({threshold:.3f}) for {attr_key} group '{group}' "
                    f"(original gate: {global_threshold:.2f})."
                )

        entry = {**c}
        entry["mitigated_selected"] = mitigated_selected
        entry["fairness_adjusted"] = fairness_adjusted
        entry["fairness_reason"] = fairness_reason
        adjusted.append(entry)

    # Compute after-metrics using mitigated_selected
    after_candidates = [
        {**c, "selected": c["mitigated_selected"]} for c in adjusted
    ]
    after_metrics = disparate_impact_ratio(after_candidates, attr_key)

    return {
        "group_thresholds": group_thresholds,
        "adjusted_candidates": adjusted,
        "metrics_before": before_metrics,
        "metrics_after": after_metrics,
    }
