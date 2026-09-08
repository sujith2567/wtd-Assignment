"""
5-Fold Cross-Validation Stress Test for the Domain-Suitability Classifier.

Why this exists:
    The single 80/20 split in train_domain_classifier.py happens to yield 100%
    accuracy on the synthetic dataset. A single split is a noisy estimator of
    generalization — the chosen 80-student test fold may simply be "easy."
    5-fold stratified cross-validation reports the mean and standard deviation
    of the metric across all 5 folds, giving a much more defensible number for
    the project report.

What it does:
    1. Loads the same student dataset (resume + skills + projects + label) used
       by train_domain_classifier.py.
    2. Builds the identical TF-IDF + Logistic Regression pipeline.
    3. Runs StratifiedKFold(n_splits=5, shuffle=True, random_state=42) over
       the full labeled set.
    4. Aggregates per-fold accuracy / macro-F1 / weighted-F1.
    5. Computes and saves:
        - A 5x5 summed confusion matrix (counts aggregated across all folds).
        - A per-class mean precision/recall/F1 across folds.
        - A JSON report (cv_evaluation_metrics.json) for the report.
    6. Does NOT overwrite the deployed model artifact — the training script
       remains the source of truth for the production model.

Run:
    python backend\scripts\cross_validate_domain_classifier.py
"""

import sys
import os
import json
from datetime import datetime
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_recall_fscore_support,
    confusion_matrix,
    classification_report,
)
from sqlalchemy.orm import joinedload

# Ensure root directory is in sys.path so `backend.*` imports resolve
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.core.database import SessionLocal
from backend.app.models.student import Student, StudentProject

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
METRICS_FILE = os.path.join(SCRIPT_DIR, "cv_evaluation_metrics.json")

N_SPLITS = 5
RANDOM_STATE = 42


def load_dataset_from_db() -> pd.DataFrame:
    """Replicates the feature construction used at training time so the CV
    pipeline sees the same input distribution."""
    print("[*] Fetching student and project records from database...")
    db = SessionLocal()
    try:
        students = (
            db.query(Student)
            .options(joinedload(Student.projects))
            .filter(Student.domain_label.isnot(None))
            .all()
        )
        print(f" -> Successfully fetched {len(students)} student records.")

        data = []
        for s in students:
            skills_str = " ".join(s.skills or [])
            projects_text = " ".join(
                [f"{p.title} {p.description} {' '.join(p.tech_stack or [])}" for p in s.projects]
            )
            # Same weighted concatenation as train_domain_classifier.py
            full_text = f"{s.raw_resume_text or ''} {skills_str} {skills_str} {projects_text}"
            data.append({"student_id": s.id, "text": full_text, "label": s.domain_label})

        return pd.DataFrame(data)
    finally:
        db.close()


def build_pipeline():
    """Identical configuration to the deployed model so the CV score is
    a fair estimate of the deployed model's true performance."""
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=2500,
        sublinear_tf=True,
        stop_words="english",
        min_df=2,
    )
    classifier = LogisticRegression(
        C=1.0,
        max_iter=1000,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        solver="lbfgs",
    )
    return vectorizer, classifier


def cross_validate():
    print("\n========================================================================")
    print(f"  5-FOLD CROSS-VALIDATION STRESS TEST (StratifiedKFold, k={N_SPLITS})")
    print("========================================================================\n")

    df = load_dataset_from_db()
    total_samples = len(df)
    if total_samples < 2 * N_SPLITS:
        print(f"[!] Not enough samples ({total_samples}) for {N_SPLITS}-fold CV.")
        return

    print(f"[*] Loaded {total_samples} labeled profiles.\n")
    print("[*] Class distribution:")
    for label, count in df["label"].value_counts().items():
        print(f"    - {label:<38}: {count} ({count/total_samples*100:.1f}%)")

    X = df["text"].values
    y = df["label"].values
    classes = sorted(np.unique(y).tolist())

    skf = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)

    fold_metrics = []
    aggregated_cm = np.zeros((len(classes), len(classes)), dtype=int)
    per_class_prf = {c: {"precision": [], "recall": [], "f1": []} for c in classes}

    print(f"\n[*] Running {N_SPLITS}-fold CV...\n")

    for fold_idx, (train_idx, test_idx) in enumerate(skf.split(X, y), start=1):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        vectorizer, classifier = build_pipeline()
        X_train_vec = vectorizer.fit_transform(X_train)
        X_test_vec = vectorizer.transform(X_test)

        classifier.fit(X_train_vec, y_train)
        y_pred = classifier.predict(X_test_vec)

        acc = accuracy_score(y_test, y_pred)
        macro_f1 = f1_score(y_test, y_pred, average="macro", zero_division=0)
        weighted_f1 = f1_score(y_test, y_pred, average="weighted", zero_division=0)

        # Confusion matrix (fold-level, in global class order)
        cm = confusion_matrix(y_test, y_pred, labels=classes)
        aggregated_cm += cm

        # Per-class precision/recall/f1
        prec, rec, f1, _ = precision_recall_fscore_support(
            y_test, y_pred, labels=classes, zero_division=0
        )
        for c, p, r, f in zip(classes, prec, rec, f1):
            per_class_prf[c]["precision"].append(float(p))
            per_class_prf[c]["recall"].append(float(r))
            per_class_prf[c]["f1"].append(float(f))

        fold_metrics.append(
            {
                "fold": fold_idx,
                "train_size": int(len(train_idx)),
                "test_size": int(len(test_idx)),
                "accuracy": float(acc),
                "macro_f1": float(macro_f1),
                "weighted_f1": float(weighted_f1),
            }
        )

        print(
            f"  Fold {fold_idx}: acc={acc:.4f}  macro_f1={macro_f1:.4f}  "
            f"weighted_f1={weighted_f1:.4f}  (test n={len(test_idx)})"
        )

    # --- Aggregate statistics ------------------------------------------------
    accs = [m["accuracy"] for m in fold_metrics]
    macros = [m["macro_f1"] for m in fold_metrics]
    weighteds = [m["weighted_f1"] for m in fold_metrics]

    summary = {
        "accuracy_mean": float(np.mean(accs)),
        "accuracy_std": float(np.std(accs, ddof=1)),
        "macro_f1_mean": float(np.mean(macros)),
        "macro_f1_std": float(np.std(macros, ddof=1)),
        "weighted_f1_mean": float(np.mean(weighteds)),
        "weighted_f1_std": float(np.std(weighteds, ddof=1)),
    }

    per_class_summary = {
        c: {
            "precision_mean": float(np.mean(per_class_prf[c]["precision"])),
            "precision_std": float(np.std(per_class_prf[c]["precision"], ddof=1)),
            "recall_mean": float(np.mean(per_class_prf[c]["recall"])),
            "recall_std": float(np.std(per_class_prf[c]["recall"], ddof=1)),
            "f1_mean": float(np.mean(per_class_prf[c]["f1"])),
            "f1_std": float(np.std(per_class_prf[c]["f1"], ddof=1)),
        }
        for c in classes
    }

    # --- Print consolidated report ------------------------------------------
    print("\n========================================================================")
    print("                CROSS-VALIDATION SUMMARY (k=5)")
    print("========================================================================")
    print(f"  Accuracy:      {summary['accuracy_mean']:.4f}  (+/- {summary['accuracy_std']:.4f})")
    print(f"  Macro F1:      {summary['macro_f1_mean']:.4f}  (+/- {summary['macro_f1_std']:.4f})")
    print(f"  Weighted F1:   {summary['weighted_f1_mean']:.4f}  (+/- {summary['weighted_f1_std']:.4f})")
    print("------------------------------------------------------------------------")
    print("\n[*] Per-class (mean across 5 folds):\n")
    header = f"  {'Domain':<38}{'Precision':>12}{'Recall':>10}{'F1':>10}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for c in classes:
        s = per_class_summary[c]
        print(
            f"  {c:<38}"
            f"{s['precision_mean']:>12.4f}"
            f"{s['recall_mean']:>10.4f}"
            f"{s['f1_mean']:>10.4f}"
        )

    print("\n[*] Aggregated confusion matrix (sum of all 5 folds, rows=actual, cols=predicted):")
    col_w = 12
    label_w = 40
    print("-" * (label_w + col_w * len(classes)))
    print(f"  {'Actual / Pred':<38}" + "".join([f"{c[:10]:>12}" for c in classes]))
    print("-" * (label_w + col_w * len(classes)))
    for i, row in enumerate(aggregated_cm):
        print(f"  {classes[i]:<38}" + "".join([f"{val:>12}" for val in row]))
    print("-" * (label_w + col_w * len(classes)))

    # --- Persist JSON report ------------------------------------------------
    report = {
        "evaluation_type": "5-fold Stratified Cross-Validation",
        "model_type": "TF-IDF + Multi-class Logistic Regression",
        "training_timestamp": datetime.utcnow().isoformat(),
        "n_splits": N_SPLITS,
        "random_state": RANDOM_STATE,
        "total_dataset_size": int(total_samples),
        "folds": fold_metrics,
        "summary": summary,
        "per_class": per_class_summary,
        "classes": classes,
        "aggregated_confusion_matrix": aggregated_cm.tolist(),
    }

    with open(METRICS_FILE, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n[+] CV report saved to: {METRICS_FILE}")
    print("========================================================================\n")
    return report


if __name__ == "__main__":
    cross_validate()
