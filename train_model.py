"""Train and export the credit-card fraud detection model used by the Streamlit app.

The original notebook explored undersampling, SMOTE, several classifiers, and a
neural network. This production-facing version keeps the strongest, easiest-to-
serve baseline: robust scaling for Time/Amount, SMOTE applied only to the
training split, and logistic regression evaluated on the untouched test split.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import RobustScaler

REQUIRED_FEATURES = ["Time", *[f"V{i}" for i in range(1, 29)], "Amount"]
TARGET = "Class"


def _json_number(value: Any) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    return value


def validate_frame(df: pd.DataFrame) -> None:
    required = set(REQUIRED_FEATURES + [TARGET])
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    if not bool(df[TARGET].dropna().isin([0, 1]).all()):
        raise ValueError("Class must contain only 0 (legitimate) and 1 (fraud) labels.")
    if df[TARGET].nunique() < 2:
        raise ValueError("The uploaded dataset must contain both classes.")


def build_pipeline(smote_ratio: float, random_state: int) -> ImbPipeline:
    preprocess = ColumnTransformer(
        transformers=[
            ("robust_scale_amount_time", RobustScaler(), ["Time", "Amount"]),
        ],
        remainder="passthrough",
        verbose_feature_names_out=False,
    )
    return ImbPipeline(
        steps=[
            ("preprocess", preprocess),
            (
                "smote",
                SMOTE(sampling_strategy=smote_ratio, random_state=random_state),
            ),
            (
                "classifier",
                LogisticRegression(
                    C=0.5,
                    solver="liblinear",
                    max_iter=2000,
                    random_state=random_state,
                ),
            ),
        ]
    )


def _downsample(values: np.ndarray, max_points: int = 600) -> list[float]:
    values = np.asarray(values)
    if len(values) <= max_points:
        return values.tolist()
    indices = np.linspace(0, len(values) - 1, max_points, dtype=int)
    return values[indices].tolist()


def evaluate(y_true: pd.Series, probabilities: np.ndarray) -> dict[str, Any]:
    predictions = (probabilities >= 0.5).astype(int)
    cm = confusion_matrix(y_true, predictions, labels=[0, 1])
    fpr, tpr, roc_thresholds = roc_curve(y_true, probabilities)
    precision, recall, pr_thresholds = precision_recall_curve(y_true, probabilities)
    return {
        "threshold": 0.5,
        "accuracy": float(accuracy_score(y_true, predictions)),
        "precision": float(precision_score(y_true, predictions, zero_division=0)),
        "recall": float(recall_score(y_true, predictions, zero_division=0)),
        "f1": float(f1_score(y_true, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, probabilities)),
        "average_precision": float(average_precision_score(y_true, probabilities)),
        "confusion_matrix": cm.tolist(),
        "roc_curve": {
            "fpr": _downsample(fpr),
            "tpr": _downsample(tpr),
            "thresholds": [None if not np.isfinite(x) else float(x) for x in _downsample(roc_thresholds)],
        },
        "precision_recall_curve": {
            "precision": _downsample(precision),
            "recall": _downsample(recall),
            "thresholds": _downsample(pr_thresholds),
        },
    }


def train(data_path: Path, output_dir: Path, test_size: float, random_state: int, smote_ratio: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(data_path)
    validate_frame(df)

    X = df[REQUIRED_FEATURES].copy()
    y = df[TARGET].astype(int).copy()
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        stratify=y,
        random_state=random_state,
    )

    model = build_pipeline(smote_ratio=smote_ratio, random_state=random_state)
    model.fit(X_train, y_train)
    probabilities = model.predict_proba(X_test)[:, 1]
    metrics = evaluate(y_test, probabilities)

    predictions = (probabilities >= 0.5).astype(int)
    test_predictions = pd.DataFrame(
        {
            "actual_class": y_test.to_numpy(),
            "fraud_probability": probabilities,
            "predicted_class": predictions,
        }
    )
    test_predictions.to_csv(output_dir / "test_predictions.csv", index=False)

    metadata = {
        "model_name": "SMOTE + Logistic Regression",
        "feature_columns": REQUIRED_FEATURES,
        "target_column": TARGET,
        "dataset_rows": int(len(df)),
        "dataset_columns": int(len(REQUIRED_FEATURES)),
        "fraud_count": int(y.sum()),
        "legitimate_count": int((y == 0).sum()),
        "fraud_rate": float(y.mean()),
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "test_size": test_size,
        "random_state": random_state,
        "smote_sampling_strategy": smote_ratio,
        "threshold_default": 0.5,
        "notes": [
            "Time and Amount are robust-scaled inside the fitted pipeline.",
            "SMOTE is fit only on the training split; the test split remains untouched.",
            "The displayed probability is a model score, not a calibrated financial risk estimate.",
        ],
    }
    metadata = {key: _json_number(value) for key, value in metadata.items()}

    joblib.dump(model, output_dir / "fraud_pipeline.joblib", compress=3)
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(json.dumps({"metadata": metadata, "metrics": metrics}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/creditcard.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("models"))
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument(
        "--smote-ratio",
        type=float,
        default=0.25,
        help="Target minority/majority ratio after SMOTE; 0.25 is faster than full 50/50 balancing.",
    )
    args = parser.parse_args()
    train(
        data_path=args.data,
        output_dir=args.output_dir,
        test_size=args.test_size,
        random_state=args.random_state,
        smote_ratio=args.smote_ratio,
    )


if __name__ == "__main__":
    main()
