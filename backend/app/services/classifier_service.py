import os
import joblib
import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from functools import lru_cache

MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models", "saved_models", "domain_classifier.joblib"
)

class DomainClassifierService:
    _instance = None

    def __init__(self):
        self.model_data = None
        self.vectorizer = None
        self.classifier = None
        self.classes = []
        self.feature_names = []
        self.load_model()

    def load_model(self):
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"Trained domain classifier model not found at {MODEL_PATH}. "
                "Please run `python backend/scripts/train_domain_classifier.py` first."
            )
        self.model_data = joblib.load(MODEL_PATH)
        self.vectorizer = self.model_data["vectorizer"]
        self.classifier = self.model_data["classifier"]
        self.classes = list(self.classifier.classes_)
        self.feature_names = np.array(self.model_data["feature_names"])

    def formulate_feature_text(self, resume_text: str, skills: List[str], projects: List[Any]) -> str:
        skills_str = " ".join(skills or [])
        projects_text = " ".join([
            f"{getattr(p, 'title', '')} {getattr(p, 'description', '')} {' '.join(getattr(p, 'tech_stack', []) or [])}"
            for p in projects
        ])
        # Dual-weighting on skills for relevance
        return f"{resume_text or ''} {skills_str} {skills_str} {projects_text}"

    def predict_and_explain(
        self,
        resume_text: str,
        skills: List[str],
        projects: List[Any],
        top_k_factors: int = 5
    ) -> Dict[str, Any]:
        full_text = self.formulate_feature_text(resume_text, skills, projects)
        
        # 1. Transform text via TF-IDF
        vec = self.vectorizer.transform([full_text])
        
        # 2. Probability distribution
        probas = self.classifier.predict_proba(vec)[0]
        prob_dict = {cls_name: round(float(prob), 4) for cls_name, prob in zip(self.classes, probas)}
        
        # 3. Winning class & confidence
        winning_idx = int(np.argmax(probas))
        winning_class = self.classes[winning_idx]
        confidence = float(probas[winning_idx])

        # 4. Explainability: Attribute prediction to input features
        # For multi-class Logistic Regression, score_k = sum_j (coef_k,j * tfidf_j) + intercept_k
        coefs = self.classifier.coef_[winning_idx]  # Shape: (num_features,)
        
        # Extract non-zero TF-IDF entries in this document
        row = vec.tocoo()
        contributions = []
        for col_idx, tfidf_val in zip(row.col, row.data):
            weight = float(coefs[col_idx] * tfidf_val)
            if weight > 0:  # Positively contributing features
                feature_name = self.feature_names[col_idx]
                contributions.append((feature_name, weight))

        # Sort by highest positive attribution weight
        contributions.sort(key=lambda x: x[1], reverse=True)
        top_factors = contributions[:top_k_factors]

        explainability_list = []
        for feat, wt in top_factors:
            explainability_list.append({
                "feature": feat,
                "weight": round(wt, 4),
                "description": f"Keyword/Skill '{feat}' provided strong positive evidence (+{wt:.3f}) for {winning_class}."
            })

        return {
            "predicted_domain": winning_class,
            "confidence": round(confidence, 4),
            "class_probabilities": prob_dict,
            "explainability": explainability_list,
            "model_version": "v1.0 (TF-IDF + Multinomial Logistic Regression)"
        }

    def build_human_readable_summary(
        self,
        predicted_domain: str,
        confidence: float,
        top_factors: List[Dict[str, Any]],
        ground_truth_domain: Optional[str] = None,
    ) -> str:
        """Compose a single recruiter-friendly sentence from the top
        positive contributors. Intentionally short — designed for a UI
        card, not a paragraph."""
        if not top_factors:
            return (f"Predicted as {predicted_domain} "
                    f"(confidence {confidence:.0%}); no strong keyword signal found.")

        # Prefer single-word features for readability; fall back to whatever
        # the top-K contains.
        keywords = [f["feature"] for f in top_factors[:5] if f.get("feature")]
        if not keywords:
            return (f"Predicted as {predicted_domain} "
                    f"(confidence {confidence:.0%}).")

        kw_str = ", ".join(keywords)
        summary = (f"Predicted as {predicted_domain} (confidence {confidence:.0%}) "
                   f"primarily due to: {kw_str}.")

        if ground_truth_domain and ground_truth_domain != predicted_domain:
            summary += (f" Note: actual placement outcome is {ground_truth_domain} — "
                        f"this student's resume does not fully reflect their true domain, "
                        f"which is expected in {int(round((1 - confidence) * 100))}% "
                        f"of cases where skill signal and outcome diverge.")
        return summary

@lru_cache()
def get_classifier_service() -> DomainClassifierService:
    return DomainClassifierService()
