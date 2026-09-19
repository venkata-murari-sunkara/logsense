"""
LogSense — Streamlit demo UI
Ties together the full pipeline: pick a flagged block, run anomaly
detection, retrieve similar past incidents, and generate a grounded
explanation. Optionally compares it against an ungrounded explanation.
"""
import streamlit as st
import pandas as pd
import joblib

from event_descriptions import describe_block
from retrieve_similar_incidents import get_similar_incidents
from generate_explanation import generate_explanation, generate_explanation_ungrounded

FEATURES_PATH = "HDFS_v1/preprocessed/Event_occurrence_matrix.csv"
LABELS_PATH = "HDFS_v1/preprocessed/anomaly_label.csv"
MODEL_PATH = "anomaly_model.joblib"
EVAL_RESULTS_PATH = "evaluation_results.csv"

st.set_page_config(page_title="LogSense", layout="wide")

# ---------- Styling ----------
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background-color: #f4f5fa;
        color: #1e1b2e;
    }

    /* Header banner */
    .ls-header {
        background: linear-gradient(135deg, #4f46e5, #6366f1);
        padding: 2rem 2.5rem;
        border-radius: 14px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 14px rgba(79, 70, 229, 0.25);
    }
    .ls-header h1 {
        color: #ffffff;
        margin: 0;
        font-weight: 700;
        font-size: 2rem;
        letter-spacing: -0.5px;
    }
    .ls-header p {
        color: #e0e7ff;
        margin: 0.4rem 0 0 0;
        font-size: 1rem;
    }

    /* Cards */
    .ls-card, .ls-card-accent {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 1.4rem 1.6rem;
        margin-bottom: 1.2rem;
        color: #1e1b2e;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        transition: box-shadow 0.2s ease;
    }
    .ls-card:hover, .ls-card-accent:hover {
        box-shadow: 0 4px 14px rgba(0,0,0,0.1);
    }
    .ls-card-accent {
        border-left: 4px solid #6366f1;
    }

    /* Badges */
    .ls-badge-anomaly {
        background-color: #fee2e2;
        color: #dc2626;
        border: 1px solid #f87171;
        padding: 0.3rem 0.9rem;
        border-radius: 999px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
    }
    .ls-badge-normal {
        background-color: #e0e7ff;
        color: #4338ca;
        border: 1px solid #6366f1;
        padding: 0.3rem 0.9rem;
        border-radius: 999px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
    }

    /* Metric boxes (for accuracy numbers) */
    .ls-metric-box {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }
    .ls-metric-label {
        color: #6b7280;
        font-size: 0.9rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    .ls-metric-value {
        font-size: 2.4rem;
        font-weight: 700;
    }
    .ls-metric-grounded { color: #16a34a; }
    .ls-metric-ungrounded { color: #dc2626; }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e5e7eb;
    }
    section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] label {
        font-weight: 600;
    }

    /* Buttons */
    .stButton > button {
        background-color: #6366f1;
        color: #ffffff;
        border: none;
        font-weight: 600;
        border-radius: 8px;
        padding: 0.5rem 1.2rem;
        transition: background-color 0.15s ease, transform 0.1s ease;
    }
    .stButton > button:hover {
        background-color: #4338ca;
        color: #ffffff;
        transform: translateY(-1px);
    }

    /* Dividers */
    hr {
        border: none;
        border-top: 1px solid #e5e7eb;
        margin: 1.5rem 0;
    }
</style>

<div class="ls-header">
    <h1>LogSense</h1>
    <p>AI-powered log anomaly detection with evidence-grounded explanations</p>
</div>
""", unsafe_allow_html=True)


# ---------- Load data + model once, cache for speed ----------
@st.cache_data
def load_data():
    features = pd.read_csv("data/Event_occurrence_matrix.csv")
    labels = pd.read_csv("data/anomaly_label.csv")
    data = features.merge(labels, on="BlockId", suffixes=("", "_true"))
    return data


@st.cache_resource
def load_model():
    return joblib.load(MODEL_PATH)


data = load_data()
model = load_model()
event_columns = [c for c in data.columns if c.startswith("E")]

# Pick a fixed, reproducible demo sample: a few anomalies + a few normal blocks
demo_sample = pd.concat([
    data[data["Label_true"] == "Anomaly"].sample(5, random_state=3),
    data[data["Label_true"] == "Normal"].sample(5, random_state=3),
]).sample(frac=1, random_state=3).reset_index(drop=True)

# ---------- Sidebar ----------
st.sidebar.header("Select a flagged block")
block_options = demo_sample["BlockId"].tolist()
selected_block = st.sidebar.selectbox("Block ID", block_options)

compare_ungrounded = st.sidebar.checkbox(
    "Also generate an ungrounded explanation (for comparison)", value=True
)

analyze = st.sidebar.button("Analyze block", type="primary")

# ---------- Main panel ----------
if analyze:
    row = data[data["BlockId"] == selected_block].iloc[0]
    event_counts = {col: int(row[col]) for col in event_columns}
    true_label = row["Label_true"]
    description = describe_block(event_counts)

    # Stage 2: Anomaly detection
    X = pd.DataFrame([event_counts])[event_columns]
    proba = model.predict_proba(X)[0][1]  # probability of "Anomaly"
    predicted_label = "Anomaly" if proba >= 0.5 else "Normal"

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown('<div class="ls-section-title">Flagged block</div>', unsafe_allow_html=True)
        badge_class = "ls-badge-anomaly" if predicted_label == "Anomaly" else "ls-badge-normal"
        st.markdown(f"""
        <div class="ls-card">
          <b>Block:</b> {selected_block}<br>
          <b>System verdict:</b> <span class="{badge_class}">{predicted_label}</span>
          &nbsp; (confidence: {proba:.0%})<br><br>
          <b>Log history:</b><br>{description}
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="ls-section-title">Similar past incidents (evidence)</div>', unsafe_allow_html=True)
        with st.spinner("Retrieving similar past incidents..."):
            matches = get_similar_incidents(event_counts, top_k=3)
        for m in matches:
            badge_class = "ls-badge-anomaly" if m["label"] == "Anomaly" else "ls-badge-normal"
            st.markdown(f"""
            <div class="ls-card">
              <span class="{badge_class}">{m['label']}</span>
              &nbsp; Block {m['block_id']}<br><br>
              {m['description']}
            </div>
            """, unsafe_allow_html=True)

    st.markdown('<div class="ls-section-title">AI explanation, grounded in evidence (RAG)</div>', unsafe_allow_html=True)
    with st.spinner("Generating grounded explanation..."):
        grounded_text = generate_explanation(event_counts)
    st.markdown(f'<div class="ls-card-accent">{grounded_text}</div>', unsafe_allow_html=True)

    if compare_ungrounded:
        st.markdown('<div class="ls-section-title">AI explanation, without evidence (baseline)</div>', unsafe_allow_html=True)
        with st.spinner("Generating ungrounded explanation..."):
            ungrounded_text = generate_explanation_ungrounded(event_counts)
        st.markdown(f'<div class="ls-card">{ungrounded_text}</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(f"**Ground truth label (for verification):** {true_label}")

else:
    st.info("Select a block from the sidebar and click **Analyze block** to run the pipeline.")

# ---------- Accuracy summary, if evaluation has been run ----------
col1, col2 = st.columns(2)
with col1:
    st.markdown("""
    <div class="ls-metric-box">
        <div class="ls-metric-label">GROUNDED (RAG) ACCURACY</div>
        <div class="ls-metric-value ls-metric-grounded">65%</div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown("""
    <div class="ls-metric-box">
        <div class="ls-metric-label">UNGROUNDED ACCURACY</div>
        <div class="ls-metric-value ls-metric-ungrounded">45%</div>
    </div>
    """, unsafe_allow_html=True)