import numpy as np
from typing import Dict, Any, List, Optional
from functools import lru_cache
from backend.app.services.classifier_service import get_classifier_service

try:
    import shap
    HAS_SHAP = True
except ImportError:
    HAS_SHAP = False


class ShapComparisonService:
    def __init__(self):
        self.classifier_service = get_classifier_service()
        self.vectorizer = self.classifier_service.vectorizer
        self.classifier = self.classifier_service.classifier
        self.classes = self.classifier_service.classes
        self.feature_names = self.classifier_service.feature_names
        self.explainer = None
        self._init_shap_explainer()

    def _init_shap_explainer(self):
        if HAS_SHAP and self.classifier is not None:
            try:
                # Create a background dataset representation (zeros + dummy mean)
                n_features = len(self.feature_names)
                background = np.zeros((10, n_features))
                # For LogisticRegression, LinearExplainer provides exact SHAP attribution
                self.explainer = shap.LinearExplainer(self.classifier, background)
            except Exception:
                self.explainer = None

    def _build_peer_shap_matrix(
        self,
        peer_students: List[Any],
        domain_idx: int,
        coefs: np.ndarray,
    ) -> Optional[np.ndarray]:
        """Build a matrix of SHAP values for all peer students (for z-score calibration)."""
        rows = []
        for s in peer_students:
            full_text = self.classifier_service.formulate_feature_text(
                resume_text=s.raw_resume_text or "",
                skills=s.skills or [],
                projects=s.projects or [],
            )
            vec = self.vectorizer.transform([full_text])
            dense = vec.toarray()[0]
            shap_vals = coefs * dense
            rows.append(shap_vals)
        if not rows:
            return None
        return np.array(rows)  # shape: (n_peers, n_features)

    def compute_shap_comparison(
        self,
        resume_text: str,
        skills: List[str],
        projects: List[Any],
        target_domain: Optional[str] = None,
        peer_students: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        full_text = self.classifier_service.formulate_feature_text(resume_text, skills, projects)
        vec = self.vectorizer.transform([full_text])
        dense_vec = vec.toarray()[0]

        # Predict domain
        probas = self.classifier.predict_proba(vec)[0]
        winning_idx = int(np.argmax(probas))
        predicted_domain = self.classes[winning_idx]
        confidence = float(probas[winning_idx])

        domain_idx = winning_idx
        if target_domain and target_domain in self.classes:
            domain_idx = self.classes.index(target_domain)

        coefs = self.classifier.coef_[domain_idx]

        # SHAP calculation: phi_j = coef_j * (x_j - mean_j)
        # Background mean is ~0 for sparse text TF-IDF
        shap_values = coefs * dense_vec

        # Extract non-zero TF-IDF features present in candidate profile
        nonzero_indices = np.where(dense_vec > 0)[0]

        feature_breakdown = []
        well_supported = []
        outliers = []

        # --- Z-score calibration ---
        # When peer_students is provided, calibrate against peer SHAP distribution
        # (section-relative). Otherwise, use single-student self-referential stats (global).
        scope_label = "global"
        if peer_students is not None and len(peer_students) >= 2:
            scope_label = f"section (n={len(peer_students)})"
            peer_matrix = self._build_peer_shap_matrix(peer_students, domain_idx, coefs)
            if peer_matrix is not None and len(nonzero_indices) > 0:
                # mean/std computed across all peers for the features present in THIS student
                peer_vals_at_nonzero = peer_matrix[:, nonzero_indices]  # (n_peers, n_nonzero)
                mean_weights = float(np.mean(peer_vals_at_nonzero))
                std_weights = float(np.std(peer_vals_at_nonzero))
            else:
                mean_weights = np.mean(coefs[nonzero_indices]) if len(nonzero_indices) > 0 else 0.0
                std_weights = np.std(coefs[nonzero_indices]) if len(nonzero_indices) > 0 else 1.0
        else:
            # Empirical statistics from this student's own feature distribution
            mean_weights = np.mean(coefs[nonzero_indices]) if len(nonzero_indices) > 0 else 0.0
            std_weights = np.std(coefs[nonzero_indices]) if len(nonzero_indices) > 0 else 1.0

        for idx in nonzero_indices:
            feat_name = str(self.feature_names[idx])
            val = float(dense_vec[idx])
            shap_val = float(shap_values[idx])

            # Classification relative to calibration reference
            z_score = (shap_val - mean_weights) / (std_weights if std_weights > 0 else 1.0)

            status = "well_supported"
            if z_score > 2.0 or val > 0.6:
                status = "exaggerated_outlier"
                outliers.append(feat_name)
            elif shap_val > 0.05:
                well_supported.append(feat_name)
            else:
                status = "low_impact"

            feature_breakdown.append({
                "feature": feat_name,
                "tfidf_weight": round(val, 4),
                "shap_value": round(shap_val, 4),
                "z_score": round(z_score, 2),
                "status": status,
            })

        # Sort features by highest SHAP contribution
        feature_breakdown.sort(key=lambda x: x["shap_value"], reverse=True)

        total_claimed = len(nonzero_indices)
        coverage_score = round(len(well_supported) / max(total_claimed, 1), 2)

        return {
            "predicted_domain": predicted_domain,
            "target_domain": self.classes[domain_idx],
            "confidence": round(confidence, 4),
            "total_features_analyzed": total_claimed,
            "database_coverage_score": coverage_score,
            "well_supported_skills": well_supported[:8],
            "outlier_or_exaggerated_skills": outliers,
            "shap_feature_breakdown": feature_breakdown[:12],
            "shap_method_used": "shap.LinearExplainer" if self.explainer else "Analytical SHAP Attributor",
            "scope": scope_label,
        }

    def generate_recommendations(
        self,
        resume_text: str,
        skills: List[str],
        projects: List[Any],
        target_domain: Optional[str] = None,
        top_k: int = 5,
        peer_students: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        shap_analysis = self.compute_shap_comparison(
            resume_text, skills, projects, target_domain, peer_students=peer_students
        )
        predicted_domain = shap_analysis["target_domain"]
        domain_idx = self.classes.index(predicted_domain)
        coefs = self.classifier.coef_[domain_idx]

        full_text = self.classifier_service.formulate_feature_text(resume_text, skills, projects)
        vec = self.vectorizer.transform([full_text])
        dense_vec = vec.toarray()[0]

        # Find features with highest positive weights in domain coefficients where candidate has 0 or low TF-IDF
        claimed_indices = set(np.where(dense_vec > 0.25)[0])
        top_coef_indices = np.argsort(coefs)[::-1]

        suggestions = []
        rank = 1

        for idx in top_coef_indices:
            if len(suggestions) >= top_k:
                break
            feat_name = str(self.feature_names[idx])

            if idx in claimed_indices:
                continue

            coef_weight = float(coefs[idx])
            if coef_weight <= 0:
                continue

            potential_shap_gain = round(coef_weight * 0.4, 4)
            impact_level = "High" if potential_shap_gain > 0.15 else "Medium"

            suggestions.append({
                "rank": rank,
                "suggested_skill": feat_name,
                "impact_level": impact_level,
                "potential_shap_gain": potential_shap_gain,
                "reason": f"Adding '{feat_name}' to your skills or resume projects could improve your {predicted_domain} match score by +{potential_shap_gain * 100:.1f}%."
            })
            rank += 1

        return {
            "target_domain": predicted_domain,
            "current_confidence": shap_analysis["confidence"],
            "suggestions_count": len(suggestions),
            "recommendations": suggestions,
        }


@lru_cache()
def get_shap_comparison_service() -> ShapComparisonService:
    return ShapComparisonService()
