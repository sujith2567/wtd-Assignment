"""
Pydantic schemas for the Fairness-Aware Matching module.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


# --------------------------------------------------------------------------- #
# Sub-components                                                               #
# --------------------------------------------------------------------------- #

class GroupRate(BaseModel):
    """Selection rate statistics for a single demographic group."""
    group: str
    total: int
    selected: int
    selection_rate: float


class UnprivilegedGroupDir(BaseModel):
    """DIR detail for one unprivileged group relative to the privileged group."""
    group: str
    selection_rate: float
    dir: Optional[float] = None          # None when privileged rate == 0
    passes_four_fifths: bool


class FairnessMetrics(BaseModel):
    """Fairness statistics for one protected attribute (gender or category)."""
    attribute: str                        # e.g. "gender" or "category"
    group_rates: list[GroupRate]
    demographic_parity_difference: float
    disparate_impact_ratio: Optional[float] = None   # None if privileged rate == 0
    privileged_group: Optional[str] = None
    unprivileged_groups: list[UnprivilegedGroupDir] = []
    passes_four_fifths: bool


# --------------------------------------------------------------------------- #
# Endpoint responses                                                           #
# --------------------------------------------------------------------------- #

class FairnessAuditResponse(BaseModel):
    """Response for GET /fairness/audit/{job_id}."""
    job_id: int
    job_title: str
    total_candidates_evaluated: int
    total_selected: int
    buffer_matching_enabled: bool
    buffer_min_confidence: float
    gender_metrics: FairnessMetrics
    category_metrics: FairnessMetrics


class AdjustedCandidate(BaseModel):
    """A single candidate whose selection status may have changed after mitigation."""
    student_id: int
    full_name: str
    roll_number: str
    gender: Optional[str] = None
    category: Optional[str] = None
    score: float
    original_selected: bool
    mitigated_selected: bool
    changed: bool
    fairness_adjusted: bool
    fairness_reason: Optional[str] = None
    fit_explanation: Optional[str] = None
    fairness_note: Optional[str] = None


class GroupThreshold(BaseModel):
    """Per-group confidence threshold after equalization."""
    group: str
    threshold: float


class MitigationResponse(BaseModel):
    """Response for GET /fairness/mitigate/{job_id}."""
    job_id: int
    job_title: str
    total_candidates_evaluated: int
    buffer_matching_enabled: bool
    buffer_min_confidence: float
    global_threshold: float
    target_dir_min: float
    target_dir_max: float

    # Gender dimension
    gender_thresholds: list[GroupThreshold]
    gender_metrics_before: FairnessMetrics
    gender_metrics_after: FairnessMetrics

    # Category dimension
    category_thresholds: list[GroupThreshold]
    category_metrics_before: FairnessMetrics
    category_metrics_after: FairnessMetrics

    # Candidates whose selection changed in EITHER dimension
    changed_candidates: list[AdjustedCandidate]
