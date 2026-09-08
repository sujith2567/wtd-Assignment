import sys
import os
import json
from datetime import datetime
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, f1_score
import joblib

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.core.database import SessionLocal
from backend.app.models.student import Student, StudentProject

SAVED_MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "models", "saved_models")
os.makedirs(SAVED_MODELS_DIR, exist_ok=True)
MODEL_FILE = os.path.join(SAVED_MODELS_DIR, "domain_classifier.joblib")
METRICS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evaluation_metrics.json")

from sqlalchemy.orm import joinedload

def load_dataset_from_db():
    print("[*] Fetching student and project records from database...")
    db = SessionLocal()
    try:
        students = db.query(Student).options(joinedload(Student.projects)).filter(Student.domain_label.isnot(None)).all()
        print(f" -> Successfully fetched {len(students)} student records.")
        data = []
        for s in students:
            skills_str = " ".join(s.skills or [])
            projects_text = " ".join([f"{p.title} {p.description} {' '.join(p.tech_stack or [])}" for p in s.projects])
            
            # Weighted feature concatenation: emphasize skills and projects
            full_text = f"{s.raw_resume_text or ''} {skills_str} {skills_str} {projects_text}"
            
            data.append({
                "student_id": s.id,
                "text": full_text,
                "label": s.domain_label
            })
            
        df = pd.DataFrame(data)
        return df
    finally:
        db.close()

def train_and_evaluate():
    print("\n========================================================================")
    print("  AI CORE: TRAINING MULTI-CLASS DOMAIN-SUITABILITY CLASSIFIER")
    print("========================================================================\n")

    df = load_dataset_from_db()
    total_samples = len(df)
    print(f"[*] Loaded {total_samples} labeled student profiles from MySQL database.")
    
    if total_samples < 20:
        print("[!] Not enough samples. Please run generate_synthetic_data.py first.")
        return

    # Check class distribution
    print("\n[*] Class Distribution in Ground Truth:")
    for label, count in df["label"].value_counts().items():
        print(f"    - {label:<38}: {count} students ({count/total_samples*100:.1f}%)")

    # Stratified Train-Test Split (80% Train, 20% Held-out Test)
    X = df["text"]
    y = df["label"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    print(f"\n[*] Dataset Partition: {len(X_train)} training samples, {len(X_test)} test samples (80/20 Stratified).")

    # 1. Feature Extraction: Sublinear TF-IDF with unigrams + bigrams
    print("[*] Extracting sublinear TF-IDF features (unigrams & bigrams)...")
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=2500,
        sublinear_tf=True,
        stop_words="english",
        min_df=2
    )
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)
    print(f" -> TF-IDF Vocabulary Size: {len(vectorizer.get_feature_names_out())} features.")

    # 2. Model: Balanced Multi-class Logistic Regression with L2 Regularization
    print("[*] Training Multi-class Logistic Regression Classifier (L2 regularization)...")
    clf = LogisticRegression(
        C=1.0,
        max_iter=1000,
        class_weight="balanced",
        random_state=42,
        solver="lbfgs"
    )
    clf.fit(X_train_vec, y_train)
    print(" -> Model converged successfully!")

    # 3. Evaluation on Test Set
    y_pred = clf.predict(X_test_vec)
    accuracy = float(accuracy_score(y_test, y_pred))
    macro_f1 = float(f1_score(y_test, y_pred, average="macro"))
    weighted_f1 = float(f1_score(y_test, y_pred, average="weighted"))

    classes = sorted(list(clf.classes_))
    report_dict = classification_report(y_test, y_pred, target_names=classes, output_dict=True)
    report_str = classification_report(y_test, y_pred, target_names=classes)
    cm = confusion_matrix(y_test, y_pred, labels=classes)

    print("\n========================================================================")
    print("                      EVALUATION RESULTS (TEST SPLIT)")
    print("========================================================================")
    print(f"  Overall Accuracy:      {accuracy * 100:.2f}%")
    print(f"  Macro-Averaged F1:     {macro_f1:.4f}")
    print(f"  Weighted-Averaged F1:  {weighted_f1:.4f}")
    print("------------------------------------------------------------------------")
    print("\n[*] Detailed Classification Report:\n")
    print(report_str)

    print("\n[*] Confusion Matrix (Rows = Actual Ground Truth, Columns = Predicted):")
    title_label = "Actual / Pred"
    header = f"{title_label:<35}" + "".join([f"{c[:10]:>12}" for c in classes])
    print("-" * len(header))
    print(header)
    print("-" * len(header))
    for i, row in enumerate(cm):
        row_str = f"{classes[i]:<35}" + "".join([f"{val:>12}" for val in row])
        print(row_str)
    print("-" * len(header))

    # 4. Save Model Artifact to Disk
    model_payload = {
        "vectorizer": vectorizer,
        "classifier": clf,
        "classes": classes,
        "feature_names": vectorizer.get_feature_names_out(),
        "created_at": datetime.utcnow().isoformat(),
        "metrics": {
            "accuracy": accuracy,
            "macro_f1": macro_f1,
            "weighted_f1": weighted_f1,
            "test_samples": len(y_test),
            "train_samples": len(y_train)
        }
    }
    joblib.dump(model_payload, MODEL_FILE)
    print(f"\n[+] Trained model saved to: {MODEL_FILE}")

    # 5. Save JSON summary metrics
    metrics_summary = {
        "model_type": "TF-IDF + Multi-class Logistic Regression",
        "training_timestamp": datetime.utcnow().isoformat(),
        "total_dataset_size": total_samples,
        "train_samples": len(y_train),
        "test_samples": len(y_test),
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "classes": classes,
        "classification_report": report_dict,
        "confusion_matrix": cm.tolist()
    }
    with open(METRICS_FILE, "w") as f:
        json.dump(metrics_summary, f, indent=2)
    print(f"[+] Evaluation metrics exported to: {METRICS_FILE}")
    print("========================================================================\n")
    return metrics_summary

if __name__ == "__main__":
    train_and_evaluate()
