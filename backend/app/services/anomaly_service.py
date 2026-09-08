import numpy as np
from typing import Dict, Any, List, Optional
from functools import lru_cache
from sklearn.ensemble import IsolationForest
from backend.app.services.classifier_service import get_classifier_service


class AnomalyDetectionService:
    def __init__(self):
        self.classifier_service = get_classifier_service()
        self.vectorizer = self.classifier_service.vectorizer
        self.iso_forest = None
        self._fit_isolation_forest()

    def _fit_isolation_forest(self):
        # Create a synthetic/sample baseline matrix for fitting IsolationForest
        # using vocabulary size from classifier vectorizer (global / backward-compat mode)
        vocab_size = len(self.vectorizer.get_feature_names_out())
        np.random.seed(42)
        # Generate baseline sparse feature distributions
        synthetic_baseline = np.random.exponential(scale=0.05, size=(100, vocab_size))
        synthetic_baseline = np.clip(synthetic_baseline, 0, 1)

        self.iso_forest = IsolationForest(
            n_estimators=100,
            contamination=0.1,  # Expect ~10% potential anomalies
            random_state=42
        )
        self.iso_forest.fit(synthetic_baseline)

    def _build_peer_vectors(self, peer_students: List[Any]) -> Optional[np.ndarray]:
        """Convert a list of Student ORM objects to a dense TF-IDF matrix."""
        rows = []
        for s in peer_students:
            full_text = self.classifier_service.formulate_feature_text(
                resume_text=s.raw_resume_text or "",
                skills=s.skills or [],
                projects=s.projects or [],
            )
            vec = self.vectorizer.transform([full_text])
            rows.append(vec.toarray()[0])
        if not rows:
            return None
        return np.array(rows)

    def _fit_on_peers(self, peer_matrix: np.ndarray) -> IsolationForest:
        """Fit a fresh IsolationForest on the given peer-group matrix."""
        n_samples = peer_matrix.shape[0]
        # Clamp n_estimators so it never exceeds sample count
        n_est = min(100, max(10, n_samples))
        contamination = min(0.4, max(0.05, 1.0 / n_samples)) if n_samples > 1 else 0.1
        iso = IsolationForest(
            n_estimators=n_est,
            contamination=contamination,
            random_state=42,
        )
        iso.fit(peer_matrix)
        return iso

    def evaluate_student_anomaly(
        self,
        resume_text: str,
        skills: List[str],
        projects: List[Any],
        peer_students: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        full_text = self.classifier_service.formulate_feature_text(resume_text, skills, projects)
        vec = self.vectorizer.transform([full_text])
        dense_vec = vec.toarray()[0]

        scope_warning: Optional[str] = None
        scope_label = "global"

        if peer_students is not None:
            # --- Scoped mode: re-fit IsolationForest on peer group ---
            scope_label = f"section (n={len(peer_students)})"
            if len(peer_students) < 10:
                scope_warning = (
                    f"Section has only {len(peer_students)} student(s); "
                    "scoped anomaly scores may be unreliable with peer group under 10 students."
                )
            peer_matrix = self._build_peer_vectors(peer_students)
            if peer_matrix is not None and len(peer_matrix) >= 2:
                active_forest = self._fit_on_peers(peer_matrix)
            else:
                # Fall back to global forest if peers too few to fit
                active_forest = self.iso_forest
                scope_warning = "Peer group too small to fit IsolationForest; fell back to global model."
        else:
            # --- Global mode (backward-compatible) ---
            active_forest = self.iso_forest

        # 1. Isolation Forest score
        # decision_function: higher is normal, lower is anomalous (range roughly -0.5 to +0.5)
        raw_score = float(active_forest.decision_function([dense_vec])[0])
        pred = int(active_forest.predict([dense_vec])[0])  # +1 normal, -1 anomaly

        # Normalize score to 0.0 (normal) -> 1.0 (anomalous)
        anomaly_score = float(np.clip(0.5 - raw_score, 0.0, 1.0))
        is_anomalous = bool(pred == -1 or anomaly_score >= 0.55)

        # 2. Rule-based anomaly heuristics for keyword stuffing / exaggeration
        reasons = []
        nonzero_count = np.count_nonzero(dense_vec)
        max_val = float(np.max(dense_vec)) if nonzero_count > 0 else 0.0

        if nonzero_count > 80:
            reasons.append("Excessive keyword density detected (high risk of resume keyword stuffing).")
        if max_val > 0.75:
            reasons.append("Unusually high single-term frequency spike (repeated keyword padding).")
        if (skills or []) and len(skills) > 25:
            reasons.append("Unusually high number of claimed skills (>25) relative to batch average.")

        if is_anomalous and not reasons:
            reasons.append("Feature vector falls in outlier region of Isolation Forest density distribution.")

        status = "FLAGGED_FOR_ADMIN_AUDIT" if is_anomalous else "APPROVE_FOR_PIPELINE"

        result = {
            "anomaly_score": round(anomaly_score, 3),
            "raw_decision_score": round(raw_score, 4),
            "is_anomalous": is_anomalous,
            "audit_status": status,
            "anomaly_reasons": reasons if is_anomalous else ["Profile aligns with normal feature distribution."],
            "recommendation": (
                "Gate for Admin review before recruiter matching"
                if is_anomalous
                else "Normal profile — safe for adaptive matching pipeline"
            ),
            "scope": scope_label,
        }
        if scope_warning:
            result["scope_warning"] = scope_warning
        return result

    def evaluate_student_anomaly_global(
        self,
        resume_text: str,
        skills: List[str],
        projects: List[Any],
    ) -> Dict[str, Any]:
        """Always run against the global synthetic baseline (no peer scoping)."""
        return self.evaluate_student_anomaly(resume_text, skills, projects, peer_students=None)


@lru_cache()
def get_anomaly_detection_service() -> AnomalyDetectionService:
    return AnomalyDetectionService()
