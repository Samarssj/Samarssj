from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sklearn.metrics import confusion_matrix, precision_recall_curve, roc_curve

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"
MODEL_PATH = MODEL_DIR / "fraud_pipeline.joblib"
METRICS_PATH = MODEL_DIR / "metrics.json"
METADATA_PATH = MODEL_DIR / "metadata.json"
PREDICTIONS_PATH = MODEL_DIR / "test_predictions.csv"

FEATURE_COLUMNS = ["Time", *[f"V{i}" for i in range(1, 29)], "Amount"]

st.set_page_config(
    page_title="CreditGuard | Fraud Detection",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .main { background: #f8fafc; }
        .block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1400px; }
        [data-testid="stSidebar"] { background: #0f172a; }
        [data-testid="stSidebar"] * { color: #e2e8f0; }
        .hero { padding: 1.4rem 1.6rem; border-radius: 18px; background: linear-gradient(135deg, #0f172a 0%, #164e63 100%); color: white; margin-bottom: 1.2rem; }
        .hero h1 { margin: 0; font-size: 2.25rem; letter-spacing: -0.04em; }
        .hero p { margin: 0.45rem 0 0; color: #cbd5e1; font-size: 1.02rem; }
        .status-card { padding: 1rem; border-radius: 14px; border: 1px solid #e2e8f0; background: white; }
        .small-muted { color: #64748b; font-size: 0.88rem; }
        div[data-testid="stMetric"] { background: white; border: 1px solid #e2e8f0; padding: 0.85rem; border-radius: 14px; }
    </style>
    """,
    unsafe_allow_html=True,
)


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_resource(show_spinner=False)
def load_model():
    if not MODEL_PATH.exists():
        return None
    return joblib.load(MODEL_PATH)


@st.cache_data(show_spinner=False)
def load_evaluation_data() -> pd.DataFrame:
    if not PREDICTIONS_PATH.exists():
        return pd.DataFrame()
    return pd.read_csv(PREDICTIONS_PATH)


metadata = load_json(METADATA_PATH)
metrics = load_json(METRICS_PATH)
model = load_model()
evaluation_df = load_evaluation_data()

with st.sidebar:
    st.markdown("## CreditGuard")
    st.caption("Imbalance-aware credit-card fraud detection")
    page = st.radio(
        "Navigate",
        ["Overview", "Single transaction", "Batch scoring", "Model evaluation"],
        label_visibility="collapsed",
    )
    st.divider()
    st.markdown("### Decision threshold")
    threshold = st.slider(
        "Flag as fraud when probability is at least",
        min_value=0.05,
        max_value=0.95,
        value=float(metadata.get("threshold_default", 0.50)),
        step=0.01,
        format="%.2f",
    )
    st.caption("Lower thresholds catch more fraud but may increase false positives.")
    st.divider()
    if model is None:
        st.error("Model artifact not found")
        st.caption("Run `python train_model.py` before launching the app.")
    else:
        st.success("Model artifact loaded")
        st.caption(str(metadata.get("model_name", "Fraud model")))

st.markdown(
    '<div class="hero"><h1>CreditGuard</h1><p>Explainable, threshold-aware fraud screening for anonymized card transactions.</p></div>',
    unsafe_allow_html=True,
)


def metric_or_dash(key: str) -> str:
    value = metrics.get(key)
    return "—" if value is None else f"{float(value):.3f}"


def score_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if model is None:
        raise RuntimeError("The model artifact is unavailable.")
    missing = [c for c in FEATURE_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"Missing required feature columns: {', '.join(missing)}")
    features = frame[FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    if features.isna().any().any():
        bad = features.columns[features.isna().any()].tolist()
        raise ValueError(f"Non-numeric or missing values found in: {', '.join(bad)}")
    result = frame.copy()
    probability = model.predict_proba(features)[:, 1]
    result["fraud_probability"] = probability
    result["decision"] = np.where(probability >= threshold, "Review / likely fraud", "Likely legitimate")
    return result


def show_overview() -> None:
    if not metadata:
        st.warning("No trained model metadata is available yet. Run the training script first.")
        return
    st.subheader("Monitoring overview")
    st.write("This app transforms the notebook into a reusable scoring workflow. The model is trained on the original imbalanced data after a stratified split, applies robust scaling to `Time` and `Amount`, and uses SMOTE only within the training pipeline.")

    cols = st.columns(5)
    cols[0].metric("Transactions", f"{int(metadata.get('dataset_rows', 0)):,}")
    cols[1].metric("Fraud cases", f"{int(metadata.get('fraud_count', 0)):,}")
    cols[2].metric("Fraud rate", f"{float(metadata.get('fraud_rate', 0)) * 100:.3f}%")
    cols[3].metric("Average precision", metric_or_dash("average_precision"))
    cols[4].metric("ROC-AUC", metric_or_dash("roc_auc"))

    left, right = st.columns([1.05, 0.95])
    with left:
        st.markdown("#### Why imbalance-aware evaluation matters")
        st.info("Fraud is a rare class in this benchmark. Accuracy alone can look strong even when a model misses most fraud cases, so the app emphasizes recall, precision, F1, ROC-AUC, and average precision.")
        st.markdown("#### Model configuration")
        config = pd.DataFrame(
            {
                "Setting": ["Model", "Resampling", "Scaled columns", "Threshold", "Test rows"],
                "Value": [
                    metadata.get("model_name", "—"),
                    f"SMOTE ratio {metadata.get('smote_sampling_strategy', '—')}",
                    "Time, Amount",
                    f"{threshold:.2f}",
                    f"{int(metadata.get('test_rows', 0)):,}",
                ],
            }
        )
        st.dataframe(config, hide_index=True, use_container_width=True)
    with right:
        if metadata.get("fraud_count") is not None:
            counts = pd.DataFrame({"Class": ["Legitimate", "Fraud"], "Transactions": [metadata.get("legitimate_count", 0), metadata.get("fraud_count", 0)]})
            fig = px.bar(counts, x="Class", y="Transactions", color="Class", color_discrete_map={"Legitimate": "#0e7490", "Fraud": "#dc2626"}, title="Training dataset class distribution")
            fig.update_layout(showlegend=False, height=360, margin=dict(l=10, r=10, t=55, b=10))
            st.plotly_chart(fig, use_container_width=True)


def show_single_transaction() -> None:
    st.subheader("Screen one transaction")
    st.write("Enter the 30 numeric inputs expected by the model. `V1`–`V28` are anonymized PCA-derived features from the benchmark dataset; they do not have a direct business interpretation.")
    if model is None:
        st.error("The model artifact is unavailable. Train the model locally and place `models/fraud_pipeline.joblib` in this project.")
        return

    with st.form("single_transaction_form"):
        first = st.columns(2)
        with first[0]:
            time_value = st.number_input("Time", min_value=0.0, value=0.0, step=1.0)
        with first[1]:
            amount_value = st.number_input("Amount", min_value=0.0, value=100.0, step=1.0)
        st.markdown("##### Anonymized PCA features")
        feature_cols = st.columns(4)
        values: dict[str, float] = {}
        for i in range(1, 29):
            with feature_cols[(i - 1) % 4]:
                values[f"V{i}"] = st.number_input(f"V{i}", value=0.0, step=0.01, format="%.6f")
        submitted = st.form_submit_button("Run fraud screening", type="primary", use_container_width=True)

    if submitted:
        row = {"Time": time_value, **values, "Amount": amount_value}
        scored = score_frame(pd.DataFrame([row]))
        probability = float(scored.loc[0, "fraud_probability"])
        decision = scored.loc[0, "decision"]
        st.divider()
        if probability >= threshold:
            st.error(f"Decision: {decision}")
        else:
            st.success(f"Decision: {decision}")
        m1, m2, m3 = st.columns(3)
        m1.metric("Fraud probability", f"{probability:.2%}")
        m2.metric("Threshold", f"{threshold:.2%}")
        m3.metric("Model score", f"{probability:.4f}")
        gauge = go.Figure(go.Indicator(mode="gauge+number", value=probability * 100, number={"suffix": "%"}, title={"text": "Fraud probability"}, gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#dc2626" if probability >= threshold else "#0e7490"}, "threshold": {"line": {"color": "#111827", "width": 4}, "thickness": 0.8, "value": threshold * 100}}))
        gauge.update_layout(height=290, margin=dict(l=35, r=35, t=50, b=10))
        st.plotly_chart(gauge, use_container_width=True)
        st.caption("This is a benchmark-model score and should not be used as the sole basis for a real financial decision.")


def show_batch_scoring() -> None:
    st.subheader("Score a transaction file")
    st.write("Upload a CSV containing `Time`, `V1`–`V28`, and `Amount`. If a `Class` column is present, it is preserved for comparison but is not used during scoring.")
    uploaded = st.file_uploader("Upload CSV", type=["csv"])
    if uploaded is None:
        st.info("No file uploaded. Use the single-transaction page for an interactive example.")
        return
    try:
        frame = pd.read_csv(uploaded)
        scored = score_frame(frame)
    except Exception as exc:
        st.error(str(exc))
        return
    fraud_count = int((scored["fraud_probability"] >= threshold).sum())
    st.success(f"Scored {len(scored):,} rows; {fraud_count:,} crossed the current threshold.")
    c1, c2 = st.columns(2)
    c1.metric("Likely fraud / review", f"{fraud_count:,}")
    c2.metric("Likely legitimate", f"{len(scored) - fraud_count:,}")
    st.dataframe(scored[[*FEATURE_COLUMNS[:2], "Amount", "fraud_probability", "decision"] + (["Class"] if "Class" in scored else [])], use_container_width=True, height=420)
    st.download_button("Download scored CSV", scored.to_csv(index=False).encode("utf-8"), "fraud_scored_transactions.csv", "text/csv", use_container_width=True)


def show_evaluation() -> None:
    st.subheader("Model evaluation")
    if not metrics or evaluation_df.empty:
        st.warning("Evaluation artifacts are unavailable. Run the training script first.")
        return
    st.write("The metrics below were calculated on the untouched stratified test split. Adjust the sidebar threshold to see how the confusion matrix changes at review time.")
    y_true = evaluation_df["actual_class"].astype(int).to_numpy()
    probabilities = evaluation_df["fraud_probability"].to_numpy()
    predictions = (probabilities >= threshold).astype(int)
    cm = confusion_matrix(y_true, predictions, labels=[0, 1])
    precision, recall, _ = precision_recall_curve(y_true, probabilities)
    fpr, tpr, _ = roc_curve(y_true, probabilities)

    cols = st.columns(5)
    cols[0].metric("Precision", f"{((cm[1,1] / (cm[1,1] + cm[0,1])) if (cm[1,1] + cm[0,1]) else 0):.3f}")
    cols[1].metric("Recall", f"{((cm[1,1] / (cm[1,1] + cm[1,0])) if (cm[1,1] + cm[1,0]) else 0):.3f}")
    p = (cm[1,1] / (cm[1,1] + cm[0,1])) if (cm[1,1] + cm[0,1]) else 0
    r = (cm[1,1] / (cm[1,1] + cm[1,0])) if (cm[1,1] + cm[1,0]) else 0
    cols[2].metric("F1", f"{(2*p*r/(p+r) if p+r else 0):.3f}")
    cols[3].metric("Average precision", metric_or_dash("average_precision"))
    cols[4].metric("Flagged rows", f"{int(predictions.sum()):,}")

    left, right = st.columns(2)
    with left:
        cm_df = pd.DataFrame(cm, index=["Actual legitimate", "Actual fraud"], columns=["Predicted legitimate", "Predicted fraud"])
        fig = px.imshow(cm_df, text_auto=True, color_continuous_scale="Blues", title=f"Confusion matrix at threshold {threshold:.2f}")
        fig.update_layout(height=390, margin=dict(l=10, r=10, t=55, b=10))
        st.plotly_chart(fig, use_container_width=True)
    with right:
        roc_fig = go.Figure()
        roc_fig.add_trace(go.Scatter(x=fpr, y=tpr, mode="lines", name="ROC curve", line={"color": "#0e7490"}))
        roc_fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="Random baseline", line={"dash": "dash", "color": "#94a3b8"}))
        roc_fig.update_layout(title=f"ROC curve · AUC {float(metrics.get('roc_auc', 0)):.3f}", xaxis_title="False-positive rate", yaxis_title="True-positive rate", height=390, margin=dict(l=10, r=10, t=55, b=10))
        st.plotly_chart(roc_fig, use_container_width=True)

    pr_fig = go.Figure(go.Scatter(x=recall, y=precision, mode="lines", line={"color": "#dc2626"}))
    pr_fig.update_layout(title=f"Precision-recall curve · AP {float(metrics.get('average_precision', 0)):.3f}", xaxis_title="Recall", yaxis_title="Precision", height=390, margin=dict(l=10, r=10, t=55, b=10))
    st.plotly_chart(pr_fig, use_container_width=True)

    st.markdown("#### Threshold trade-off")
    threshold_rows = []
    for value in np.linspace(0.05, 0.95, 19):
        pred = (probabilities >= value).astype(int)
        matrix = confusion_matrix(y_true, pred, labels=[0, 1])
        tp, fp, fn = matrix[1, 1], matrix[0, 1], matrix[1, 0]
        p = tp / (tp + fp) if tp + fp else 0
        r = tp / (tp + fn) if tp + fn else 0
        threshold_rows.append({"threshold": round(float(value), 2), "precision": p, "recall": r, "flagged": int(pred.sum())})
    threshold_df = pd.DataFrame(threshold_rows)
    st.dataframe(threshold_df.style.format({"precision": "{:.3f}", "recall": "{:.3f}"}), use_container_width=True, hide_index=True)


if page == "Overview":
    show_overview()
elif page == "Single transaction":
    show_single_transaction()
elif page == "Batch scoring":
    show_batch_scoring()
else:
    show_evaluation()

st.divider()
st.caption("CreditGuard is an educational benchmark application. It is not a substitute for a production fraud operations system, calibrated risk model, regulatory review, or human investigation.")
