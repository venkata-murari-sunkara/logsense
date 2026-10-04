import threading

import joblib
import pandas as pd

from app.config import REPO_ROOT

MODEL_PATH = REPO_ROOT / "anomaly_model.joblib"
EVENT_COLUMNS = [f"E{i}" for i in range(1, 30)]

_model_lock = threading.Lock()
_model = None

# sentence-transformers proved that concurrent native-BLAS inference calls
# can crash this process outright (see embeddings.py); serialize predict_proba
# too as a precaution even though scikit-learn's LogisticRegression is much
# lighter weight — the cost is negligible and it's not worth re-learning
# that lesson the hard way a second time.
_inference_lock = threading.Lock()


def get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = joblib.load(MODEL_PATH)
    return _model


def predict(event_counts: dict) -> tuple[str, float]:
    """Returns (predicted_label, confidence) for a block's event counts.

    confidence is the probability of whichever class was predicted (not
    always P(anomaly)) so a "Normal" verdict shows how confident the model
    is in "Normal", not the near-zero P(anomaly) that produced it.
    """
    model = get_model()
    row = {col: int(event_counts.get(col, 0)) for col in EVENT_COLUMNS}
    X = pd.DataFrame([row])[EVENT_COLUMNS]
    with _inference_lock:
        proba_anomaly = float(model.predict_proba(X)[0][1])
    label = "Anomaly" if proba_anomaly >= 0.5 else "Normal"
    confidence = max(proba_anomaly, 1 - proba_anomaly)
    return label, confidence
